import datetime
import shlex
import subprocess
from typing import Iterator, List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

from .db import DB
from .types import EvalType, IgnoreType, MeasureResult, MeasureType, ReportData, Point


def push(
    db: DB,
    metric_name: str,
    value: Optional[float] = None,
    absolute_max: Optional[float] = None,
    absolute_min: Optional[float] = None,
    relative_max: Optional[float] = None,
    relative_min: Optional[float] = None,
    ignore: Optional[IgnoreType] = None,
    measure_source: Optional[str] = None,
    url: Optional[str] = None,
) -> Point:
    p = Point(
        metric_name=metric_name,
        time=datetime.datetime.now(datetime.timezone.utc),
        metric_value=value,
        absolute_max=absolute_max,
        absolute_min=absolute_min,
        relative_max=relative_max,
        relative_min=relative_min,
        ignore=ignore,
        diffable_content=measure_source,
        url=url,
    )
    return db.add(p)


def combine(dest_db: DB, src_dbs: List[DB]):
    for src_db in src_dbs:
        for p in src_db.iter_all():
            dest_db.add(p)


def prune(db: DB, keep: int = 10) -> int:
    assert keep > 0, "keep must be greater than 0"
    return db.prune(keep=keep)


def recent(db: DB, count: int = 10) -> Iterator[Point]:
    assert count > 0, "count must be greater than 0"
    for p in db.recent(count=count):
        yield p


def measure(source: str, method: MeasureType) -> MeasureResult:
    content = subprocess.check_output(shlex.split(source)).strip()
    if method.eval_type == EvalType.lines:
        return MeasureResult(value=len(content.splitlines()), content=content)
    if method.eval_type == EvalType.raw:
        return MeasureResult(value=float(content.strip()), content=content)
    raise Exception(f"Unknown measurement method: {method}")


def gather_report_data(db: DB, metric_name: str) -> ReportData:
    data = ReportData(metric_name=metric_name)
    points = list(db.recent(metric_name, 10))

    if not points:
        return data

    data.latest_values = [p.metric_value for p in points]

    latest = points.pop(0)
    data.latest_value = latest.metric_value
    data.absolute_max = latest.absolute_max
    data.absolute_min = latest.absolute_min
    data.relative_max = latest.relative_max
    data.relative_min = latest.relative_min
    data.ignore = latest.ignore
    data.latest_content = latest.diffable_content
    data.url = latest.url

    if not points:
        return data

    previous = points.pop(0)
    data.previous_value = previous.metric_value
    data.previous_content = previous.diffable_content

    return data
