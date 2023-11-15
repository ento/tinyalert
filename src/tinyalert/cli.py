import json
import sys
from pathlib import Path
from typing import Any, List, Optional

import click
import tomli

from . import api, db
from .cli_helpers import Duration
from .reporters import DiffReporter, ListReporter, StatusReporter, TableReporter
from .types import Config

ENVVAR_PREFIX = "TINYALERT_"


class JSONType(click.ParamType):
    name = "json"

    def convert(self, value, param, ctx):
        return json.loads(value)


@click.group()
@click.option(
    "--db",
    "db_path",
    required=True,
    default="tinyalert.sqlite",
    type=click.Path(exists=False),
    show_default=True,
)
@click.pass_context
def cli(ctx, db_path):
    ctx.obj = db.DB(db_path)


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
@click.option("--url", default=None, help="URL", envvar=ENVVAR_PREFIX + "URL")
@click.option(
    "--epoch",
    type=int,
    default=0,
    help="Epoch number",
    envvar=ENVVAR_PREFIX + "EPOCH",
    show_default=True,
)
@click.option(
    "-n",
    "--generation",
    type=int,
    default=0,
    help="Generation number",
    envvar=ENVVAR_PREFIX + "GENERATION",
    show_default=True,
)
@click.option(
    "--tag",
    "tags",
    type=(str, str),
    multiple=True,
    help="Key-value pair to store as a tag. Value is stored as a string",
    envvar=ENVVAR_PREFIX + "TAGS",
)
@click.option(
    "--tagjson",
    "json_tags",
    type=(str, JSONType()),
    multiple=True,
    help="Key-value pair to store as a tag. Value is evaluated as JSON",
    envvar=ENVVAR_PREFIX + "JSON_TAGS",
)
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
    epoch,
    generation,
    tags,
    json_tags,
):
    if value is None:
        value = float(sys.stdin.read().strip())

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
        epoch=epoch,
        generation=generation,
        tags=dict(tags + json_tags),
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
    show_default=True,
)
@click.option(
    "--metrics",
    default=None,
    callback=split_values,
    help="Comma-separated names of metrics to measure",
)
@click.option(
    "-n",
    "--generation",
    type=int,
    default=0,
    help="Generation number",
    envvar=ENVVAR_PREFIX + "GENERATION",
    show_default=True,
)
@click.option("--url", default=None, help="URL", envvar=ENVVAR_PREFIX + "URL")
@click.option(
    "--tag",
    "tags",
    type=(str, str),
    multiple=True,
    help="Key-value pair to store as a tag. Value is stored as a string",
    envvar=ENVVAR_PREFIX + "TAGS",
)
@click.option(
    "--tagjson",
    "json_tags",
    type=(str, JSONType()),
    multiple=True,
    help="Key-value pair to store as a tag. Value is evaluated as JSON",
    envvar=ENVVAR_PREFIX + "JSON_TAGS",
)
@click.pass_context
def measure(
    ctx: click.Context,
    config_path: Path,
    metrics: Optional[List[str]],
    generation: int,
    url: Optional[str],
    tags: list[tuple[str, str]],
    json_tags: list[tuple[str, Any]],
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
        elif metric.measure_source_is_diffable:
            diffable_content = result.source
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
            epoch=metric.epoch,
            generation=generation,
            tags=dict(tags + json_tags),
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
@click.option(
    "-n",
    "--generation",
    type=int,
    default=None,
    help="Only report on metrics with latest point that matches this generation",
    envvar=ENVVAR_PREFIX + "GENERATION",
)
@click.option("--format", "output_format", default=None)
@click.option(
    "--mute/--no-mute",
    default=False,
    help="If muted, don't exit with an error. Marks latest data points as skipped if they violate a threshold.",
    show_default=True,
)
@click.pass_context
def report(ctx, generation, output_format, mute):
    reports = {}
    list_reporter = ListReporter()
    table_reporter = TableReporter()
    diff_reporter = DiffReporter()
    status_reporter = StatusReporter()

    for metric_name in ctx.obj.iter_metric_names():
        report_data = api.gather_report_data(ctx.obj, metric_name, generation)
        if mute and report_data.violates_limits:
            api.skip_latest(ctx.obj, metric_name)
        reports[metric_name] = report_data
        table_reporter.add(report_data)
        list_reporter.add(report_data)
        diff_reporter.add(report_data)
        status_reporter.add(report_data)

    has_violation = not status_reporter.get_value()

    if output_format == "json":
        status = "ok"
        if has_violation and mute:
            status = "alarm_muted"
        if has_violation and not mute:
            status = "alarm"
        output = {
            "reports": {
                metric_name: report.model_dump(mode="json")
                for metric_name, report in reports.items()
            },
            "table": table_reporter.get_value(),
            "list": list_reporter.get_value(),
            "diff": diff_reporter.get_value(),
            "status": status,
        }
        print(json.dumps(output, indent=2))
    else:
        print(table_reporter.get_value())
        print("")
        print(list_reporter.get_value())
        print("")
        print(diff_reporter.get_value())

    if has_violation and not mute:
        ctx.exit(1)


@cli.command()
@click.option(
    "--keep-last",
    type=click.IntRange(min=1),
    required=False,
    help="Keep the specified number of points for each metric",
)
@click.option(
    "--keep-within",
    type=Duration(),
    required=False,
    help="Keep points recorded within the specified duration of the latest point for each metric",
)
@click.option(
    "--keep-auto", is_flag=True, help="Keep points since the last non-skipped point"
)
@click.pass_context
def prune(ctx, keep_last, keep_within, keep_auto):
    if keep_last is None and keep_within is None and not keep_auto:
        raise click.UsageError(
            "Must specify at least one of --keep-last, --keep-within or --keep-auto"
        )
    count = api.prune(
        ctx.obj, keep_last=keep_last, keep_within=keep_within, keep_auto=keep_auto
    )
    click.echo(f"Pruned {count} points in total")


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
