import datetime
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .db import DB
from .types import EvalType, MeasureResult, MeasureType, Point, ReportData, SourceType, GenerationMatchStatus


def push(
    db: DB,
    metric_name: str,
    value: Optional[float] = None,
    absolute_max: Optional[float] = None,
    absolute_min: Optional[float] = None,
    relative_max: Optional[float] = None,
    relative_min: Optional[float] = None,
    measure_source: Optional[str] = None,
    diffable_content: Optional[str] = None,
    url: Optional[str] = None,
    epoch: int = 0,
    generation: int = 0,
    tags: Dict[str, Any] = {},
) -> Point:
    p = Point(
        metric_name=metric_name,
        time=datetime.datetime.now(datetime.timezone.utc),
        metric_value=value,
        absolute_max=absolute_max,
        absolute_min=absolute_min,
        relative_max=relative_max,
        relative_min=relative_min,
        measure_source=measure_source,
        diffable_content=diffable_content,
        url=url,
        epoch=epoch,
        generation=generation,
        tags=tags,
    )
    return db.add(p)


def measure(source: str, method: MeasureType) -> MeasureResult:
    source_content = eval_source(source, method.source_type)
    if method.eval_type == EvalType.lines:
        return MeasureResult(
            value=len(source_content.splitlines()), source=source_content
        )
    if method.eval_type == EvalType.raw:
        return MeasureResult(value=float(source_content.strip()), source=source_content)
    raise Exception(f"Unknown measurement method: {method}")


def eval_source(source: str, method: SourceType) -> str:
    if method == SourceType.exec_:
        return subprocess.check_output(shlex.split(source), text=True).strip()
    if method == SourceType.shell:
        return subprocess.check_output(source, shell=True, text=True).strip()
    if method == SourceType.file_:
        return Path(source).read_text()
    raise Exception(f"Unknown source type: {method}")


def skip_latest(db: DB, metric_name: str):
    db.skip_latest(metric_name)


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


def gather_report_data(
    db: DB, metric_name: str, head_generation: Optional[int] = None
) -> ReportData:
    data = ReportData(metric_name=metric_name)
    points = list(db.recent(metric_name, count=None))

    if not points:
        return data

    data.latest_values = [p.metric_value for p in reversed(points[:10])]

    eligible_points = _iter_alert_eligible_points(points, head_generation)
    latest, generation_status = next(eligible_points, None)
    data.generation_status = generation_status
    if latest:
        data.latest_value = latest.metric_value
        data.absolute_max = latest.absolute_max
        data.absolute_min = latest.absolute_min
        data.relative_max = latest.relative_max
        data.relative_min = latest.relative_min
        data.latest_diffable_content = latest.diffable_content
        data.latest_url = latest.url
        data.latest_tags = latest.tags

    previous, _ = next(eligible_points, (None, None))
    if previous:
        data.previous_value = previous.metric_value
        data.previous_diffable_content = previous.diffable_content
        data.previous_url = previous.url
        data.previous_tags = previous.tags

    return data


def _iter_alert_eligible_points(
    all_points: Sequence[Point], head_generation: Optional[int] = None
) -> Iterator[Tuple[Point, GenerationMatchStatus]]:
    active_epoch = None
    generation_status = GenerationMatchStatus.NONE_SPECIFIED if head_generation is None else GenerationMatchStatus.NONE_MATCHED
    for i, p in enumerate(all_points):
        if i == 0:
            if head_generation is not None and p.generation == head_generation:
                generation_status = GenerationMatchStatus.MATCHED
            active_epoch = p.epoch
            yield p, generation_status
            continue
        if p.skipped:
            continue
        if p.epoch != active_epoch:
            break
        yield p, generation_status
