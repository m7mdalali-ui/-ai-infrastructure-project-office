from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class Severity(str, Enum):
    INFO="info"; WARNING="warning"; ERROR="error"; CRITICAL="critical"

@dataclass(slots=True)
class Activity:
    id: str
    name: str
    duration: float = 0.0
    remaining_duration: float | None = None
    percent_complete: float = 0.0
    actual_start: datetime | None = None
    actual_finish: datetime | None = None
    planned_start: datetime | None = None
    planned_finish: datetime | None = None
    constraint_date: datetime | None = None
    calendar_id: str | None = None
    wbs: str | None = None
    source_total_float: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    es: float | None = None
    ef: float | None = None
    ls: float | None = None
    lf: float | None = None
    total_float: float | None = None
    free_float: float | None = None
    critical: bool = False
    near_critical: bool = False

@dataclass(slots=True)
class Relationship:
    predecessor_id: str
    successor_id: str
    type: str = "FS"
    lag: float = 0.0

@dataclass(slots=True)
class Schedule:
    project_id: str
    project_name: str
    activities: dict[str, Activity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    data_date: datetime | None = None
    calendars: dict[str, Any] = field(default_factory=dict)
    source_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class ReviewIssue:
    code: str
    severity: Severity
    description: str
    activity_id: str | None = None
    evidence: str | None = None
    impact: str | None = None
    required_action: str | None = None

@dataclass(slots=True)
class CPMResult:
    project_finish: float
    critical_activities: list[str]
    near_critical_activities: list[str]
    negative_float_activities: list[str]
    topological_order: list[str]
