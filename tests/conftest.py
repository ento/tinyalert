import pytest

from tinyalert.db import DB


@pytest.fixture
def create_db(tmp_path):
    def _create_db(filename: str):
        db = DB(tmp_path / filename)
        db.migrate()
        return db

    return _create_db


@pytest.fixture
def db(create_db):
    return create_db("tinyalert.db")
