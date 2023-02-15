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
import json
import argparse
import tomllib
import threading
import functools
import btrfsutil
import gi
from gi.repository import Gio, GLib
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
            <signal name="Error"></signal>
            <signal name="BackupStarted"></signal>
            <signal name="Progress">
                <arg name="json_data" type="a{sv}"/>
            </signal>
            <signal name="BackupComplete"></signal>
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

@reexec
def cli():
    parser = argparse.ArgumentParser(
        prog = 'igotchuu',
        description = 'A backup software based on restic and btrfs snapshots'
    )
    parser.add_argument('-c', '--config-file', required=True)
    parser.add_argument('-v', '--verbose', action="store_true")
    args = parser.parse_args()

    def verbose(*arguments, **kwargs):
        if args.verbose:
            print(*arguments, **kwargs, file=sys.stderr)

    config = {
        "places": ["/home"], "snapshot": ["/home"],
        "restic_args": ["-x", "--exclude-caches"]
    }
    if "config_file" in args:
        with open(args.config_file, "rb") as f:
            config = tomllib.load(f)
        if "places" not in config:
            config["places"] = ["/home"]
        if "snapshot" not in config:
            config["snapshot"] = config["places"]
        for place in config["places"]:
            if place[0] != "/":
                print("Error: paths in `sources` must be absolute, got", place)
                exit(1)
        if config["snapshot"] != config["places"]:
            for snapshot in config["snapshots"]:
                if isinstance(snapshot, str):
                    snapshot = {"source": snapshot}
                if snapshot["source"][0] != "/":
                    print("Error: snapshot source paths must be absolute, got", snapshot["source"])
                    exit(1)
        verbose("Acquired config:", config)

    bus_ready_barrier = threading.Barrier(2)
    name_acquired = False
    backup_manager = None

    verbose("Preparing for backup...")

    def on_bus_acquired(dbus, name):
        verbose("Acquired DBus connection:", dbus, name)
        nonlocal backup_manager
        backup_manager = DBusBackupManagerInterface(dbus, restic=None)
        verbose("Created backup manager object:", backup_manager)

    def on_name_acquired(dbus, name):
        nonlocal name_acquired
        name_acquired = True
        verbose("Acquired bus name:", dbus, name)
        bus_ready_barrier.wait()

    def on_name_lost(dbus, name):
        nonlocal name_acquired
        if name_acquired:
            verbose("Lost bus name:", dbus, name)
            nonlocal backup_manager
            if backup_manager is not None:
                backup_manager.unregister()
                backup_manager = None
        else:
            print("Cannot acquire name on the bus.", file=sys.stderr)
            sys.exit(1)

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
        if "exec_before_snapshot" in config:
            verbose("Executing", config["exec_before_snapshot"])
            import subprocess
            subprocess.run(config["exec_before_snapshot"])
        verbose("Creating snapshots...")
        # Create a filesystem snapshot that will be deleted later
        timestamp = datetime.datetime.now()
        for place in config["snapshot"]:
            if isinstance(place, str):
                place = {
                    "source": place,
                    "snapshot_location": os.path.join(config.get("snapshot_prefix", ""), place[1:])
                }
            
            snapshot_path="{place}-{timestamp}".format(
                place=place["source"],
                timestamp=timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")   
            )
            verbose("Creating snapshot for", place["source"], "at", snapshot_path)
            os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
            btrfsutil.create_snapshot(place["source"], snapshot_path, read_only=True)

        try:
            for place in config["snapshot"]:
                if isinstance(place, str):
                    place = {
                        "source": place,
                        "snapshot_location": os.path.join(config.get("snapshot_prefix", ""), place[1:])
                    }
                snapshot_path="{place}-{timestamp}".format(
                    place=place["source"],
                    timestamp=timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")
                )
                verbose("Remounting {} to {}...".format(snapshot_path, place["source"]))
                mount(snapshot_path, place["source"], flags=MountFlags.MS_BIND)
            verbose("Running restic...")

            backup_manager.restic = Restic.backup(places=config["places"], extra_args=config.get("restic_args", []))
            dbus.emit_signal(
                None,
                "/com/nyantec/igotchuu",
                "com.nyantec.igotchuu1",
                "BackupStarted",
                None
            )
            for progress in backup_manager.restic.progress_iter():
                if progress["message_type"] == "status":
                    # Map JSON progress keys to GLib.Variant
                    # I wonder if there's a way to do this automatically?
                    glib_progress = GLib.VariantBuilder.new("a{sv}")
                    for key in keys(progress):
                        if type(progress[key]) == int:
                            glib_progress.add_value(
                                GLib.Variant.new_dict_entry(
                                    GLib.Variant.new_string(key)
                                    GLib.Variant.new_variant(
                                        GLib.Variant.new_int64(progress[key])
                                    )
                                )
                            )
                        elif type(progress[key]) == float:
                            glib_progress.add_value(
                                GLib.Variant.new_dict_entry(
                                    GLib.Variant.new_string(key)
                                    GLib.Variant.new_variant(
                                        GLib.Variant.new_double(progress[key])
                                    )
                                )
                            )
                        elif type(progress[key]) == str:
                            glib_progress.add_value(
                                GLib.Variant.new_dict_entry(
                                    GLib.Variant.new_string(key)
                                    GLib.Variant.new_variant(
                                        GLib.Variant.new_string(progress[key])
                                    )
                                )
                            )
                        elif key == "current_files":
                            glib_progress.add_value(
                                GLib.Variant.new_dict_entry(
                                    GLib.Variant.new_string(key)
                                    GLib.Variant.new_variant(
                                        GLib.Variant.new_array(
                                            GLib.VariantType.new("s"),
                                            list(map(GLib.Variant.new_string, progress[key]))
                                        )
                                    )
                                )
                            )
                        else:
                            raise TypeError("Unknown key type: {} for {}".format(type(progress[key]), key))
                    dbus.emit_signal(
                        None,
                        "/com/nyantec/igotchuu",
                        "com.nyantec.igotchuu1",
                        "Progress",
                        GLib.Variant.new_tuple(glib_progress.end())
                    )
                    if "seconds_remaining" not in progress:
                        # Scan isn't complete yet
                        print("[scan...]", end=" ")
                    else:
                        print(f"[{progress['percent_done']: >7.2%}]", end=" ")

                    print(f"{progress.get('files_done', 0)}/{progress['total_files']} files", end=", ")
                    if "total_bytes" in progress:
                        print(f"{progress.get('bytes_done', 0) / (1024**3):5.2f}/{progress['total_bytes'] / (1024**3):5.2f}G uploaded", end=" ")
                    else:
                        print(f"{progress.get('bytes_done', 0) / (1024**3):5.2f}G uploaded", end=" ")
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
            verbose("Deleting snapshots...")
            for place in config["snapshot"]:
                if isinstance(place, str):
                    place = {
                        "source": place,
                        "snapshot_location": os.path.join(
                            config.get("snapshot_prefix", ""),
                            place
                        )
                    }
                snapshot_path="{place}-{timestamp}".format(
                    place=place["source"],
                    timestamp=timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")   
                )
                btrfsutil.delete_subvolume(snapshot_path)
            Gio.bus_unown_name(name)
