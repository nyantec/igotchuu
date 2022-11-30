#!/usr/bin/env python3
import sys
import os

# TODO re-execute with pkexec if we're not root?
#
# This script technically is supposed to be ran via cron or systemd
# timers, but could potentially be ran directly by user if they wish
# to take an unscheduled backup. In this situation we might actually
# want to re-exec ourselves as root, potentially presenting a nice
# prompt to the user.
#
# (Backups are a good thing, but some might only want admins to run
# them... so we'll use polkit. Besides, this script does some funky
# stuff with mounts and subvolumes.)

# Re-execute in an unshared namespace to clear bind-mounts on exit
if os.environ.get("_BACKUP_REEXEC") != "done":
    print("Unsharing namespaces...")
    os.execvpe(
        "/run/current-system/sw/bin/unshare",
        ["unshare", "-m", sys.executable] + sys.argv,
        {"_BACKUP_REEXEC": "done", **os.environ}
    )
    print("Failed to re-exec")
    exit(1)
else:
    print("We should've been re-executed...")

# We are now guaranteed to be in an unshared mount namespace.
#
# Proceed with the rest of the script.
import datetime
import subprocess
import json
import threading
import gi
from gi.repository import Gio, GLib
import igotchuu.btrfs as btrfs
import igotchuu.idle_inhibit
import igotchuu.glib_loop
import igotchuu.dbus_service
from igotchuu.mount import mount, MountFlags
from igotchuu.restic import Restic

bus_ready_barrier = threading.Barrier(2)

#def vtable_method_call_cb(
#    connection: Gio.DBusConnection,
#    sender: str,
#    object_path: str,
#    interface_name: str,
#    method_name: str,
#    params: GLib.Variant,
#    invocation: Gio.DBusMethodInvocation
#):
#    pass

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

    def __init__(self, dbus):
        super().__init__(dbus, self.introspection_xml, self.publish_path)

    def Stop(self):
        global restic
        if restic is not None:
            restic.terminate()


backup_manager = None

def on_bus_acquired(dbus, name):
    global backup_manager
    backup_manager = DBusBackupManagerInterface(dbus)

def on_name_acquired(dbus, name):
    bus_ready_barrier.wait()

def on_name_lost(dbus, name):
    # TODO un-export objects
    global backup_manager
    if backup_manager is not None:
        backup_manager.unregister()
        backup_manager = None

# We could potentially own a DBus name here
# This would allow:
# - exposing a method to cancel a running backup
# - sending signals with progress data/errors
# - using polkit to accept requests from unprivileged users via Polkit's CheckAuthorization method
igotchuu.glib_loop.GLibMainLoopThread().start()
name = Gio.bus_own_name(
    Gio.BusType.SYSTEM, "com.nyantec.IGotChuu",
    Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
    on_bus_acquired,
    on_name_acquired,
    on_name_lost
)
bus_ready_barrier.wait()
# Retrieve the D-Bus connection again
# Should be a singleton anyway
dbus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
logind = igotchuu.idle_inhibit.Logind(dbus)

with logind.inhibit("sleep:handle-lid-switch", "igotchuu", "Backup in progress", "block"):
    print("Creating snapshot...")
    # Create a filesystem snapshot that will be deleted later
    snapshot_path="/home-{}".format(datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"))
    btrfs.create_snapshot("/home", snapshot_path, readonly=True)

    restic = None

    try:
        print("Remounting home...")
        mount(snapshot_path, "/home", flags=MountFlags.MS_BIND)
        print("Running restic")

        restic = Restic.backup(places=["/home"], extra_args=[
            "-x", "--exclude-caches", "--dry-run",
            "--exclude-file", "/home/vika/Projects/nix-flake/backup-exclude.txt"
        ])
        dbus.emit_signal(
            None,
            "/com/nyantec/igotchuu",
            "com.nyantec.igotchuu1",
            "BackupStarted",
            None
        )
        for progress in restic.progress_iter():
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
        if restic is not None:
            restic.wait()
        print("Deleting snapshot...")
        btrfs.remove_snapshot(snapshot_path)
        Gio.bus_unown_name(name)
