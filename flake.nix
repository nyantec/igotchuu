{
  description = "Backup script wrapping Restic with btrfs snapshots and other goodies";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }: {
    overlay = nixpkgs.lib.composeManyExtensions [
      #poetry2nix.overlay
      (final: prev: {
        /*igotchuu = final.poetry2nix.mkPoetryApplication {
          projectDir = ./.;

          buildInputs = with final; [ gobject-introspection ];
          nativeBuildInputs = with final; [ wrapGAppsHook ];
          overrides = final.poetry2nix.overrides.withDefaults (pyfinal: pyprev: {
            inherit (prev.python310Packages) pycairo;
          });

          meta = {
            mainProgram = "igotchuu";
          };
        };*/
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

          postInstall = ''
            install -Dm644 ./dbus-policy.conf $out/share/dbus-1/system.d/com.nyantec.IGotChuu.conf
          '';

          meta = {
            mainProgram = "igotchuu";
          };
        };
      })
    ];
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
    devShells.default = let
      poetry-env = pkgs.poetry2nix.mkPoetryEnv {
        projectDir = ./.;
        editablePackageSources = {
          igotchuu = ./.;
        };
      };
    in poetry-env.env.overrideAttrs (old: {
      nativeBuildInputs = (old.nativeBuildInputs or []) ++ (with pkgs; [
        poetry
      ]);
      buildInputs = with pkgs; [ gobject-introspection ];
    });
  }));
}
