from __future__ import annotations
from dataclasses import dataclass, asdict
from .models import Schedule, ReviewIssue, Severity
from .validation import validate_schedule
from .cpm import calculate_cpm, NetworkCycleError

@dataclass(slots=True)
class ProgrammeReview:
    facts: dict
    calculated_results: dict
    data_exceptions: list[dict]
    analysis: list[str]
    risks: list[str]
    recommendation: str
    required_actions: list[str]
    confidence: str
    human_decision_required: bool=True

def review_programme(schedule: Schedule, programme_type: str="Updated") -> ProgrammeReview:
    issues=validate_schedule(schedule)
    cpm=None
    try: cpm=calculate_cpm(schedule)
    except NetworkCycleError as exc:
        issues.append(ReviewIssue("CIRCULAR_LOGIC",Severity.CRITICAL,str(exc),impact="CPM results cannot be relied upon",required_action="Correct circular logic and resubmit"))
    errors=[i for i in issues if i.severity in {Severity.ERROR,Severity.CRITICAL}]
    warnings=[i for i in issues if i.severity==Severity.WARNING]
    if errors: recommendation="Revise & Resubmit"
    elif warnings: recommendation="Accept with Comments"
    else: recommendation="Accept"
    result={} if not cpm else {"project_finish_day":cpm.project_finish,"critical_activities":cpm.critical_activities,"near_critical_activities":cpm.near_critical_activities,"negative_float_activities":cpm.negative_float_activities}
    return ProgrammeReview(
        facts={"project_id":schedule.project_id,"project_name":schedule.project_name,"programme_type":programme_type,"activity_count":len(schedule.activities),"relationship_count":len(schedule.relationships),"source_type":schedule.source_type},
        calculated_results=result,
        data_exceptions=[asdict(i) for i in issues],
        analysis=[f"{len(errors)} error/critical issue(s); {len(warnings)} warning(s)."],
        risks=["Programme reliability is reduced until error/critical data exceptions are resolved."] if errors else [],
        recommendation=recommendation,
        required_actions=sorted({i.required_action for i in issues if i.required_action}),
        confidence="low" if errors else ("medium" if warnings else "high"),
    )
