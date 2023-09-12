import json
from pathlib import Path
from typing import List

import pytest
import tomli_w
from click.testing import CliRunner

from tinyalert import api
from tinyalert.cli import cli
from tinyalert.types import MetricConfig


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
    recent_result = runner.invoke(cli, ["--db", db_path, "recent", "--json"])
    assert recent_result.exit_code == 0, recent_result

    return [json.loads(line) for line in recent_result.stdout.split("\n") if line]


# push


def test_push(runner, temp_dir):
    result = runner.invoke(
        cli,
        [
            "--db",
            "db.sqlite",
            "push",
            "errors",
            "--value",
            1,
            "--abs-max",
            2,
            "--abs-min",
            3,
            "--rel-max",
            4,
            "--rel-min",
            5,
            "--source",
            "source",
            "--diffable",
            "diffable",
            "--url",
            "url",
            "--epoch",
            "1",
            "--generation",
            "100",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout + "\n" + result.stderr

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
    assert recents[0]["epoch"] == 1
    assert recents[0]["generation"] == 100


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
                epoch=1,
            ),
        ]
    )
    temp_dir.joinpath("foo.txt").write_text("1\n2\n")
    temp_dir.joinpath("bar.txt").write_text("1\n2\n3")
    expected_epochs = {"foo": 0, "bar": 1}

    result = runner.invoke(
        cli,
        [
            "--db",
            "db.sqlite",
            "measure",
            "--metrics",
            metrics_to_measure,
            "-n",
            "100",
            "--config",
            config_path,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result

    recents = read_recents(runner, "db.sqlite")
    assert len(recents) == len(expected)
    assert set([p["metric_name"] for p in recents]) == set(expected.keys())
    for p in recents:
        assert p["metric_value"] == expected[p["metric_name"]]
        assert p["epoch"] == expected_epochs[p["metric_name"]]
        assert p["generation"] == 100


@pytest.mark.parametrize(
    "diffable_config,expected_content",
    [
        ({}, "foo"),
        ({"diffable_source": "bar.txt"}, "bar"),
        ({"measure_source_is_diffable": False}, None),
        ({"diffable_source": "bar.txt", "measure_source_is_diffable": False}, "bar"),
    ],
)
def test_measure_diffable_content(
    runner, temp_dir, write_config, diffable_config, expected_content
):
    config_path = write_config(
        [
            MetricConfig(
                name="foo",
                measure_source="foo.txt",
                measure_type="file-lines",
                **diffable_config,
            ),
        ]
    )
    temp_dir.joinpath("foo.txt").write_text("foo")
    temp_dir.joinpath("bar.txt").write_text("bar")

    result = runner.invoke(
        cli,
        [
            "--db",
            "db.sqlite",
            "measure",
            "--metrics",
            "foo",
            "--config",
            config_path,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result

    recents = read_recents(runner, "db.sqlite")
    assert len(recents) == 1
    assert recents[0]["diffable_content"] == expected_content


def test_measure_non_existent_metric(runner, temp_dir, write_config):
    config_path = write_config(
        [
            MetricConfig(name="foo", measure_source="grep -vc ^$ foo.txt"),
        ]
    )

    result = runner.invoke(
        cli,
        ["--db", "db.sqlite", "measure", "--metrics", "foo,bar", "--config", config_path],
        catch_exceptions=False,
    )
    assert result.exit_code == 1, result


# combine


def test_combine_works(runner, create_db):
    dest = create_db("combined.db")
    Path("src").mkdir(parents=True, exist_ok=True)
    src = create_db("src/coverage.db")
    api.push(dest, "errors", value=1)
    api.push(src, "coverage", value=4)

    result = runner.invoke(
        cli, ["--db", str(dest.db_path), "combine", "src/*.db"], catch_exceptions=False
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
        cli, ["--db", "db.sqlite", "combine", str(src.db_path), str(src2.db_path)]
    )
    assert result.exit_code == 0, result

    recents = read_recents(runner, "db.sqlite")
    assert [p["metric_value"] for p in recents] == [4, 1]


def test_recent_works(runner, db):
    api.push(db, "errors", value=1)
    api.push(db, "coverage", value=4)

    recent_result = runner.invoke(
        cli, ["--db", str(db.db_path), "recent", "--json"], catch_exceptions=False
    )
    assert recent_result.exit_code == 0, recent_result

    recents = [json.loads(line) for line in recent_result.stdout.split("\n") if line]

    assert len(recents) == 2
    assert recents[0]["metric_name"] == "coverage"
    assert recents[1]["metric_name"] == "errors"


# report


def test_report_returns_ok_when_empty_db(runner, db):
    json_result = runner.invoke(
        cli, ["--db", str(db.db_path), "report", "--format", "json"], catch_exceptions=False
    )
    assert json_result.exit_code == 0, json_result
    report = json.loads(json_result.stdout)
    assert report["table"]
    assert not report["list"]
    assert not report["diff"]
    assert report["status"] == "ok"


def test_report_exits_with_error_when_latest_value_violates_threshold(runner, db):
    api.push(db, "errors", value=10, absolute_max=0, diffable_content="foo")

    result = runner.invoke(cli, ["--db", str(db.db_path), "report"], catch_exceptions=False)

    assert result.exit_code == 1, result.stdout + "\n" + result.stderr

    json_result = runner.invoke(
        cli, ["--db", str(db.db_path), "report", "--format", "json"], catch_exceptions=False
    )

    assert json_result.exit_code == 1, json_result
    report = json.loads(json_result.stdout)
    assert report["table"]
    assert report["list"]
    assert report["diff"]
    assert report["status"] == "alarm"


def test_report_returns_ok_when_non_current_generation_violates_threshold(runner, db):
    api.push(db, "errors", value=10, absolute_max=0, diffable_content="foo", generation=1)

    result = runner.invoke(cli, ["--db", str(db.db_path), "report"], catch_exceptions=False)

    assert result.exit_code == 1, result.stdout + "\n" + result.stderr

    json_result = runner.invoke(
        cli, ["--db", str(db.db_path), "report", "--generation", "2", "--format", "json"], catch_exceptions=False
    )

    assert json_result.exit_code == 0, json_result
    report = json.loads(json_result.stdout)
    assert report["table"]
    assert not report["list"]
    assert not report["diff"]
    assert report["status"] == "ok"


def test_report_doesnt_alert_when_muted(runner, db):
    api.push(db, "errors", value=10, absolute_max=0)

    result = runner.invoke(
        cli, ["--db", str(db.db_path), "report", "--mute"], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output

    json_result = runner.invoke(
        cli,
        ["--db", str(db.db_path), "report", "--mute", "--format", "json"],
        catch_exceptions=False,
    )

    assert json_result.exit_code == 0, json_result
    report = json.loads(json_result.stdout)
    assert report["table"]
    assert report["list"]
    assert report["diff"] == ""
    assert report["status"] == "alarm_muted"


def test_report_with_previous_no_alert_skips_previous_value(runner, db):
    api.push(db, "errors", value=10, absolute_max=0)
    no_alert_result = runner.invoke(
        cli, ["--db", str(db.db_path), "report", "--mute"], catch_exceptions=False
    )
    assert no_alert_result.exit_code == 0, no_alert_result.output
    api.push(db, "errors", value=20, relative_max=0)

    result = runner.invoke(cli, ["--db", str(db.db_path), "report"], catch_exceptions=False)

    assert result.exit_code == 0, result.output + "\n" + result.output


def test_report_with_new_epoch_doesnt_alert(runner, db):
    api.push(db, "errors", value=10, absolute_max=0)
    api.push(db, "errors", value=20, relative_max=0, epoch=1)

    result = runner.invoke(cli, ["--db", str(db.db_path), "report"], catch_exceptions=False)

    assert result.exit_code == 0, result.output + "\n" + result.output


# prune


def test_prune_keeps_specified_number_of_points(runner, db):
    api.push(db, "errors", value=1)
    api.push(db, "errors", value=4)
    api.push(db, "coverage", value=7)

    result = runner.invoke(
        cli, ["--db", str(db.db_path), "prune", "--keep", 1], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output

    recents = list(db.recent())
    assert [(p.metric_name, p.metric_value) for p in recents] == [
        ("coverage", 7),
        ("errors", 4),
    ]


# migrate


def test_migrate_command(runner):
    result = runner.invoke(
        cli, ["--db", "db.sqlite", "migrate", "upgrade", "head"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output + result.stderr
