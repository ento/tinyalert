{ pkgs, lib, config, inputs, self, ... }:

{
  name = "tinyalert";

  # https://devenv.sh/packages/
  packages = lib.optionals (!config.container.isBuilding) [
    pkgs.act
    pkgs.nodejs
    pkgs.sqlite-interactive
  ];

  languages.python.enable = true;
  languages.python.package = pkgs.python310;
  languages.python.poetry.enable = true;
  languages.python.poetry.activate.enable = true;
  languages.python.poetry.install.enable = !config.container.isBuilding;


  #
  ## https://devenv.sh/tests/
  #enterTest = ''
  #  pytest
  #'';
  #
  #pre-commit.hooks.ruff.enable = true;
  #pre-commit.hooks.ruff-format.enable = true;
  #pre-commit.hooks.pyright.enable = true;
  #
  processes.main.exec = "poetry run tinyalert";
  #
  containers."main".name = "tinyalert";
  containers."main".isDev = false;
  containers."main".startupCommand = "--help";
  containers."main".entrypoint = let
    cfg = config.languages.python;
    bash = "${pkgs.bash}/bin/bash";
    entrypoint = pkgs.writeScript "entrypoint" ''
      #!${bash}

      ${cfg.poetry.package}/bin/poetry -C /app install --only-root
      ${cfg.poetry.package}/bin/poetry -C /app run tinyalert "''${@}"
    '';
  in [ entrypoint ];
  containers."main".copyToRoot =
    let
      cfg = config.languages.python;
      homeDir = "/app";
      nix2container = inputs.nix2container.packages.${pkgs.stdenv.system};
      app = pkgs.stdenv.mkDerivation {
        name = "build-poetry-deps";
        src = self;
        buildPhase = ''
          export XDG_CONFIG_HOME=$TMPDIR/.config
          set -x
          ls -ld .
          ls -l
          ${cfg.poetry.package}/bin/poetry config virtualenvs.in-project true --local
          ${cfg.poetry.package}/bin/poetry config virtualenvs.create true --local
          ${cfg.poetry.package}/bin/poetry config cache-dir $TMPDIR/.cache --local
          ${cfg.poetry.package}/bin/poetry install --only main --no-root --no-directory --no-interaction --compile
        '';
        installPhase = ''
          mkdir -p $out/tmp
          mkdir -p $out${homeDir}
          cp -R ./. $out${homeDir}/
        '';
      };
    in (nix2container.nix2container.buildLayer {
      copyToRoot = app;
    });
  #containers.shell.verifyTrace = true;
}
