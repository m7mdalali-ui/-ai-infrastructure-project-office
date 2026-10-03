from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date, datetime
import math

@dataclass(slots=True)
class RecoveryScenario:
    remaining_quantity: float
    target_date: str
    available_days: int
    required_quantity_per_day: float
    unit_per_item: float
    required_items_per_day: float
    production_per_crew_per_day: float
    crews_by_production: int
    material_cap_per_day: float | None
    workfront_cap_crews: int | None
    practical_crews: int
    practical_quantity_per_day: float
    earliest_finish_days: int | None
    recoverable_by_target: bool
    bottleneck: str
    human_decision_required: bool=True

def _days_until(target, start=None):
    if isinstance(target,datetime): target=target.date()
    if isinstance(start,datetime): start=start.date()
    if start is None: start=date.today()
    return max((target-start).days+1,0)

def analyse_recovery(*, remaining_quantity: float, target_date: date|datetime,
                     production_per_crew_per_day: float, unit_per_item: float=1.0,
                     start_date: date|datetime|None=None, material_cap_per_day: float|None=None,
                     workfront_cap_crews: int|None=None) -> RecoveryScenario:
    if remaining_quantity<0 or production_per_crew_per_day<=0 or unit_per_item<=0:
        raise ValueError("Quantities and productivity must be valid positive values.")
    days=_days_until(target_date,start_date)
    required_q=(remaining_quantity/days) if days else math.inf
    required_items=required_q/unit_per_item
    crews=math.ceil(required_q/production_per_crew_per_day) if math.isfinite(required_q) else math.inf
    practical_crews=int(crews) if math.isfinite(crews) else 0
    bottlenecks=[]
    if workfront_cap_crews is not None and practical_crews>workfront_cap_crews:
        practical_crews=workfront_cap_crews; bottlenecks.append("workfront")
    crew_cap=practical_crews*production_per_crew_per_day
    practical_q=crew_cap
    if material_cap_per_day is not None and material_cap_per_day<practical_q:
        practical_q=material_cap_per_day; bottlenecks.append("material")
    if practical_q<=0:
        finish_days=None; recoverable=False
    else:
        finish_days=math.ceil(remaining_quantity/practical_q)
        recoverable=finish_days<=days
    if not bottlenecks and not recoverable: bottlenecks.append("production")
    return RecoveryScenario(
        remaining_quantity, str(target_date), days, required_q, unit_per_item, required_items,
        production_per_crew_per_day, int(crews) if math.isfinite(crews) else 0,
        material_cap_per_day, workfront_cap_crews, practical_crews, practical_q,
        finish_days,recoverable,"+".join(bottlenecks) if bottlenecks else "none"
    )

def recovery_to_dict(result: RecoveryScenario) -> dict:
    return asdict(result)
