import datetime
import enum
from functools import cached_property
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Point(BaseModel):
    metric_name: str
    time: datetime.datetime
    metric_value: Optional[float]
    absolute_max: Optional[float]
    absolute_min: Optional[float]
    relative_max: Optional[float]
    relative_min: Optional[float]
    measure_source: Optional[str]
    diffable_content: Optional[str]
    url: Optional[str]
    skipped: bool = False
    epoch: int = 0
    generation: int = 0
    tags: Dict[str, Any] = {}

    model_config = dict(from_attributes=True)


class SourceType(str, enum.Enum):
    exec_ = "exec"
    shell = "shell"
    file_ = "file"


class EvalType(str, enum.Enum):
    lines = "lines"
    raw = "raw"


class MeasureType(BaseModel):
    source_type: SourceType
    eval_type: EvalType

    @model_validator(mode="before")
    def parse_string_format(cls, v):
        attrs = v
        if isinstance(v, str):
            source_type, eval_type = v.split("-")
            attrs = dict(source_type=source_type, eval_type=eval_type)
        return attrs


class MetricConfig(BaseModel):
    name: str
    measure_source: str
    measure_type: MeasureType = Field(
        default_factory=lambda: MeasureType(
            source_type=SourceType.file_, eval_type=EvalType.lines
        )
    )
    diffable_source: str = None
    diffable_type: SourceType = SourceType.file_
    measure_source_is_diffable: bool = True
    absolute_max: Optional[float] = None
    absolute_min: Optional[float] = None
    relative_max: Optional[float] = None
    relative_min: Optional[float] = None
    url: Optional[str] = None
    epoch: int = 0


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
    source: str


class MetricDiff(BaseModel):
    metric_name: str
    diff: str


class GenerationMatchStatus(enum.Enum):
    NONE_SPECIFIED = "none_specified"
    NONE_MATCHED = "none_matched"
    MATCHED = "matched"


class ReportData(BaseModel):
    metric_name: str
    generation_status: GenerationMatchStatus = GenerationMatchStatus.NONE_SPECIFIED
    latest_value: Optional[float] = None
    previous_value: Optional[float] = None
    latest_values: List[float] = Field(default_factory=list)
    absolute_max: Optional[float] = None
    absolute_min: Optional[float] = None
    relative_max: Optional[float] = None
    relative_min: Optional[float] = None
    latest_diffable_content: Optional[str] = None
    previous_diffable_content: Optional[str] = None
    latest_url: Optional[str] = None
    previous_url: Optional[str] = None
    latest_tags: Optional[Dict[str, Any]] = None
    previous_tags: Optional[Dict[str, Any]] = None

    @cached_property
    def violates_absolute_max(self) -> bool:
        if self.generation_status == GenerationMatchStatus.NONE_MATCHED:
            return False
        if self.latest_value is None:
            return False
        if self.absolute_max is None:
            return False
        return self.latest_value > self.absolute_max

    @cached_property
    def violates_absolute_min(self) -> bool:
        if self.generation_status == GenerationMatchStatus.NONE_MATCHED:
            return False
        if self.latest_value is None:
            return False
        if self.absolute_min is None:
            return False
        return self.latest_value < self.absolute_min

    @cached_property
    def violates_relative_max(self) -> bool:
        if self.generation_status == GenerationMatchStatus.NONE_MATCHED:
            return False
        latest_change = self.latest_change
        if latest_change is None:
            return False
        if self.relative_max is None:
            return False
        return latest_change > self.relative_max

    @cached_property
    def violates_relative_min(self) -> bool:
        if self.generation_status == GenerationMatchStatus.NONE_MATCHED:
            return False
        latest_change = self.latest_change
        if latest_change is None:
            return False
        if self.relative_min is None:
            return False
        return latest_change < self.relative_min

    @cached_property
    def violates_absolute_limits(self) -> bool:
        return self.violates_absolute_max or self.violates_absolute_min

    @cached_property
    def violates_relative_limits(self) -> bool:
        return self.violates_relative_max or self.violates_relative_min

    @cached_property
    def violates_limits(self) -> bool:
        return self.violates_absolute_limits or self.violates_relative_limits

    @cached_property
    def latest_change(self) -> Optional[float]:
        if self.latest_value is None:
            return None
        if self.previous_value is None:
            return None
        return self.latest_value - self.previous_value
