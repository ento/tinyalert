import datetime
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from .db import DB
from .db import Point as DBPoint
from .types import (
    EvalType,
    GenerationMatchStatus,
    MeasureResult,
    MeasureType,
    Point,
    ReportData,
    SourceType,
)


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
    skipped: bool = False,
    epoch: int = 0,
    generation: int = 0,
    tags: Dict[str, Any] = None,
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
        skipped=skipped,
        epoch=epoch,
        generation=generation,
        tags=tags or {},
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
            dest_db.add(Point.model_validate(p))


def prune(
    db: DB,
    keep_last: Optional[int] = None,
    keep_within: Optional[datetime.timedelta] = None,
    keep_auto: bool = False,
) -> int:
    total_pruned = 0
    for metric_name in db.iter_metric_names():
        points = list(db.recent(metric_name, count=None))

        auto_prune_before = _prune_point_auto(points)
        prune_candidates = list(
            filter(
                None,
                (
                    _prune_point_last(points, keep_last),
                    _prune_point_within(points, auto_prune_before, keep_within),
                    auto_prune_before if keep_auto else None,
                ),
            )
        )

        if not prune_candidates:
            continue

        # Take the oldest point
        prune_before = sorted(prune_candidates, key=lambda p: (p.time, p.id))[0]
        total_pruned += db.prune_before(prune_before)

    if total_pruned > 0:
        db.vacuum()

    return total_pruned


def _prune_point_last(
    points: List[DBPoint], keep_last: Optional[int]
) -> Optional[DBPoint]:
    assert keep_last is None or keep_last > 0
    if not points:
        return
    if keep_last is None:
        return
    if len(points) < keep_last:
        return points[-1]
    return points[keep_last - 1]


def _prune_point_within(
    points: List[DBPoint],
    auto_prune_before: Optional[DBPoint],
    keep_within: Optional[datetime.timedelta],
) -> Optional[DBPoint]:
    assert keep_within is None or keep_within.total_seconds() > 0
    assert points
    if keep_within is None:
        return
    if len(points) == 1:
        return points[0]
    anchor_point = auto_prune_before or points[0]
    keep_within_abs = anchor_point.time - keep_within
    prune_before = points[1]
    for p in points[2:]:
        if p.time < keep_within_abs:
            break
        prune_before = p
    return prune_before


def _prune_point_auto(points: List[DBPoint]) -> Optional[DBPoint]:
    if not points:
        return
    if len(points) == 1:
        return points[0]

    current_epoch_points = list(_iter_current_epoch_points(points))
    eligible_points = _iter_alert_eligible_points(current_epoch_points)
    latest, previous, _ = _report_points(eligible_points)

    if latest and not latest.skipped:
        return latest
    elif previous:
        return previous
    return current_epoch_points[-1] if current_epoch_points else None


def recent(db: DB, count: int = 10) -> Iterator[Point]:
    assert count > 0, "count must be greater than 0"
    for p in db.recent(count=count):
        yield Point.model_validate(p)


def gather_report_data(
    db: DB, metric_name: str, head_generation: Optional[int] = None
) -> ReportData:
    data = ReportData(metric_name=metric_name)
    points = list(db.recent(metric_name, count=None))

    if not points:
        return data

    data.latest_values = [p.metric_value for p in reversed(points[:10])]

    eligible_points = _iter_alert_eligible_points(points, head_generation)
    latest, previous, generation_status = _report_points(eligible_points)
    if generation_status:
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
    if previous:
        data.previous_value = previous.metric_value
        data.previous_diffable_content = previous.diffable_content
        data.previous_url = previous.url
        data.previous_tags = previous.tags

    return data


def _report_points(
    eligible_points: Iterator[Tuple[DBPoint, GenerationMatchStatus]],
) -> Tuple[Optional[DBPoint], Optional[DBPoint], Optional[GenerationMatchStatus]]:
    latest, generation_status = next(eligible_points, (None, None))
    previous, _ = next(eligible_points, (None, None))
    return (latest, previous, generation_status)


def _iter_current_epoch_points(all_points: Sequence[DBPoint]) -> Iterator[DBPoint]:
    active_epoch = None
    for i, p in enumerate(all_points):
        if i == 0:
            active_epoch = p.epoch
        if p.epoch != active_epoch:
            break
        yield p


def _iter_alert_eligible_points(
    all_points: Sequence[DBPoint],
    head_generation: Optional[int] = None,
    check_epoch: bool = True,
) -> Iterator[Tuple[DBPoint, GenerationMatchStatus]]:
    generation_status = (
        GenerationMatchStatus.NONE_SPECIFIED
        if head_generation is None
        else GenerationMatchStatus.NONE_MATCHED
    )
    for i, p in enumerate(_iter_current_epoch_points(all_points)):
        if i == 0:
            if head_generation is not None and p.generation == head_generation:
                generation_status = GenerationMatchStatus.MATCHED
            yield p, generation_status
            continue
        if p.skipped:
            continue
        yield p, generation_status
