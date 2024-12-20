import datetime
import os
from csv import DictReader
from io import StringIO

import pytest
from syrupy import PyTestLocation
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.amber import AmberSnapshotExtension

from tinyalert import api
from tinyalert.db import DB

ENV_VAR = "PANTS_WITH_SNAPSHOTS_HACK_DIR"


class EscapePantsSandboxExtension(AmberSnapshotExtension):
    """Point syrupy to the original files outside pants' sandbox

    FIXME https://github.com/pantsbuild/pants/issues/11622:

    Pants runs tests in a 'sandboxed' temporary directory, so edits to the
    snapshot file aren't persistent. This works around via an orchestration
    script that copies the snapshots to a temporary directory, editing paths
    to have syrupy be reading/writing those files, and then copies back
    (see scripts/pants-with-snapshot-sandbox.sh).
    """

    @classmethod
    def dirname(cls, *, test_location: PyTestLocation) -> str:
        # Changes here should also be applied to any other extensions
        # (search for imports/uses of 'syrupy.extensions')

        # /tmp/whatever/tests/something/__snapshots__
        original = super().dirname(test_location=test_location)

        # duplicated root directory, set from original invocation via pants.toml
        # and scripts/pants-with-snapshot-sandbox.sh
        snapshot_hack_dir = os.environ[ENV_VAR]

        # find just the /tests/... part
        tests_index = original.index("/tests/")
        # mash 'em together to get the path that'll be copied back to the repo
        # after the test run
        return f"{snapshot_hack_dir}{original[tests_index:]}"


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    if os.environ.get(ENV_VAR) is None:
        # pytest without the snapshot hack
        return snapshot

    # updating snapshots requires looking outside the sandbox
    return snapshot.use_extension(EscapePantsSandboxExtension)


@pytest.fixture
def create_db(tmp_path):
    def _create_db(filename: str):
        db = DB(tmp_path / filename, verbose=True)
        db.migrate()
        return db

    return _create_db


@pytest.fixture
def db(create_db):
    return create_db("metrics/tinyalert.db")


@pytest.fixture
def db_from_csv(freezer, create_db):
    def inner(csv_content: str) -> DB:
        db = create_db("metrics/tinyalert.db")
        io = StringIO(csv_content.strip())
        reader = DictReader(io, skipinitialspace=True)
        for row in reader:
            api.push(db, **row)
            freezer.tick(delta=datetime.timedelta(days=1))
        return db

    return inner
