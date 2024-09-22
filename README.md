## Development

Running tests

```sh
./scripts/pants-with-snapshot-sandbox.sh test ::
```

Creating an alembic revision

```sh
cd src/tinyalert
tinyalert migrate upgrade head
tinyalert migrate revision --autogenerate -m "Description"
```

Packaging

```sh
./pants package ::
```

Building Docker image locally

```sh
echo CACHIX_AUTH_TOKEN=[..] >> .env
echo CACHIX_CACHE_NAME=tinyalert >> .env
./scripts/local-build.sh
```
