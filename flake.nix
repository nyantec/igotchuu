{
  description = "Backup script wrapping Restic with btrfs snapshots and other goodies";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }: {
    overlay = nixpkgs.lib.composeManyExtensions [
      poetry2nix.overlay
      (final: prev: {
        igotchuu = final.poetry2nix.mkPoetryApplication {
          projectDir = ./.;

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
    });
  }));
}
