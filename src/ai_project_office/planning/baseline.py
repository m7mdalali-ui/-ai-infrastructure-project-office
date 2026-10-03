from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from .models import Schedule

@dataclass(slots=True)
class BaselineAssessment:
    executive_summary: dict
    network: dict
    calendars: list[dict]
    milestones: list[dict]
    constraints: list[dict]
    long_duration_activities: list[dict]
    lag_audit: dict
    loading: dict
    wbs: dict
    source_reconciliation: dict

def _activity_row(a):
    return {
        "activity_id":a.id,"name":a.name,"wbs":a.wbs,
        "wbs_name":a.metadata.get("wbs_name"),"duration_days":a.duration,
        "calendar_id":a.calendar_id,"source_total_float_days":a.source_total_float,
        "task_type":a.metadata.get("task_type"),"constraint_type":a.metadata.get("constraint_type"),
    }

def assess_baseline(schedule: Schedule, long_duration_days: float=30.0) -> BaselineAssessment:
    ids=set(schedule.activities)
    incoming=Counter(); outgoing=Counter()
    rel_types=Counter(); positive=[]; negative=[]; pair_types=defaultdict(set)
    for r in schedule.relationships:
        rel_types[r.type]+=1
        if r.predecessor_id in ids and r.successor_id in ids:
            incoming[r.successor_id]+=1; outgoing[r.predecessor_id]+=1
        pair_types[(r.predecessor_id,r.successor_id)].add(r.type)
        if (r.lag_hours or 0)>0: positive.append(r)
        if (r.lag_hours or 0)<0: negative.append(r)

    roots=[a.id for a in schedule.activities.values() if incoming[a.id]==0]
    finishes=[a.id for a in schedule.activities.values() if outgoing[a.id]==0]
    isolated=[a.id for a in schedule.activities.values() if incoming[a.id]==0 and outgoing[a.id]==0 and len(ids)>1]
    milestones=[a for a in schedule.activities.values() if (a.duration==0 and a.metadata.get("duration_conversion_available") is not False) or "MILE" in (a.metadata.get("task_type") or "").upper()]
    constraints=[a for a in schedule.activities.values() if a.metadata.get("constraint_type") or a.metadata.get("constraint_type_2")]
    long_acts=[a for a in schedule.activities.values() if a.duration>long_duration_days and a not in milestones]
    long_acts.sort(key=lambda a:a.duration,reverse=True)

    cal_rows=[]
    for c in schedule.calendars.values():
        parsed=c.metadata.get("parsed_weekly_hours")
        mismatch=bool(parsed is not None and c.hours_per_week is not None and abs(parsed-c.hours_per_week)>0.01)
        cal_rows.append({"id":c.id,"name":c.name,"hours_per_day":c.hours_per_day,"declared_hours_per_week":c.hours_per_week,"parsed_hours_per_week":parsed,"exception_count":c.metadata.get("exception_count"),"hours_mismatch":mismatch})

    compound=[{"predecessor":p,"successor":s,"types":sorted(types)} for (p,s),types in pair_types.items() if len(types)>1]
    pos_sorted=sorted(positive,key=lambda r:abs(r.lag_hours or 0),reverse=True)
    zero_float=sum(1 for a in schedule.activities.values() if a.source_total_float is not None and abs(a.source_total_float)<1e-9)
    near_float=sum(1 for a in schedule.activities.values() if a.source_total_float is not None and 0<a.source_total_float<=10)
    negative_float=sum(1 for a in schedule.activities.values() if a.source_total_float is not None and a.source_total_float<0)

    assignments=schedule.metadata.get("resource_assignment_count",0)
    target_cost=schedule.metadata.get("target_cost_sum",0.0)
    cost_count=schedule.metadata.get("cost_assignment_count",0)
    if assignments and cost_count and target_cost:
        loading_status="resource_and_cost_loaded" if cost_count==assignments else "partially_cost_loaded"
    elif assignments:
        loading_status="resource_loaded_cost_loading_unconfirmed"
    else:
        loading_status="not_resource_loaded"

    return BaselineAssessment(
        executive_summary={
            "project_id":schedule.project_id,"project_name":schedule.project_name,
            "activities":len(schedule.activities),"relationships":len(schedule.relationships),
            "wbs_records":schedule.metadata.get("wbs_count",0),"calendars":len(schedule.calendars),
            "source_zero_float_activities":zero_float,"source_near_critical_0_to_10_days":near_float,
            "source_negative_float_activities":negative_float,
            "human_decision_required":True,
        },
        network={"roots":roots,"finishes":finishes,"isolated":isolated,"relationship_types":dict(rel_types),"compound_logic_pairs":len(compound),"compound_logic_examples":compound[:100]},
        calendars=cal_rows,
        milestones=[_activity_row(a) for a in milestones],
        constraints=[_activity_row(a) for a in constraints],
        long_duration_activities=[_activity_row(a) for a in long_acts],
        lag_audit={
            "positive_lag_count":len(positive),"negative_lag_count":len(negative),
            "largest_positive_lags":[{"predecessor":r.predecessor_id,"successor":r.successor_id,"type":r.type,"lag_hours":r.lag_hours,"lag_days_normalized":r.lag} for r in pos_sorted[:100]],
        },
        loading={"status":loading_status,"resource_count":schedule.metadata.get("resource_count",0),"resource_assignment_count":assignments,"cost_assignment_count":cost_count,"target_cost_sum":target_cost},
        wbs={"count":schedule.metadata.get("wbs_count",0),"records":schedule.metadata.get("wbs_records",{})},
        source_reconciliation={"p6_source_float_preserved":True,"p6_source_dates_preserved":True,"independent_cpm_calendar_aware":False,"warning":"Independent CPM is not P6-equivalent until detailed calendar/date arithmetic and constraint handling are verified."},
    )

def assessment_to_dict(assessment: BaselineAssessment) -> dict:
    return asdict(assessment)
