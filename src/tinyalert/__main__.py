from .cli import cli


def main():
    cli(auto_envvar_prefix="TINYALERT")


if __name__ == "__main__":
    main()
