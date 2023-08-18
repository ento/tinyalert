## Development

Running tests

```sh
./scripts/pants-with-snapshot-sandbox.sh test ::
```

Creating an alembic revision

```sh
cd src/tinyalert
tinyalert db.sqlite migrate revision --autogenerate -m "Description"
```

Packaging

```sh
./pants package ::
```
