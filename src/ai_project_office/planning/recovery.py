from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
import math

@dataclass(slots=True)
class RecoveryScenario:
    remaining_quantity: float
    target_date: str
    available_days: int
    required_quantity_per_day: float | None
    unit_per_item: float
    required_items_per_day: float | None
    production_per_crew_per_day: float
    crews_by_production: int | None
    material_cap_per_day: float | None
    workfront_cap_crews: int | None
    practical_crews: int
    practical_quantity_per_day: float
    earliest_finish_days: int | None
    recoverable_by_target: bool
    bottleneck: str
    human_decision_required: bool = True
    earliest_achievable_finish: str | None = None
    recoverability_date: str | None = None
    non_recoverable_delay_days: int | None = None
    practical_resource_ceiling: int | None = None
    required_quantity_per_week: float | None = None
    data_exceptions: list[dict] | None = None
    assumptions: list[str] | None = None


def _asdate(value):
    if isinstance(value,datetime): return value.date()
    if isinstance(value,date): return value
    raise ValueError('Explicit date required')


def analyse_recovery(*, remaining_quantity: float, target_date: date|datetime,
                     production_per_crew_per_day: float, unit_per_item: float=1.0,
                     start_date: date|datetime|None=None, material_cap_per_day: float|None=None,
                     workfront_cap_crews: int|None=None, available_crews: int|None=None,
                     equipment_cap_crews: int|None=None, sequence_cap_per_day: float|None=None,
                     testing_days: int=0, material_available_date: date|None=None,
                     access_available_date: date|None=None,
                     working_weekdays: tuple[int,...] | None=None) -> RecoveryScenario:
    for value in (remaining_quantity,production_per_crew_per_day,unit_per_item):
        if not math.isfinite(value): raise ValueError('Inputs must be finite')
    if remaining_quantity<0 or production_per_crew_per_day<=0 or unit_per_item<=0:
        raise ValueError('Invalid quantity or productivity')
    if start_date is None: raise ValueError('Explicit assessment start date required; current date is not inferred')
    start=_asdate(start_date); target=_asdate(target_date)
    for cap in (material_cap_per_day,sequence_cap_per_day):
        if cap is not None and (not math.isfinite(cap) or cap<0): raise ValueError('Invalid production cap')
    for cap in (workfront_cap_crews,available_crews,equipment_cap_crews,testing_days):
        if cap is not None and (not isinstance(cap,int) or cap<0): raise ValueError('Crew caps/testing days must be nonnegative integers')
    weekdays=set(range(7) if working_weekdays is None else working_weekdays)
    if not weekdays or not weekdays<=set(range(7)): raise ValueError('Invalid working weekdays')
    gate=max([start]+[_asdate(d) for d in (material_available_date,access_available_date) if d is not None])
    production_deadline=target-timedelta(days=testing_days)
    days=sum((gate+timedelta(days=i)).weekday() in weekdays for i in range(max(0,(production_deadline-gate).days+1)))
    required=remaining_quantity/days if days else (0 if remaining_quantity==0 else None)
    crews=math.ceil(required/production_per_crew_per_day) if required is not None else None
    caps={name:cap for name,cap in [('material',material_cap_per_day),('sequence',sequence_cap_per_day),
          ('workfront',None if workfront_cap_crews is None else workfront_cap_crews*production_per_crew_per_day),
          ('equipment',None if equipment_cap_crews is None else equipment_cap_crews*production_per_crew_per_day)] if cap is not None}
    maximum=min(caps.values()) if caps else None
    ceiling=math.ceil(maximum/production_per_crew_per_day) if maximum is not None else None
    practical=available_crews if available_crews is not None else (crews or ceiling or 0)
    if ceiling is not None: practical=min(practical,ceiling)
    rate=min([practical*production_per_crew_per_day]+list(caps.values()))
    finish_days=math.ceil(remaining_quantity/rate) if rate>0 else (0 if remaining_quantity==0 else None)
    def finish_for(n):
        if n==0: return start+timedelta(days=testing_days)
        d=gate; count=0
        while count<n:
            if d.weekday() in weekdays: count+=1
            if count<n: d+=timedelta(days=1)
        return d+timedelta(days=testing_days)
    finish=finish_for(finish_days) if finish_days is not None else None
    recoverable=finish is not None and finish<=target
    threshold=None
    if maximum and remaining_quantity:
        count=math.ceil(remaining_quantity/maximum); d=production_deadline
        while count:
            if d.weekday() in weekdays: count-=1
            if count: d-=timedelta(days=1)
        threshold=d
    bottlenecks=[name for name,cap in caps.items() if cap<=rate+1e-9]
    if available_crews is not None and practical*production_per_crew_per_day<=rate+1e-9: bottlenecks.append('resources')
    if gate>start: bottlenecks.append('execution gate')
    if testing_days: bottlenecks.append('testing')
    exceptions=[]
    if available_crews is None: exceptions.append({'code':'CURRENT_CREWS_UNKNOWN','description':'Result is a required-resource scenario, not a forecast of current resources.'})
    if maximum is None: exceptions.append({'code':'PRACTICAL_CAPACITY_UNKNOWN','description':'No verified material/workfront/equipment/sequence ceiling supplied; recoverability threshold unavailable.'})
    return RecoveryScenario(remaining_quantity,target.isoformat(),days,required,unit_per_item,
        None if required is None else required/unit_per_item,production_per_crew_per_day,crews,
        material_cap_per_day,workfront_cap_crews,practical,rate,finish_days,recoverable,
        '+'.join(bottlenecks) or 'none',earliest_achievable_finish=None if finish is None else finish.isoformat(),
        recoverability_date=None if threshold is None else threshold.isoformat(),
        non_recoverable_delay_days=None if finish is None else max(0,(finish-target).days),
        practical_resource_ceiling=ceiling,required_quantity_per_week=None if required is None else required*len(weekdays),
        data_exceptions=exceptions,assumptions=['Uniform daily production/delivery; no inventory or batch simulation.',
        'Testing follows production and is measured in elapsed days.',
        'Seven working days/week requires human confirmation.' if working_weekdays is None else 'Working weekdays supplied by user; holidays require a detailed calendar.'])

def recovery_to_dict(result: RecoveryScenario) -> dict:
    return asdict(result)
