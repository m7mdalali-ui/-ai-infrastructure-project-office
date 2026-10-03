from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from .models import Schedule

@dataclass(slots=True)
class ProgressComparison:
    summary: dict
    activity_changes: list[dict]
    criticality_changes: list[dict]
    logic_changes: dict
    data_exceptions: list[dict]
    human_decision_required: bool=True

def _iso(d): return d.isoformat() if isinstance(d,datetime) else None

def compare_programmes(baseline: Schedule, update: Schedule) -> ProgressComparison:
    if baseline.project_id and update.project_id and baseline.project_id != update.project_id:
        return ProgressComparison(
            summary={"comparison_status":"BLOCKED","reason":"Explicit project mapping required before comparing different source project IDs."},
            activity_changes=[],criticality_changes=[],logic_changes={"added":[],"removed":[]},
            data_exceptions=[{"code":"PROJECT_ID_MISMATCH","baseline":baseline.project_id,"update":update.project_id}])
    base_ids=set(baseline.activities); upd_ids=set(update.activities)
    common=sorted(base_ids & upd_ids)
    added=sorted(upd_ids-base_ids); deleted=sorted(base_ids-upd_ids)
    changes=[]; crit=[]
    slipped=0; duration_changed=0; progress_inconsistent=0
    for aid in common:
        b=baseline.activities[aid]; u=update.activities[aid]
        row={"activity_id":aid,"name":u.name}
        changed=False
        for attribute in ("name","calendar_id","remaining_duration","actual_start","actual_finish","constraint_date","wbs"):
            before=getattr(b,attribute); after=getattr(u,attribute)
            if before != after:
                row[attribute]={"baseline":_iso(before) if isinstance(before,datetime) else before,
                                "update":_iso(after) if isinstance(after,datetime) else after}
                changed=True
        for field in ("constraint_type","constraint_type_2","constraint_date_2","free_float_hours","float_path","float_path_order"):
            if b.metadata.get(field)!=u.metadata.get(field):
                row[field]={"baseline":b.metadata.get(field),"update":u.metadata.get(field)}
                changed=True
        if b.duration != u.duration:
            row["baseline_duration"]=b.duration; row["update_duration"]=u.duration
            duration_changed+=1; changed=True
        if b.planned_start != u.planned_start:
            row["baseline_start"]=_iso(b.planned_start); row["update_start"]=_iso(u.planned_start); changed=True
        if b.planned_finish != u.planned_finish:
            row["baseline_finish"]=_iso(b.planned_finish); row["update_finish"]=_iso(u.planned_finish); changed=True
            if b.planned_finish and u.planned_finish and u.planned_finish>b.planned_finish: slipped+=1
        if u.percent_complete != b.percent_complete:
            row["baseline_percent"]=b.percent_complete; row["update_percent"]=u.percent_complete; changed=True
        if u.percent_complete < b.percent_complete:
            row["progress_regression"]=True; progress_inconsistent+=1
        if b.source_total_float != u.source_total_float:
            row["baseline_float"]=b.source_total_float; row["update_float"]=u.source_total_float; changed=True
            if b.source_total_float is not None and u.source_total_float is not None:
                crit.append({"activity_id":aid,"name":u.name,"baseline_float":b.source_total_float,"update_float":u.source_total_float,"float_change":u.source_total_float-b.source_total_float})
        if changed: changes.append(row)

    def relkey(r): return (r.predecessor_id,r.successor_id,r.type,round(r.lag_hours if r.lag_hours is not None else r.lag,6))
    br={relkey(r) for r in baseline.relationships}; ur={relkey(r) for r in update.relationships}
    exceptions=[]
    if added: exceptions.append({"code":"ADDED_ACTIVITIES","count":len(added),"examples":added[:50]})
    if deleted: exceptions.append({"code":"DELETED_ACTIVITIES","count":len(deleted),"examples":deleted[:50]})
    if progress_inconsistent: exceptions.append({"code":"PROGRESS_REGRESSION","count":progress_inconsistent})
    if baseline.project_id and update.project_id and baseline.project_id!=update.project_id:
        exceptions.append({"code":"PROJECT_ID_MISMATCH","baseline":baseline.project_id,"update":update.project_id})

    crit.sort(key=lambda x:x["float_change"])
    return ProgressComparison(
        summary={
            "baseline_project":baseline.project_name,"update_project":update.project_name,
            "baseline_data_date":_iso(baseline.data_date),"update_data_date":_iso(update.data_date),
            "common_activities":len(common),"added_activities":len(added),"deleted_activities":len(deleted),
            "changed_activities":len(changes),"duration_changes":duration_changed,
            "activities_with_later_planned_finish":slipped,"progress_regressions":progress_inconsistent,
            "relationships_added":len(ur-br),"relationships_removed":len(br-ur),
        },
        activity_changes=changes,
        criticality_changes=crit[:200],
        logic_changes={"added":[list(x) for x in sorted(ur-br)[:500]],"removed":[list(x) for x in sorted(br-ur)[:500]]},
        data_exceptions=exceptions,
    )

def comparison_to_dict(result: ProgressComparison) -> dict:
    return asdict(result)
