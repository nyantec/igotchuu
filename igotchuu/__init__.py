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
import os
import sys
import datetime
import subprocess
import json
import threading
import functools
import gi
from gi.repository import Gio, GLib
import igotchuu.btrfs as btrfs
import igotchuu.idle_inhibit
import igotchuu.glib_loop
import igotchuu.dbus_service
from igotchuu.mount import mount, MountFlags
from igotchuu.restic import Restic

class DBusBackupManagerInterface(igotchuu.dbus_service.DbusService):
    introspection_xml = """
    <!DOCTYPE node PUBLIC
     "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
     "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
    <node name="/com/nyantec/igotchuu">
        <interface name="com.nyantec.igotchuu1">
            <method name="Stop"></method>
            <signal name="Error">
            </signal>
            <signal name="BackupStarted">
            </signal>
            <signal name="Progress">
                <arg name="json_data" type="s"/>
            </signal>
            <signal name="BackupComplete">
            </signal>
        </interface>
    </node>
    """
    publish_path = '/com/nyantec/igotchuu'

    def __init__(self, dbus, restic=None):
        super().__init__(dbus, self.introspection_xml, self.publish_path)
        self.restic = restic

    def Stop(self):
        if self.restic is not None:
            self.restic.terminate()

def reexec(function):
    @functools.wraps(function)
    def _reexec(*args, **kwargs):
        if os.environ.get("_REEXEC") != "done":
            print("argv:", sys.argv, file=sys.stderr)
            os.execvpe(
                "unshare",
                ["unshare", "-m", *sys.argv],
                {"_REEXEC": "done", **os.environ}
            )
            print("Failed to re-exec")
            exit(1)
        else:
            function(*args, **kwargs)

    return _reexec

def verbose(*args, **kwargs):
    if "--verbose" in sys.argv:
        print(*args, **kwargs, file=sys.stderr)

@reexec
def cli():
    bus_ready_barrier = threading.Barrier(2)
    backup_manager = None

    verbose("Preparing for backup...")

    def on_bus_acquired(dbus, name):
        verbose("Acquired DBus connection:", dbus, name)
        nonlocal backup_manager
        backup_manager = DBusBackupManagerInterface(dbus, restic=None)
        verbose("Created backup manager object:", backup_manager)

    def on_name_acquired(dbus, name):
        verbose("Acquired bus name:", dbus, name)
        bus_ready_barrier.wait()

    def on_name_lost(dbus, name):
        verbose("Lost bus name:", dbus, name)
        nonlocal backup_manager
        if backup_manager is not None:
            backup_manager.unregister()
            backup_manager = None

    verbose("Starting glib main loop...")
    igotchuu.glib_loop.GLibMainLoopThread().start()

    name = Gio.bus_own_name(
        Gio.BusType.SYSTEM, "com.nyantec.IGotChuu",
        Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
        on_bus_acquired,
        on_name_acquired,
        on_name_lost
    )
    verbose("Waiting for bus name to be acquired...")
    bus_ready_barrier.wait()
    # Retrieve the D-Bus connection again
    # Should be a singleton anyway
    dbus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
    logind = igotchuu.idle_inhibit.Logind(dbus)

    with logind.inhibit("sleep:handle-lid-switch", "igotchuu", "Backup in progress", "block"):
        verbose("Creating snapshot...")
        # Create a filesystem snapshot that will be deleted later
        snapshot_path="/home-{}".format(datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"))
        btrfs.create_snapshot("/home", snapshot_path, readonly=True)

        try:
            verbose("Remounting home...")
            mount(snapshot_path, "/home", flags=MountFlags.MS_BIND)
            verbose("Running restic...")

            backup_manager.restic = Restic.backup(places=["/home"], extra_args=[
                "-x", "--exclude-caches",
                "--exclude-file", "/home/vika/Projects/nix-flake/backup-exclude.txt"
            ])
            dbus.emit_signal(
                None,
                "/com/nyantec/igotchuu",
                "com.nyantec.igotchuu1",
                "BackupStarted",
                None
            )
            for progress in backup_manager.restic.progress_iter():
                if progress["message_type"] == "status":
                    dbus.emit_signal(
                        None,
                        "/com/nyantec/igotchuu",
                        "com.nyantec.igotchuu1",
                        "Progress",
                        GLib.Variant.new_tuple(
                            GLib.Variant.new_string(json.dumps(progress))
                        )
                    )
                    if "seconds_remaining" not in progress:
                        # Scan isn't complete yet
                        print("[scan...]", end=" ")
                    else:
                        print(f"[{progress['percent_done']: >7.2%}]", end=" ")

                    print(f"{progress.get('files_done', 0)}/{progress['total_files']} files", end=", ")
                    print(f"{progress.get('bytes_done', 0) / (1024**3):5.2f}/{progress['total_bytes'] / (1024**3):5.2f}G uploaded", end=" ")
                    print("\r", end="")
                elif progress["message_type"] == "summary":
                    dbus.emit_signal(
                        None,
                        "/com/nyantec/igotchuu",
                        "com.nyantec.igotchuu1",
                        "BackupComplete",
                        None
                    )
                    print()
                    print(progress)
                    break
        finally:
            if backup_manager.restic is not None:
                verbose("Waiting for restic to terminate...")
                backup_manager.restic.wait()
            verbose("Deleting snapshot...")
            btrfs.remove_snapshot(snapshot_path)
            Gio.bus_unown_name(name)
