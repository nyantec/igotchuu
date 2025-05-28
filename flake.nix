{
  description = "Backup script wrapping Restic with btrfs snapshots and other goodies";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils }: {
    overlay = final: prev: {
      pythonPackagesExtensions = (prev.pythonPackagesExtensions or []) ++ [
        (final': prev': {
          python-unshare = final'.callPackage ./python-unshare.nix {};
        })
      ];
      igotchuu = final.callPackage ./default.nix {};
    };
    nixosModules.default = import ./configuration.nix self.overlay;
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
    devShells.default = pkgs.mkShell {
      inputsFrom = [ self.packages.${system}.default ];
      nativeBuildInputs = with pkgs; [ pyright ];
      PIP_DISABLE_PIP_VERSION_CHECK = "true";
    };
  }));
}
