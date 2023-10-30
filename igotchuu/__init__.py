# Copyright © 2022-2023 nyantec GmbH <oss@nyantec.com>
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
import subprocess
import btrfsutil
import gi
import unshare
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
            <signal name="BackupStarted"></signal>
            <!-- Signal payload mirrors structs found in Restic's source code
                 https://github.com/restic/restic/blob/master/internal/ui/backup/json.go
              -->
            <signal name="Progress">
                <arg name="seconds_elapsed" type="t" />   <!-- uint64 -->
                <arg name="seconds_remaining" type="t" />
                <arg name="percent_done" type="d" />      <!-- float64 -->
                <arg name="total_files" type="t" />
                <arg name="files_done" type="t" />
                <arg name="total_bytes" type="t" />
                <arg name="bytes_done" type="t" />
                <arg name="error_count" type="t" />       <!-- uint -->
                <arg name="current_files" type="as" />    <!-- []string -->
            </signal>
            <signal name="BackupComplete">
                <arg name="files_new" type="t" />
                <arg name="files_changed" type="t" />
                <arg name="files_unmodified" type="t" />
                <arg name="dirs_new" type="t" />
                <arg name="dirs_changed" type="t" />
                <arg name="dirs_unmodified" type="t" />
                <arg name="data_blobs" type="x" />        <!-- int -->
                <arg name="tree_blobs" type="x" />
                <arg name="data_added" type="t" />
                <arg name="total_files_processed" type="t" />
                <arg name="total_bytes_processed" type="t" />
                <arg name="total_duration" type="d" />
                <arg name="snapshot_id" type="s" />       <!-- string -->
                <arg name="dry_run" type="b" />           <!-- bool -->
            </signal>
            <signal name="Error">
              <arg name="error" type="s" />               <!-- error -->
              <arg name="during" type="s" />
              <arg name="item" type="s" />
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


def cli():
    parser = argparse.ArgumentParser(
        prog = 'igotchuu',
        description = 'A backup software based on restic and btrfs snapshots'
    )
    parser.add_argument('-c', '--config-file', default="/etc/igotchuu.toml")
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
        verbose("Unsharing mount namespace...")
        unshare.unshare(unshare.CLONE_NEWNS)
        verbose("Making / mount private...")
        mount("none", "/", None, MountFlags.MS_PRIVATE | MountFlags.MS_REC, None)
        if "exec_before_snapshot" in config and config["exec_before_snapshot"] is not None:
            verbose("Executing", config["exec_before_snapshot"])
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
            progress_percentage_int = 0
            verbose("Is stdout a tty? ", sys.stdout.isatty())
            if not sys.stdout.isatty():
                print("scanning...", file=sys.stderr)
            for progress in backup_manager.restic.progress_iter():
                if progress["message_type"] == "status":
                    # Map JSON progress keys to GLib.Variant
                    # I wonder if there's a way to do this automatically?
                    dbus.emit_signal(
                        None,
                        "/com/nyantec/igotchuu",
                        "com.nyantec.igotchuu1",
                        "Progress",
                        GLib.Variant.new_tuple(
                            GLib.Variant.new_uint64(progress.get("seconds_elapsed", 0)),
                            GLib.Variant.new_uint64(progress.get("seconds_remaining", 0)),
                            GLib.Variant.new_double(float(progress.get("percent_done", 0.0))),
                            GLib.Variant.new_uint64(progress.get("total_files", 0)),
                            GLib.Variant.new_uint64(progress.get("files_done", 0)),
                            GLib.Variant.new_uint64(progress.get("total_bytes", 0)),
                            GLib.Variant.new_uint64(progress.get("bytes_done", 0)),
                            GLib.Variant.new_uint64(progress.get("error_count", 0)),
                            GLib.Variant.new_array(
                                GLib.VariantType.new("s"),
                                list(map(
                                    GLib.Variant.new_string,
                                    progress.get("current_files", [])
                                ))
                            )
                        )
                    )
                    if sys.stdout.isatty():
                        if "seconds_remaining" not in progress and progress.get("percent_done", 0.0) < 1.0:
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
                    else:
                        if int(progress.get("percent_done", 0.0) * 1000) > progress_percentage_int and "seconds_remaining" in progress:
                            print(f"{progress['percent_done']: >5.1%}", end=" ", file=sys.stderr)
                            if "total_bytes" in progress:
                                print(f"{progress.get('bytes_done', 0) / (1024**3):5.2f}/{progress['total_bytes'] / (1024**3):5.2f}G uploaded", file=sys.stderr)
                    if int(progress.get("percent_done", 0.0) * 1000) > progress_percentage_int and "seconds_remaining" in progress:
                        progress_percentage_int = int(progress.get("percent_done", 0.0) * 1000)
                elif progress["message_type"] == "error":
                    dbus.emit_signal(
                        None,
                        "/com/nyantec/igotchuu",
                        "com.nyantec.igotchuu1",
                        "Error",
                        GLib.Variant.new_tuple(
                            GLib.Variant.new_string(progress["error"]),
                            GLib.Variant.new_string(progress["during"]),
                            GLib.Variant.new_string(progress["item"])
                        )
                    )
                    if sys.stdout.isatty():
                        print("")
                    print("Error during {} of {}: {}".format(
                        progress["during"], progress["item"], progress["error"]
                    ), file=sys.stderr)
                elif progress["message_type"] == "summary":
                    dbus.emit_signal(
                        None,
                        "/com/nyantec/igotchuu",
                        "com.nyantec.igotchuu1",
                        "BackupComplete",
                        GLib.Variant.new_tuple(
                            GLib.Variant.new_uint64(progress["files_new"]),
                            GLib.Variant.new_uint64(progress["files_changed"]),
                            GLib.Variant.new_uint64(progress["files_unmodified"]),
                            GLib.Variant.new_uint64(progress["dirs_new"]),
                            GLib.Variant.new_uint64(progress["dirs_changed"]),
                            GLib.Variant.new_uint64(progress["dirs_unmodified"]),
                            GLib.Variant.new_int64(progress["data_blobs"]),
                            GLib.Variant.new_int64(progress["tree_blobs"]),
                            GLib.Variant.new_uint64(progress["total_files_processed"]),
                            GLib.Variant.new_uint64(progress["total_bytes_processed"]),
                            GLib.Variant.new_double(float(progress["total_duration"])),
                            GLib.Variant.new_string(progress["snapshot_id"]),
                            GLib.Variant.new_boolean(progress.get("dry_run", False))
                        )
                    )
                    if sys.stdout.isatty():
                        print()
                    print("Backup complete. Stats:")
                    print(" - New files:         ", progress["files_new"])
                    print(" - Changed files:     ", progress["files_changed"])
                    print(" - Unmodified files:  ", progress["files_unmodified"])
                    print(" - New folders:       ", progress["dirs_new"])
                    print(" - Changed folders:   ", progress["dirs_changed"])
                    print(" - Unmodified folders:", progress["dirs_unmodified"])
                    print(" - Data blobs:        ", progress["data_blobs"])
                    print(" - Tree blobs:        ", progress["tree_blobs"])
                    print(" - Processed {} files of {} bytes".format(
                        progress["total_files_processed"],
                        progress["total_bytes_processed"]
                    ))
                    print(" - Snapshot ID:", progress["snapshot_id"])
                    if progress.get("dry_run", False):
                        print("(this was a dry run)")
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
