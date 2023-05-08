import json
from typing import List

import pytest
import tomli_w
from click.testing import CliRunner

from tinyalert import api
from tinyalert.cli import cli
from tinyalert.types import Config, MetricConfig


@pytest.fixture
def runner():
    return CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def temp_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def write_config(temp_dir):
    def _write_config(metrics: List[MetricConfig]):
        config_path = temp_dir.joinpath("tinyalert.toml")
        config_path.write_text(
            tomli_w.dumps(
                {
                    "metrics": {
                        m.name: m.model_dump(exclude=["name"], exclude_none=True)
                        for m in metrics
                    }
                }
            )
        )
        return config_path

    return _write_config


def read_recents(runner, db_path):
    recent_result = runner.invoke(cli, [db_path, "recent", "--json"])
    assert recent_result.exit_code == 0, result

    return [json.loads(line) for line in recent_result.stdout.split("\n") if line]


# push


def test_push(runner, temp_dir):
    result = runner.invoke(
        cli,
        [
            "db.sqlite",
            "push",
            "errors",
            "--value", 1,
            "--abs-max", 2,
            "--abs-min", 3,
            "--rel-max", 4,
            "--rel-min", 5,
            "--source", "source",
            "--diffable","diffable",
            "--url", "url",
            "--ignore", "rel",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result

    recents = read_recents(runner, "db.sqlite")
    assert recents[0]["metric_name"] == "errors"
    assert recents[0]["metric_value"] == 1
    assert recents[0]["absolute_max"] == 2
    assert recents[0]["absolute_min"] == 3
    assert recents[0]["relative_max"] == 4
    assert recents[0]["relative_min"] == 5
    assert recents[0]["measure_source"] == "source"
    assert recents[0]["diffable_content"] == "diffable"
    assert recents[0]["url"] == "url"
    assert recents[0]["ignore"] == "rel"


# measure


@pytest.mark.parametrize(
    "metrics_to_measure,expected",
    [("foo", {"foo": 2}), ("foo, bar", {"foo": 2, "bar": 3})],
)
def test_measure(runner, temp_dir, write_config, metrics_to_measure, expected):
    config_path = write_config(
        [
            MetricConfig(
                name="foo",
                measure_source="grep -vc ^$ foo.txt",
                measure_type="exec-raw",
            ),
            MetricConfig(
                name="bar",
                measure_source="grep -vc ^$ bar.txt",
                measure_type="exec-raw",
            ),
        ]
    )
    temp_dir.joinpath("foo.txt").write_text("1\n2\n")
    temp_dir.joinpath("bar.txt").write_text("1\n2\n3")

    result = runner.invoke(
        cli,
        ["db.sqlite", "measure", "--metrics", metrics_to_measure, "--config", config_path],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result

    recents = read_recents(runner, "db.sqlite")
    assert len(recents) == len(expected)
    assert set([p["metric_name"] for p in recents]) == set(expected.keys())
    for p in recents:
        assert p["metric_value"] == expected[p["metric_name"]]


def test_measure_non_existent_metric(runner, temp_dir, write_config):
    config_path = write_config(
        [
            MetricConfig(name="foo", measure_source="grep -vc ^$ foo.txt"),
        ]
    )

    result = runner.invoke(
        cli,
        ["db.sqlite", "measure", "--metrics", "foo,bar", "--config", config_path],
        catch_exceptions=False,
    )
    assert result.exit_code == 1, result


# combine


def test_combine_works(runner, create_db):
    dest = create_db("combined.db")
    src = create_db("coverage.db")
    api.push(dest, "errors", value=1)
    api.push(src, "coverage", value=4)

    result = runner.invoke(
        cli, [str(dest.db_path), "combine", str(src.db_path)], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output

    recents = list(dest.recent())
    assert [p.metric_value for p in recents] == [4, 1]


def test_combine_works_against_empty_db(runner, create_db):
    src = create_db("errors.db")
    src2 = create_db("coverage.db")
    api.push(src, "errors", value=1)
    api.push(src2, "coverage", value=4)

    result = runner.invoke(
        cli, ["db.sqlite", "combine", str(src.db_path), str(src2.db_path)]
    )
    assert result.exit_code == 0, result

    recents = read_recents(runner, "db.sqlite")
    assert [p["metric_value"] for p in recents] == [4, 1]


def test_recent_works(runner, db):
    api.push(db, "errors", value=1)
    api.push(db, "coverage", value=4)

    recent_result = runner.invoke(
        cli, [str(db.db_path), "recent", "--json"], catch_exceptions=False
    )
    assert recent_result.exit_code == 0, recent_result

    recents = [json.loads(line) for line in recent_result.stdout.split("\n") if line]

    assert len(recents) == 2
    assert recents[0]["metric_name"] == "coverage"
    assert recents[1]["metric_name"] == "errors"


# report


def test_report_exits_with_error_when_latest_value_violates_threshold(runner, db):
    api.push(db, "errors", value=10, absolute_max=0)

    result = runner.invoke(cli, [str(db.db_path), "report"], catch_exceptions=False)

    assert result.exit_code == 1, result


def test_report_can_skip_latest_value(runner, db):
    # TODO: test the same with measure
    push_result = runner.invoke(
        cli,
        [
            str(db.db_path),
            "push",
            "errors",
            "--value",
            "10",
            "--abs-max",
            0,
            "--ignore",
            "all",
        ],
        catch_exceptions=False,
    )
    assert push_result.exit_code == 0, push_result

    result = runner.invoke(cli, [str(db.db_path), "report"], catch_exceptions=False)

    assert result.exit_code == 0, result.output


# prune


def test_prune_keeps_specified_number_of_points(runner, db):
    api.push(db, "errors", value=1)
    api.push(db, "errors", value=4)
    api.push(db, "coverage", value=7)

    result = runner.invoke(
        cli, [str(db.db_path), "prune", "--keep", 1], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output

    recents = list(db.recent())
    assert [(p.metric_name, p.metric_value) for p in recents] == [("coverage", 7), ("errors", 4)]


# migrate


def test_migrate_command(runner):
    result = runner.invoke(
        cli, ["db.sqlite", "migrate", "upgrade", "head"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
