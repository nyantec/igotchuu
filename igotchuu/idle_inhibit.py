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
