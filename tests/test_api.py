from datetime import timedelta
from pathlib import Path

import pytest
import tomli

from tinyalert import api
from tinyalert.cli_helpers import Duration
from tinyalert.types import GenerationMatchStatus, MeasureType


def test_push_with_all_fields(db):
    p = api.push(
        db,
        "measure",
        1,
        absolute_max=2,
        absolute_min=3,
        relative_max=4,
        relative_min=5,
        measure_source="source",
        diffable_content="diff",
        url="test",
        epoch=1,
        generation=100,
        tags={"foo": 1},
    )
    assert p.metric_value == 1
    assert p.absolute_max == 2
    assert p.absolute_min == 3
    assert p.relative_max == 4
    assert p.relative_min == 5
    assert p.measure_source == "source"
    assert p.diffable_content == "diff"
    assert p.url == "test"
    assert p.epoch == 1
    assert p.generation == 100
    assert p.tags == {"foo": 1}


@pytest.mark.parametrize(
    "source,method,expected",
    [
        ("test.md", "file-lines", 1),
        ("test.md", "file-raw", 10),
        ("cat test.md", "exec-lines", 1),
        ("cat test.md", "exec-raw", 10),
        ("cat test.md | cat", "shell-lines", 1),
        ("cat test.md | cat", "shell-raw", 10),
    ],
)
def test_measure(monkeypatch, tmp_path, source, method, expected):
    tmp_path.joinpath("test.md").write_text("10")
    monkeypatch.chdir(tmp_path)

    result = api.measure(source, MeasureType.model_validate(method))
    assert result.value == expected
    assert result.source == "10"


@pytest.mark.parametrize(
    "source,method,expected",
    [
        ("test.md", "file", "hello"),
        ("cat test.md", "exec", "hello"),
        ("cat test.md | cat", "shell", "hello"),
    ],
)
def test_eval_source(monkeypatch, tmp_path, source, method, expected):
    tmp_path.joinpath("test.md").write_text("hello")
    monkeypatch.chdir(tmp_path)

    assert api.eval_source(source, method) == expected


def test_skip_latest(db):
    api.push(db, "errors", value=1)
    api.push(db, "errors", value=7)
    api.push(db, "coverage", value=4)

    api.skip_latest(db, "errors")

    points = list(db.recent(count=3))

    assert len(points) == 3
    assert [p.metric_value for p in points] == [4, 7, 1]
    assert [p.skipped for p in points] == [False, True, False]


def test_combine_with_minimum_data(db, create_db, freezer):
    src = create_db("coverage.db")
    api.push(db, "errors", value=1)
    freezer.tick()
    api.push(src, "coverage", value=4)
    api.push(db, "errors", value=7)

    api.combine(db, [src])

    points = list(db.recent(count=3))

    assert len(points) == 3
    assert [p.metric_value for p in points] == [4, 7, 1]


def test_prune_with_empty_db(db):
    assert (
        api.prune(db, keep_last=0, keep_within=timedelta(seconds=0), keep_auto=True)
        == 0
    )
    assert (
        api.prune(db, keep_last=1, keep_within=timedelta(seconds=1), keep_auto=True)
        == 0
    )


@pytest.mark.parametrize(
    "fixture_path",
    list(Path(__file__).parent.joinpath("__fixtures__").glob("api_prune_*.toml")),
)
def test_prune_with_fixtures(db_from_csv, fixture_path):
    testcase = tomli.loads(fixture_path.read_text())
    db = db_from_csv(testcase["points"])

    kwargs = testcase.get("args", {})
    if "keep_within" in kwargs:
        kwargs["keep_within"] = Duration.from_string(kwargs["keep_within"])
    deleted = api.prune(db, **kwargs)
    points = list(db.recent())

    assert deleted == testcase["result"]["return_value"]
    assert [p.metric_value for p in points] == testcase["result"]["recent_values"]


def test_rename(db):
    api.push(db, "warnings", value=10, epoch=1)
    api.push(db, "warnings", value=10, epoch=2)
    api.push(db, "errors", value=10, epoch=1)
    api.push(db, "errors", value=10, epoch=2)

    count = api.rename(db, "warnings", "infos")

    assert count == 2

    assert len(list(db.recent("warnings", count=10))) == 0
    assert len(list(db.recent("errors", count=10))) == 2
    assert len(list(db.recent("infos", count=10))) == 2


def test_rename_no_points(db):
    api.push(db, "warnings", value=10, epoch=1)
    api.push(db, "warnings", value=10, epoch=2)

    count = api.rename(db, "errors", "infos")

    assert count == 0

    assert len(list(db.recent("warnings", count=10))) == 2
    assert len(list(db.recent("infos", count=10))) == 0


def test_rename_existing_points_with_same_destination_name(db):
    api.push(db, "warnings", value=10, epoch=1)
    api.push(db, "warnings", value=10, epoch=2)
    api.push(db, "errors", value=10, epoch=1)
    api.push(db, "errors", value=10, epoch=2)

    count = api.rename(db, "warnings", "errors")

    assert count == 2

    assert len(list(db.recent("warnings", count=10))) == 0
    assert len(list(db.recent("errors", count=10))) == 4


def test_recent(db):
    api.push(
        db,
        "errors",
        value=1,
        absolute_max=10,
        absolute_min=0,
        relative_max=2,
        relative_min=3,
        measure_source="content",
        diffable_content="diff",
        url="url",
        tags={"foo": "bar"},
    )
    api.push(db, "warnings", value=10, epoch=1)

    points = list(db.recent(count=1))

    assert len(points) == 1
    assert points[0].metric_name == "warnings"
    assert points[0].metric_value == 10
    assert points[0].absolute_max is None
    assert points[0].absolute_min is None
    assert points[0].relative_max is None
    assert points[0].relative_min is None
    assert points[0].measure_source is None
    assert points[0].diffable_content is None
    assert points[0].url is None
    assert points[0].epoch == 1
    assert points[0].tags == {}

    points = list(db.recent(count=3))

    assert len(points) == 2
    assert points[0].metric_name == "warnings"
    assert points[0].metric_value == 10
    assert points[0].absolute_max is None
    assert points[0].absolute_min is None
    assert points[0].relative_max is None
    assert points[0].relative_min is None
    assert points[0].measure_source is None
    assert points[0].diffable_content is None
    assert points[0].url is None
    assert points[0].epoch == 1
    assert points[0].tags == {}
    assert points[1].metric_name == "errors"
    assert points[1].metric_value == 1
    assert points[1].absolute_max == 10
    assert points[1].absolute_min == 0
    assert points[1].relative_max == 2
    assert points[1].relative_min == 3
    assert points[1].measure_source == "content"
    assert points[1].diffable_content == "diff"
    assert points[1].url == "url"
    assert points[1].epoch == 0
    assert points[1].tags == {"foo": "bar"}


def test_gather_report_data_when_no_data(db):
    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.generation_status == GenerationMatchStatus.NONE_SPECIFIED
    assert data.latest_values == []
    assert data.latest_value is None
    assert data.previous_value is None
    assert data.absolute_max is None
    assert data.absolute_min is None
    assert data.relative_max is None
    assert data.relative_min is None
    assert data.latest_diffable_content is None
    assert data.previous_diffable_content is None
    assert data.latest_url is None
    assert data.previous_url is None
    assert data.latest_tags is None
    assert data.previous_tags is None


def test_gather_report_data_when_single_point(db):
    api.push(
        db,
        "errors",
        value=1,
        absolute_max=10,
        absolute_min=0,
        relative_max=2,
        relative_min=3,
        diffable_content="content",
        url="url",
        tags={"foo": "bar"},
    )
    api.push(db, "warnings", value=10)

    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.generation_status == GenerationMatchStatus.NONE_SPECIFIED
    assert data.latest_values == [1]
    assert data.latest_value == 1
    assert data.previous_value is None
    assert data.absolute_max == 10
    assert data.absolute_min == 0
    assert data.relative_max == 2
    assert data.relative_min == 3
    assert data.latest_diffable_content == "content"
    assert data.previous_diffable_content is None
    assert data.latest_url == "url"
    assert data.previous_url is None
    assert data.latest_tags == {"foo": "bar"}
    assert data.previous_tags is None


def test_gather_report_data_when_two_points(db):
    api.push(
        db,
        "errors",
        value=1,
        absolute_max=10,
        absolute_min=0,
        relative_max=2,
        relative_min=3,
        diffable_content="previous",
        url="prev_url",
        tags={"foo": "bar"},
    )
    api.push(
        db,
        "errors",
        value=2,
        diffable_content="latest",
        url="current_url",
        tags={"foo": "baz"},
    )

    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.generation_status == GenerationMatchStatus.NONE_SPECIFIED
    assert data.latest_values == [1.0, 2.0]
    assert data.latest_value == 2
    assert data.previous_value == 1
    assert data.absolute_max is None
    assert data.absolute_min is None
    assert data.relative_max is None
    assert data.relative_min is None
    assert data.latest_diffable_content == "latest"
    assert data.previous_diffable_content == "previous"
    assert data.latest_url == "current_url"
    assert data.previous_url == "prev_url"
    assert data.latest_tags == {"foo": "baz"}
    assert data.previous_tags == {"foo": "bar"}


def test_gather_report_data_when_two_points_from_older_generation(db):
    api.push(
        db,
        "errors",
        value=1,
        absolute_max=10,
        absolute_min=0,
        relative_max=2,
        relative_min=3,
        diffable_content="previous",
        url="prev_url",
        tags={"foo": "bar"},
    )
    api.push(
        db,
        "errors",
        value=2,
        diffable_content="latest",
        url="current_url",
        tags={"foo": "baz"},
    )

    data = api.gather_report_data(db, "errors", head_generation=1)

    assert data.metric_name == "errors"
    assert data.generation_status == GenerationMatchStatus.NONE_MATCHED
    assert data.latest_values == [1.0, 2.0]
    assert data.latest_value == 2.0
    assert data.previous_value == 1.0
    assert data.absolute_max is None
    assert data.absolute_min is None
    assert data.relative_max is None
    assert data.relative_min is None
    assert data.latest_diffable_content == "latest"
    assert data.previous_diffable_content == "previous"
    assert data.latest_url == "current_url"
    assert data.previous_url == "prev_url"
    assert data.latest_tags == {"foo": "baz"}
    assert data.previous_tags == {"foo": "bar"}


def test_gather_report_data_dont_alert_on_skipped_data(db):
    api.push(db, "errors", value=1)
    api.skip_latest(db, "errors")
    api.push(db, "errors", value=2)
    api.push(db, "errors", value=3)
    api.skip_latest(db, "errors")
    api.push(db, "errors", value=4)
    api.skip_latest(db, "errors")

    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.generation_status == GenerationMatchStatus.NONE_SPECIFIED
    assert data.latest_values == [1.0, 2.0, 3.0, 4.0]
    assert data.latest_value == 4
    assert data.previous_value == 2


def test_gather_report_data_dont_alert_on_different_epoch(db):
    api.push(db, "errors", value=1)
    api.push(db, "errors", value=2, epoch=1)

    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.generation_status == GenerationMatchStatus.NONE_SPECIFIED
    assert data.latest_values == [1.0, 2.0]
    assert data.latest_value == 2
    assert data.previous_value is None
