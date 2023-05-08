import datetime

import pytest

from tinyalert import api
from tinyalert.types import MeasureType


def test_push_with_all_fields(db):
    p = api.push(db, "measure", 1, absolute_max=2, absolute_min=3, relative_max=4, relative_min=5, measure_source="source", diffable_content="diff", url="test")
    assert p.metric_value == 1
    assert p.absolute_max == 2
    assert p.absolute_min == 3
    assert p.relative_max == 4
    assert p.relative_min == 5
    assert p.measure_source == "source"
    assert p.diffable_content == "diff"
    assert p.url == "test"


@pytest.mark.parametrize("source,method,expected", [("test.md", "file-lines", 1), ("test.md", "file-raw", 10), ("cat test.md", "exec-lines", 1), ("cat test.md", "exec-raw", 10)])
def test_measure(monkeypatch, tmp_path, source, method, expected):
    tmp_path.joinpath("test.md").write_text("10")
    monkeypatch.chdir(tmp_path)

    result = api.measure(source, MeasureType.model_validate(method))
    assert result.value == expected
    assert result.source == "10"


@pytest.mark.parametrize("source,method,expected", [("test.md", "file", "hello"), ("cat test.md", "exec", "hello")])
def test_eval_source(monkeypatch, tmp_path, source, method, expected):
    tmp_path.joinpath("test.md").write_text("hello")
    monkeypatch.chdir(tmp_path)

    assert api.eval_source(source, method) == expected


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


def test_prune_with_minimum_data(db):
    api.push(db, "errors", value=1)
    api.push(db, "errors", value=7)

    deleted = api.prune(db, 1)
    assert deleted == 1

    points = list(db.recent())

    assert len(points) == 1
    assert points[0].metric_value == 7


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
    )
    api.push(db, "warnings", value=10)

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
    assert points[1].metric_name == "errors"
    assert points[1].metric_value == 1
    assert points[1].absolute_max == 10
    assert points[1].absolute_min == 0
    assert points[1].relative_max == 2
    assert points[1].relative_min == 3
    assert points[1].measure_source == "content"
    assert points[1].diffable_content == "diff"
    assert points[1].url == "url"


def test_gather_report_data_when_no_data(db):
    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.latest_values == []
    assert data.latest_value is None
    assert data.previous_value is None
    assert data.absolute_max is None
    assert data.absolute_min is None
    assert data.relative_max is None
    assert data.relative_min is None
    assert data.latest_diffable_content is None
    assert data.previous_diffable_content is None
    assert data.url is None


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
    )
    api.push(db, "warnings", value=10)

    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.latest_values == [1]
    assert data.latest_value == 1
    assert data.previous_value is None
    assert data.absolute_max == 10
    assert data.absolute_min == 0
    assert data.relative_max == 2
    assert data.relative_min == 3
    assert data.latest_diffable_content == "content"
    assert data.previous_diffable_content is None
    assert data.url == "url"


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
    )
    api.push(db, "errors", value=2, diffable_content="latest", url="current_url")

    data = api.gather_report_data(db, "errors")

    assert data.metric_name == "errors"
    assert data.latest_values == [2.0, 1.0]
    assert data.latest_value == 2
    assert data.previous_value == 1
    assert data.absolute_max is None
    assert data.absolute_min is None
    assert data.relative_max is None
    assert data.relative_min is None
    assert data.latest_diffable_content == "latest"
    assert data.previous_diffable_content == "previous"
    assert data.url == "current_url"
