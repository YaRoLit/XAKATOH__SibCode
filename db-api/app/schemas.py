from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    login: str
    password: str


class UserOut(BaseModel):
    id: str
    login: str
    role: str
    display_name: str


class TokenOut(BaseModel):
    token: str
    user: UserOut


class Corner(BaseModel):
    lat: float
    lon: float


def validate_plot_corners(value: list[Corner]) -> list[Corner]:
    n = len(value)
    if n == 1 or n >= 4:
        return value
    raise ValueError("Укажите одну точку участка или не меньше четырёх угловых точек")


class ObjectImportCreate(BaseModel):
    name: str
    cadastral_number: str
    address: str
    plot_corners: list[Corner] = []
    credit_issued_at: date
    planned_completion_at: date
    material: str = "иное"

    @field_validator("plot_corners")
    @classmethod
    def corners_ok(cls, value: list[Corner]) -> list[Corner]:
        if not value:
            return value
        return validate_plot_corners(value)


class ObjectCreate(BaseModel):
    name: str
    cadastral_number: str
    address: str
    plot_corners: list[Corner] = Field(min_length=1)
    credit_issued_at: date
    planned_completion_at: date
    material: str

    @field_validator("plot_corners")
    @classmethod
    def corners_unique_enough(cls, value: list[Corner]) -> list[Corner]:
        return validate_plot_corners(value)


class ObjectUpdate(BaseModel):
    name: str | None = None
    cadastral_number: str | None = None
    address: str | None = None
    plot_corners: list[Corner] | None = Field(default=None, min_length=1)
    credit_issued_at: date | None = None
    planned_completion_at: date | None = None
    material: str | None = None

    @field_validator("plot_corners")
    @classmethod
    def corners_ok(cls, value: list[Corner] | None) -> list[Corner] | None:
        if value is None:
            return value
        return validate_plot_corners(value)


class CheckpointDateUpdate(BaseModel):
    planned_date: date
    confirm: bool = False


class AlertActionIn(BaseModel):
    status: Literal["new", "in_progress", "resolved", "reopened"] | None = None
    comment: str | None = None


class CheckpointOut(BaseModel):
    id: str
    object_id: str
    object_name: str | None = None
    title: str
    planned_date: date
    expected_readiness: int
    sort_order: int
    shoot_status: str
    actual_shot_at: datetime | None = None
    date_history: list[dict[str, Any]] = []


class ObjectOut(BaseModel):
    id: str
    name: str | None
    cadastral_number: str
    address: str
    plot_corners: list[dict]
    status: str
    material: str | None
    credit_issued_at: date | None
    planned_completion_at: date | None
    is_demo: bool
    has_problems: bool = False
    checkpoints: list[CheckpointOut] = []
    created_at: datetime | None = None


class ObjectListOut(BaseModel):
    items: list[ObjectOut]
    total: int
    page: int
    page_size: int


class AlertOut(BaseModel):
    id: str
    object_id: str
    object_name: str | None = None
    report_id: str | None
    title: str
    summary: str | None
    severity: str | None
    status: str
    raw_item: dict | None
    created_at: datetime
    actions: list[dict[str, Any]] = []


class PlanIn(BaseModel):
    description: str = ""


class ReportOut(BaseModel):
    id: str
    object_id: str
    checkpoint_id: str | None
    agent_run_id: str | None
    raw_json: dict
    created_at: datetime


class DashboardOut(BaseModel):
    objects_in_progress: int
    objects_with_problems: int
    overdue_checkpoints: int
    upcoming_checkpoints: list[CheckpointOut]
    recent_alerts: list[AlertOut]
