{
  description = "Backup script wrapping Restic with btrfs snapshots and other goodies";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils }: {
    overlay = final: prev: {
      igotchuu = final.python310Packages.buildPythonApplication {
        name = "igotchuu";
        version = "0.1.0";

        src = final.poetry2nix.cleanPythonSources {
          src = ./.;
        };

        buildInputs = with final; [ gobject-introspection ];
        nativeBuildInputs = with final; [ wrapGAppsHook ];
        propagatedBuildInputs = with final.python310Packages; [
          pygobject3
        ];

        # There are no tests for now
        doCheck = false;

        postInstall = ''
          install -Dm644 ./dbus-policy.conf $out/share/dbus-1/system.d/com.nyantec.IGotChuu.conf
        '';

        meta = {
          mainProgram = "igotchuu";
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
