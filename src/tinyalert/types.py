import datetime
import enum
from functools import cached_property
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class IgnoreType(str, enum.Enum):
    relative = "rel"
    all_ = "all"


class Point(BaseModel):
    metric_name: str
    time: datetime.datetime
    metric_value: Optional[float]
    absolute_max: Optional[float]
    absolute_min: Optional[float]
    relative_max: Optional[float]
    relative_min: Optional[float]
    ignore: Optional[IgnoreType]
    diffable_content: Optional[str]
    url: Optional[str]

    model_config = dict(from_attributes=True)


class ContentType(str, enum.Enum):
    exec_ = "exec"
    file_ = "file"


class EvalType(str, enum.Enum):
    lines = "lines"
    raw = "raw"


class MeasureType(BaseModel):
    content_type: ContentType
    eval_type: EvalType


class MetricConfig(BaseModel):
    name: str
    measure_source: str
    measure_type: MeasureType = Field(
        default_factory=lambda: MeasureType(
            content_type=ContentType.file_, eval_type=EvalType.lines
        )
    )
    diffable_source: str = None
    diffable_type: ContentType = ContentType.file_
    absolute_max: Optional[float] = None
    absolute_min: Optional[float] = None
    relative_max: Optional[float] = None
    relative_min: Optional[float] = None
    url: Optional[str] = None

    @field_validator("measure_type", mode="before")
    def validate_measure_type(cls, v):
        attrs = v
        if isinstance(v, str):
            content_type, eval_type = v.split("-")
            attrs = dict(content_type=content_type, eval_type=eval_type)
        return MeasureType.model_validate(attrs)


class Config(BaseModel):
    metrics: List[MetricConfig] = Field(default_factory=list)

    @field_validator("metrics", mode="before")
    def validate_metrics(cls, v):
        return [
            MetricConfig.model_validate(dict(name=name, **attrs))
            for name, attrs in v.items()
        ]


class MeasureResult(BaseModel):
    value: float
    content: str


class MetricDiff(BaseModel):
    metric_name: str
    diff: str


class ReportData(BaseModel):
    metric_name: str
    latest_value: Optional[float] = None
    previous_value: Optional[float] = None
    latest_values: List[float] = Field(default_factory=list)
    absolute_max: Optional[float] = None
    absolute_min: Optional[float] = None
    relative_max: Optional[float] = None
    relative_min: Optional[float] = None
    ignore: Optional[IgnoreType] = None
    latest_content: Optional[str] = None
    previous_content: Optional[str] = None
    url: Optional[str] = None

    @cached_property
    def violates_absolute_max(self) -> bool:
        if self.latest_value is None:
            return False
        if self.absolute_max is None:
            return False
        return self.latest_value > self.absolute_max

    @cached_property
    def violates_absolute_min(self) -> bool:
        if self.latest_value is None:
            return False
        if self.absolute_min is None:
            return False
        return self.latest_value < self.absolute_min

    @cached_property
    def violates_relative_max(self) -> bool:
        latest_diff = self.latest_diff
        if latest_diff is None:
            return False
        if self.relative_max is None:
            return False
        return latest_diff > self.relative_max

    @cached_property
    def violates_relative_min(self) -> bool:
        latest_diff = self.latest_diff
        if latest_diff is None:
            return False
        if self.relative_min is None:
            return False
        return latest_diff < self.relative_min

    @cached_property
    def violates_absolute_limits(self) -> bool:
        if self.violates_absolute_max or self.violates_absolute_min:
            if self.ignore != IgnoreType.all_:
                return True
        return False

    @cached_property
    def violates_relative_limits(self) -> bool:
        if self.violates_relative_max or self.violates_relative_min:
            if self.ignore != IgnoreType.relative:
                return True
        return False

    @cached_property
    def violates_limits(self) -> bool:
        return self.violates_absolute_limits or self.violates_relative_limits

    @cached_property
    def latest_diff(self) -> Optional[float]:
        if self.latest_value is None:
            return None
        if self.previous_value is None:
            return None
        return self.latest_value - self.previous_value
