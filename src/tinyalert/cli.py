import json
import sys
from pathlib import Path
from typing import List, Optional

import click
import tomli

from . import api, db
from .reporters import DiffReporter, ListReporter, StatusReporter, TableReporter
from .types import Config


@click.group()
@click.argument("db_path", type=click.Path(exists=False), envvar="TINYALERT_DB")
@click.pass_context
def cli(ctx, db_path):
    ctx.obj = db.DB(db_path)
    ctx.obj.migrate()


@cli.command()
@click.argument("metric_name")
@click.option("--value", default=None, type=float, help="Measurement value")
@click.option("--abs-max", default=None, type=float, help="Absolute max (inclusive)")
@click.option("--abs-min", default=None, type=float, help="Absolute min (inclusive)")
@click.option("--rel-max", default=None, type=float, help="Relative max (inclusive)")
@click.option("--rel-min", default=None, type=float, help="Relative min (inclusive)")
@click.option("--source", default=None, help="Raw content of the measured thing")
@click.option(
    "--diffable", default=None, help="Text content suitable for showing diffs"
)
@click.option("--url", default=None, help="URL")
@click.pass_context
def push(
    ctx,
    metric_name,
    value,
    abs_max,
    abs_min,
    rel_max,
    rel_min,
    source,
    diffable,
    url,
):
    if value is None:
        value = float(sys.stdin.read().strip())

    if not value:
        click.echo("No value provided")
        ctx.exit(1)

    api.push(
        db=ctx.obj,
        metric_name=metric_name,
        value=value,
        absolute_max=abs_max,
        absolute_min=abs_min,
        relative_max=rel_max,
        relative_min=rel_min,
        measure_source=source,
        diffable_content=diffable,
        url=url,
    )


def split_values(ctx, param, value):
    if not value:
        return None
    return [v.strip() for v in value.split(",")]


@cli.command()
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default="tinyalert.toml",
)
@click.option(
    "--metrics",
    default=None,
    callback=split_values,
    help="Comma-separated names of metrics to measure",
)
@click.option("--url", default=None, help="URL")
@click.pass_context
def measure(
    ctx: click.Context,
    config_path: Path,
    metrics: Optional[List[str]],
    url: Optional[str],
):
    raw = tomli.loads(Path(config_path).read_text())
    config = Config.model_validate(raw)
    metric_configs_by_name = {metric.name: metric for metric in config.metrics}
    if metrics and set(metrics) - set(metric_configs_by_name.keys()):
        click.echo(
            "Unknown metrics: {}".format(
                ", ".join(set(metrics) - set(metric_configs_by_name.keys()))
            ),
            err=True,
        )
        ctx.exit(1)
    metrics_to_measure = metric_configs_by_name.keys() if metrics is None else metrics
    for metric_name in metrics_to_measure:
        metric = metric_configs_by_name[metric_name]
        result = api.measure(metric.measure_source, metric.measure_type)
        diffable_content = None
        if metric.diffable_source:
            diffable_content = api.eval_source(
                metric.diffable_source, metric.diffable_type
            )
        api.push(
            ctx.obj,
            metric.name,
            value=result.value,
            absolute_max=metric.absolute_max,
            absolute_min=metric.absolute_min,
            relative_max=metric.relative_max,
            relative_min=metric.relative_min,
            measure_source=result.source,
            diffable_content=diffable_content,
            url=url,
        )


@cli.command()
@click.argument("src_db_pattern", nargs=-1)
@click.pass_context
def combine(ctx, src_db_pattern):
    src_dbs = [
        db.DB(path)
        for pattern in src_db_pattern
        for path in ([pattern] if Path(pattern).is_absolute() else Path().glob(pattern))
    ]
    api.combine(ctx.obj, src_dbs)


@cli.command()
@click.option("--json", "output_format", flag_value="json")
@click.pass_context
def recent(ctx, output_format):
    for p in api.recent(ctx.obj):
        if output_format == "json":
            print(p.model_dump_json())
        else:
            print("{time} {metric_name} {metric_value}".format(**p.dict()))


@cli.command()
@click.option("--format", "output_format", default=None)
@click.option(
    "--no-alert",
    is_flag=True,
    default=False,
    help="Don't exit with an error. Mark latest data points as skipped if they violate a threshold.",
)
@click.pass_context
def report(ctx, output_format, no_alert):
    reports = []
    list_reporter = ListReporter()
    table_reporter = TableReporter()
    diff_reporter = DiffReporter()
    status_reporter = StatusReporter()

    for metric_name in ctx.obj.iter_metric_names():
        report_data = api.gather_report_data(ctx.obj, metric_name)
        if no_alert and report_data.violates_limits:
            api.skip_latest(ctx.obj, metric_name)
        reports.append(report_data)
        table_reporter.add(report_data)
        list_reporter.add(report_data)
        diff_reporter.add(report_data)
        status_reporter.add(report_data)

    if output_format == "json":
        output = {
            "reports": [report.model_dump(mode="json") for report in reports],
            "table": table_reporter.get_value(),
            "list": list_reporter.get_value(),
            "diff": diff_reporter.get_value(),
        }
        print(json.dumps(output, indent=2))
    else:
        print(table_reporter.get_value())
        print("")
        print(list_reporter.get_value())
        print("")
        print(diff_reporter.get_value())
    if not status_reporter.get_value() and not no_alert:
        ctx.exit(1)


@cli.command()
@click.option("--keep", type=int, required=True, help="How many points to keep")
@click.pass_context
def prune(ctx, keep):
    count = api.prune(ctx.obj, keep=keep)
    click.echo(f"Pruned {count} points in total", err=True)


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.option("--help", is_flag=True)
@click.argument("alembic_args", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def migrate(ctx, alembic_args, help):
    args = list(alembic_args) + (["--help"] if help else [])
    ctx.obj.run_alembic(*args)
