# igotchuu

## Installation
This software requires a D-Bus policy file installed, to claim a name
on the bus. Please refer to your distribution's documentation on how
to properly install D-Bus policies.

### On NixOS
Assuming `igotchuu` is a flake reference to this repository:

```nix
{ config, pkgs, lib, ... }: {
  environment.systemPackages = [
    igotchuu.packages.${config.nixpkgs.localSystem.system}.default
  ];
  
  services.dbus.packages = [
    igotchuu.packages.${config.nixpkgs.localSystem.system}.default
  ];
}
```

## Usage
This software makes several assumptions about your system
installation, particularly the filesystem organization:

1. `/` is a Btrfs filesystem/subvolume
2. `/home` is a Btrfs subvolume on the same filesystem as `/`

The algorithm of this script is as follows:

1. `unshare` the mount namespace
2. Create a btrfs snapshot of `/home`
3. Bind-mount `/home-<snapshot date>` to `/home`
4. Run `restic` on `/home`

## Config file
The config file is a TOML file. Example:

```toml
# Executes a command before creating snapshots.
# This is useful if your / is on a tmpfs, and stateful data is on btrfs,
# and you need to mount your subvolume somewhere to create snapshots.
exec_before_snapshot = ["mount", "/dev/mapper/root", "/mnt", "-o", "subvol=5"]
# Prepends a prefix to all snapshot paths. This is useful if you want your
snapshots to be contained elsewhere. This must not have a trailing slash.
snapshot_prefix = "/mnt/snapshots"
# Places you want to back up.
places = ["/home", "/var/lib"]

# Arguments that will be passed to Restic.
#
# `--one-file-system` is heavily recommended due to how igotchuu works with
# subvolumes. In theory, if you need to back up a tree composed of several
# filesystems, you should be able to list them all in `places` so they will
# also be snapshotted.
restic_args = [
	"--one-file-system", "--exclude-caches",
	"--exclude-file=/etc/igotchuu/exclude.txt"
]
# Snapshots that will be created and bind-mounted over your root hierarchy.
# If not set, defaults to the value of `places`.
#
# Snapshotting all backup locations is heavily recommended to ensure
# consistency of backups. It is surprising that restic only includes this
# functionality on Windows.
#
# Note that the paths in `source` must be absolute.
#
# Creates a snapshot with the same name and a timestamp appended.
[[snapshot]]
source = "/home"
# Creates a snapshot with a different name (and a timestamp).
# This is useful sometimes.
[[snapshot]]
source = "/var/lib"
# Override the location for the snapshot. `snapshot_prefix` will not be used.
# However, a timestamp will still be appended to the snapshot name.
snapshot_location = "/var-lib"

```

## D-Bus interface
This software can be controlled via D-Bus, to receive progress updates
and stop an ongoing backup.

```xml
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN" "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">

<node name="/com/nyantec/igotchuu">
    <interface name="com.nyantec.igotchuu1">
        <method name="Stop"></method>

        <signal name="Error"></signal>

        <signal name="BackupStarted"></signal>

        <signal name="Progress">
            <arg name="json_data" type="s"/>
        </signal>

        <signal name="BackupComplete"></signal>
    </interface>
</node>
```

## TODOs
 - [ ] Make restic invocation arguments configurable
 - [ ] Consider using `btrfsutil` Python package instead of shelling out
 - [ ] Consider abstracting filesystem snapshotting and preparation
   - [ ] Handle cases where `/` is a `tmpfs` and `/home` is a btrfs subvolume
   - [ ] Handle ZFS subvolumes
   - [ ] Consider allowing running a subprocess to prepare the filesystem
 - [ ] Make signals carry typed data instead of JSON strings
 - [ ] Consider running as a daemon, to allow for triggering on-demand backups
 - [ ] Consider providing an example systemd service configuration
