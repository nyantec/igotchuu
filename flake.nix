{
  description = "Backup script wrapping Restic with btrfs snapshots and other goodies";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils }: {
    overlay = final: prev: {
      igotchuu = final.python311Packages.buildPythonApplication {
        name = "igotchuu";
        version = "0.1.0";

        src = final.poetry2nix.cleanPythonSources {
          src = ./.;
        };

        buildInputs = with final; [ gobject-introspection ];
        nativeBuildInputs = with final; [ wrapGAppsHook ];
        propagatedBuildInputs = with final.python311Packages; [
          pygobject3 btrfsutil
        ];

        # There are no tests for now
        doCheck = false;

        postInstall = ''
          install -Dm644 ./dbus-policy.conf $out/share/dbus-1/system.d/com.nyantec.IGotChuu.conf
        '';

        meta = with final.lib; {
          mainProgram = "igotchuu";
          homepage = "https://github.com/nyantec/igotchuu";
          description = "Backup script wrapping Restic with btrfs snapshots and other goodies";
          maintainers = with maintainers; [
            vikanezrimaya
          ];
          license = licenses.miros;
          platforms = platforms.linux;
        };
      };
    };
  } // (flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import nixpkgs {
      inherit system;
      overlays = [ self.overlay ];
    };
  in {
    packages = {
      igotchuu = pkgs.igotchuu;
      default = pkgs.igotchuu;
    };
  }));
}
