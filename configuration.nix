# Copyright © 2023 nyantec GmbH <oss@nyantec.com>
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
overlay:
{ config, pkgs, lib, utils, ... }:
with lib;
let
  cfg = config.services.igotchuu;
  inherit (utils.systemdUtils.unitOptions) unitOption;
  settingsFormat = pkgs.formats.toml {};
  snapshotType = types.submodule {
    options = {
      source = lib.mkOption {
        type = types.str;
        description = ''
          Source btrfs subvolume to snapshot. Must be an absolute path.
        '';
        example = "/var";
      };
      snapshot_location = lib.mkOption {
        type = types.str;
        description = ''
          Location where the snapshot will be placed, including the name.

          A timestamp will be affixed to the name.
        '';
        example = "/mnt/snapshots/var";
      };
    };
  };
in {
  options = {
    services.igotchuu = {
      enable = mkEnableOption "igotchuu, a backup tool based on restic with support for btrfs snapshots";

      package = mkPackageOption pkgs "igotchuu" {};

      settings = mkOption {
        description = "igotchuu settings.";
        type = types.submodule {
          freeformType = settingsFormat.type;

          options = {
            exec_before_snapshot = lib.mkOption {
              type = types.nullOr (types.listOf types.str);
              default = null;
              description = ''
                A program to execute in a mount namespace right before
                snapshotting.

                This might be useful to deal with complex hierarchies, like
                backing up btrfs subvolumes mounted to a different rootfs -- in
                which case one will need to mount the btrfs root subvolume
                somewhere first. (In this particular case, setting
                `snapshot_prefix` may also prove useful)
              '';
            };
            places = lib.mkOption {
              type = types.listOf types.str;
              default = ["/home"];
              example = ["/home" "/var/lib"];
              description = ''
                Places to backup (and snapshot if `snapshot` is unset).
              '';
            };
            restic_backup_args = lib.mkOption {
              type = types.listOf types.str;
              default = ["-x" "--exclude-caches"];
              example = [
                "-x" "--exclude-caches"
                "--exclude-file=/root/exclude.txt"
              ];
              description = ''
                Options to pass to the `restic backup` invocation.
              '';
            };
            restic_args = lib.mkOption {
              type = types.listOf types.str;
              default = [];
              example = [
                "--repo=sftp://rsync.net/restic-backups"
                "--password-file=/root/restic-password"
              ];
              description = ''
                Options to pass to all restic commands.
              '';
            };
            snapshot_prefix = lib.mkOption {
              type = types.str;
              default = "";
              description = "Path to prefix to submodule snapshots.";
              example = "/mnt/btrfs-root/snapshots/";
            };
            snapshot = lib.mkOption {
              type = types.nullOr (types.listOf (types.oneOf [types.str snapshotType]));
              default = null;
              example = [
                "/home/user"
                { source = "/var"; snapshot_location = "/mnt/var"; }
              ];
              description = ''
                List of subvolumes to snapshot, in case it should be different
                from `places`.

                (e.g. not all `places` may be on a `btrfs` filesystem, or mounted
                to one)
              '';
            };
          };
        };
      };
      timerConfig = mkOption {
        type = types.attrsOf unitOption;
        default = {
          OnCalendar = "daily";
        };
        description = ''
          When to run the backup. See {manpage}`systemd.timer(5)` for details.
        '';
        example = {
          OnCalendar = "00:05";
          RandomizedDelaySec = "5h";
        };
      };
    };
  };
  config = mkMerge [
    {
      nixpkgs.overlays = [ overlay ];
    }
    (mkIf cfg.enable {
      environment.etc."igotchuu.toml".source = settingsFormat.generate "igotchuu.toml" (filterAttrs (k: v: v != null) cfg.settings);

      systemd.services.igotchuu = {
        description = "a backup tool based on restic with btrfs snapshots support";
        path = [ cfg.package pkgs.restic pkgs.openssh ];

        wants = [ "network-online.target" ];
        after = [ "network-online.target" ];

        environment = { XDG_CACHE_HOME = "/root/.cache"; };

        serviceConfig = {
          ExecStart = "${cfg.package}/bin/igotchuu backup";
        };
      };
      systemd.timers.igotchuu = {
        description = config.systemd.services.igotchuu.description;
        timerConfig = cfg.timerConfig;

        wantedBy = [ "timers.target" ];
      };

      services.dbus.packages = [ cfg.package ];
      environment.systemPackages = [ cfg.package pkgs.restic ];
    })
  ];
}
