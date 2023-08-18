# To use this file, install Nix: https://nixos.org/download.html#download-nix
# and enable flakes: https://nixos.wiki/wiki/Flakes#Enable_flakes
# Then install direnv: https://direnv.net/
{
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem
      (system: let
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication overrides;
        pkgs = nixpkgs.legacyPackages.${system};
        defaultPython = pkgs.python310;
        packages = [
          pkgs.act
          pkgs.nodejs
          pkgs.poetry
          pkgs.sqlite
          defaultPython
        ];
        app = mkPoetryApplication {
          projectDir = ./.;
          overrides = overrides.withDefaults (self: super: {
            pytest-freezer = super.pytest-freezer.overridePythonAttrs (old: {
              buildInputs = (old.nativeBuildInputs or [ ]) ++ [ self.hatchling ];
            });
            syrupy = super.syrupy.overridePythonAttrs (old: {
              buildInputs = (old.nativeBuildInputs or [ ]) ++ [ self.poetry ];
            });
          });
        };
      in {
        devShells.default = pkgs.mkShell {
          inherit packages;
          shellHook = ''
            export PYTHON_SEARCH_PATH=${defaultPython}/bin
          '';
        };
        packages.tinyalert = app;
        packages.default = self.packages.${system}.tinyalert;
      });
}
