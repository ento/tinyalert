# To use this file, install Nix: https://nixos.org/download.html#download-nix
# and enable flakes: https://nixos.wiki/wiki/Flakes#Enable_flakes
# Then install direnv: https://direnv.net/
{
  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem
      (system: let
        pkgs = import nixpkgs {
          inherit system;
        };
        buildInputs = [
          pkgs.act
          pkgs.nodejs
          pkgs.poetry
          pkgs.sqlite
          pkgs.python38
        ];
        app = pkgs.poetry2nix.mkPoetryApplication {
          projectDir = ./.;
          overrides = pkgs.poetry2nix.overrides.withDefaults (self: super: {
            annotated-types = super.annotated-types.overridePythonAttrs (old: {
              buildInputs = (old.nativeBuildInputs or [ ]) ++ [ self.hatchling ];
            });
            pydantic = super.pydantic.overridePythonAttrs (old: {
              buildInputs = (old.nativeBuildInputs or [ ]) ++ [ self.hatchling self.hatch-fancy-pypi-readme ];
            });
            pydantic-core = super.pydantic-core.overridePythonAttrs (old: {
              cargoDeps = pkgs.rustPlatform.fetchCargoTarball {
                inherit (old) src;
                name = "${old.pname}-${old.version}";
                hash = "sha256-QIEdSTCkb94PrJ6UIHYp19knCPAW3iHBQmI1An7FzlA=";
              };
              nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ pkgs.rustPlatform.cargoSetupHook pkgs.rustPlatform.maturinBuildHook ];
            });
          });
        };
      in {
        devShells.default = pkgs.mkShell {
          inherit buildInputs;
        };
        packages.tinyalert = app;
        defaultPackage = app;
      });
}
