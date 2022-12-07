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
