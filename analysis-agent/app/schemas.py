from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MarkerStatus(str, Enum):
    present = "present"
    absent = "absent"
    partial = "partial"


class Location(str, Enum):
    top_left = "верхний левый угол"
    top_center = "верхний центр"
    top_right = "верхний правый угол"
    mid_left = "средний левый"
    center = "центр кадра"
    mid_right = "средний правый"
    bottom_left = "нижний левый угол"
    bottom_center = "нижний центр"
    bottom_right = "нижний правый угол"
    na = "N/A"


class UtilityStatus(str, Enum):
    not_connected = "not_connected"
    in_progress = "in_progress"
    connected = "connected"
    not_visible = "not_visible"


class ObjectMatch(str, Enum):
    match = "match"
    mismatch = "mismatch"
    uncertain = "uncertain"


class ImageQuality(str, Enum):
    excellent = "excellent"
    good = "good"
    fair = "fair"
    poor = "poor"


class ComplianceStatus(str, Enum):
    on_track = "on_track"
    ahead = "ahead"
    behind = "behind"
    unknown = "unknown"


class DeviationSeverity(str, Enum):
    critical = "critical"
    moderate = "moderate"
    minor = "minor"
    none = "none"


class MaterialsStatus(str, Enum):
    match = "match"
    mismatch = "mismatch"
    partial = "partial"
    not_assessable = "not_assessable"


class MarkerCheck(BaseModel):
    feature: str
    status: MarkerStatus
    location: str
    confidence: float = Field(ge=0.0, le=1.0)
    note: str | None = None


class Utilities(BaseModel):
    electricity: UtilityStatus | None = None
    gas: UtilityStatus | None = None
    water: UtilityStatus | None = None
    sewerage: UtilityStatus | None = None


class ReportCommon(BaseModel):
    object_match: ObjectMatch
    mismatch_description: str | None = None
    detected_stage_ids: list[int] | None = Field(default=None, min_length=1, max_length=2)
    stage_transition_comment: str | None = None
    stage_progress_percent: int | None = Field(default=None, ge=0, le=100)
    stage_progress_comment: str | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    progress_comment: str | None = None
    checklist: list[MarkerCheck] = Field(default_factory=list)
    utilities: Utilities | None = None
    utilities_comment: str | None = None
    looks_residential: bool | None = None
    residential_comment: str | None = None
    attention_required: bool = False
    attention_reason: str | None = None
    markup_used: bool | None = None
    image_quality: ImageQuality
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ReportWithPlan(ReportCommon):
    plan_understanding: str | None = None
    compliance_status: ComplianceStatus | None = None
    compliance_comment: str | None = None
    deviation_days: int | None = None
    deviation_severity: DeviationSeverity | None = None
    materials_status: MaterialsStatus | None = None
    materials_comment: str | None = None


class ReportNoPlan(ReportCommon):
    pass


ReportMode = Literal["with_plan", "no_plan"]
