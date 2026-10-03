from __future__ import annotations
from .models import Schedule, ReviewIssue, Severity

def _issue(code, severity, description, activity_id=None, impact=None, action=None):
    return ReviewIssue(code=code, severity=severity, description=description, activity_id=activity_id, evidence=activity_id, impact=impact, required_action=action)

def validate_schedule(schedule: Schedule) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    ids=set(schedule.activities)
    incoming={i:0 for i in ids}; outgoing={i:0 for i in ids}
    seen=set()
    for r in schedule.relationships:
        key=(r.predecessor_id,r.successor_id,r.type,r.lag)
        if key in seen:
            issues.append(_issue("DUPLICATE_REL",Severity.WARNING,f"Duplicate relationship {key}"))
        seen.add(key)
        if r.predecessor_id not in ids or r.successor_id not in ids:
            issues.append(_issue("BROKEN_REL",Severity.ERROR,f"Relationship references missing activity: {r.predecessor_id}->{r.successor_id}",impact="Network calculation unreliable",action="Correct activity IDs/relationship"))
            continue
        if r.predecessor_id == r.successor_id:
            issues.append(_issue("SELF_REL",Severity.ERROR,"Activity is linked to itself",r.predecessor_id))
        incoming[r.successor_id]+=1; outgoing[r.predecessor_id]+=1
        if r.type.upper() not in {"FS","SS","FF","SF"}:
            issues.append(_issue("INVALID_REL_TYPE",Severity.ERROR,f"Unsupported relationship type {r.type}",r.successor_id))
    for a in schedule.activities.values():
        if not a.name.strip(): issues.append(_issue("MISSING_NAME",Severity.ERROR,"Activity name is missing",a.id))
        if a.duration < 0: issues.append(_issue("NEGATIVE_DURATION",Severity.ERROR,"Negative duration",a.id))
        if not 0 <= a.percent_complete <= 100: issues.append(_issue("INVALID_PROGRESS",Severity.ERROR,"Percent complete outside 0-100",a.id))
        if a.actual_finish and not a.actual_start: issues.append(_issue("FINISH_WITHOUT_START",Severity.ERROR,"Actual finish exists without actual start",a.id))
        if a.actual_start and a.actual_finish and a.actual_finish < a.actual_start: issues.append(_issue("INVALID_ACTUAL_DATES",Severity.ERROR,"Actual finish precedes actual start",a.id))
        if schedule.data_date and a.actual_start and a.actual_start > schedule.data_date: issues.append(_issue("FUTURE_ACTUAL",Severity.ERROR,"Actual start is after data date",a.id))
        if schedule.data_date and a.actual_finish and a.actual_finish > schedule.data_date: issues.append(_issue("FUTURE_ACTUAL",Severity.ERROR,"Actual finish is after data date",a.id))
        if a.percent_complete >= 100 and not a.actual_finish: issues.append(_issue("COMPLETE_NO_FINISH",Severity.WARNING,"100% complete without actual finish",a.id))
        if a.actual_finish and a.percent_complete < 100: issues.append(_issue("FINISHED_NOT_COMPLETE",Severity.WARNING,"Actual finish exists but progress is below 100%",a.id))
        if incoming[a.id]==0 and outgoing[a.id]==0 and len(ids)>1: issues.append(_issue("ISOLATED",Severity.WARNING,"Activity is isolated from the network",a.id))
        elif incoming[a.id]==0 and a.duration>0: issues.append(_issue("OPEN_START",Severity.WARNING,"Activity has no predecessor",a.id))
        elif outgoing[a.id]==0 and a.duration>0: issues.append(_issue("OPEN_FINISH",Severity.WARNING,"Activity has no successor",a.id))
    return issues
