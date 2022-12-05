# Copyright © 2022 nyantec GmbH <oss@nyantec.com>
# Written by Vika Shleina <vsh@nyantec.com>
#
# Provided that these terms and disclaimer and all copyright notices
# are retained or reproduced in an accompanying document, permission
# is granted to deal in this work without restriction, including un‐
# limited rights to use, publicly perform, distribute, sell, modify,
# merge, give away, or sublicence.
#
# This work is provided "AS IS" and WITHOUT WARRANTY of any kind, to
# the utmost extent permitted by applicable law, neither express nor
# implied; without malicious intent or gross negligence. In no event
# may a licensor, author or contributor be held liable for indirect,
# direct, other damage, loss, or other issues arising in any way out
# of dealing in the work, even if advised of the possibility of such
# damage or existence of a defect, except proven that it results out
# of said person's immediate fault when using the work as intended.
import sys
import os
from gi.repository import GLib, Gio

class Inhibitor:
    """A systemd-logind inhibitor that should be used as a context manager."""
    def __init__(self, dbus_response, what, who, why, mode):
        index = dbus_response[0].get_child_value(0).get_handle()
        fds = dbus_response.out_fd_list.steal_fds()
        self._fd = fds[0]
        self.what = what
        self.who = who
        self.why = why
        self.mode = mode
    def close(self):
        os.close(self._fd)
    def __enter__(self):
        return self
    def __exit__(self, *exc_info):
        self.close()


class NullInhibitor:
    """A fake inhibitor that can be used as a substitute for a real one. Does nothing."""
    def __init__(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self):
        pass


class Logind:
    """An abstraction over systemd-logind's D-Bus interface."""
    def __init__(self, dbus):
        """Connect to systemd-logind via the D-Bus connection specified."""
        self.dbus = Gio.DBusProxy.new_sync(
            dbus, Gio.DBusProxyFlags.NONE, None,
            'org.freedesktop.login1', '/org/freedesktop/login1',
            'org.freedesktop.login1.Manager',
            None
        )
    def inhibit(self, what, who, why, mode):
        """Get an inhibitor object suppressing or blocking idle or sleep actions.

        It is recommended to use this method as a context manager.

        In case of permission errors, returns a null inhibitor that does nothing."""
        try:
            response = self.dbus.call_with_unix_fd_list_sync(
                'Inhibit',
                # These are a pain to construct
                GLib.Variant.new_tuple(
                    GLib.Variant.new_string(what),
                    GLib.Variant.new_string(who),
                    GLib.Variant.new_string(why),
                    GLib.Variant.new_string(mode)
                ),
                Gio.DBusCallFlags.NO_AUTO_START,
                500,
                None
            )
            return Inhibitor(response, what, who, why, mode)
        except GLib.Error as e:
            if e.matches('g-dbus-error-quark', 9):
                # Permission denied
                print("Can't get inhibitor lock:", e)
                return NullInhibitor()
            else:
                raise e
