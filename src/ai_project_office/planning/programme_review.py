from __future__ import annotations
from collections import Counter, defaultdict
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

def _baseline_audits(schedule: Schedule) -> tuple[list[ReviewIssue],dict]:
    issues=[]; rel_types=Counter(r.type for r in schedule.relationships)
    positive_lags=[r for r in schedule.relationships if r.lag_hours is not None and r.lag_hours>0]
    negative_lags=[r for r in schedule.relationships if r.lag_hours is not None and r.lag_hours<0]
    pairs=defaultdict(set)
    for r in schedule.relationships: pairs[(r.predecessor_id,r.successor_id)].add(r.type)
    compound=sum(1 for types in pairs.values() if len(types)>1)
    constraints=[a for a in schedule.activities.values() if a.metadata.get("constraint_type")]
    long_acts=[a for a in schedule.activities.values() if a.duration>30 and (a.metadata.get("task_type") or "").upper() not in {"TT_MILE","TT_STARTMILE","TT_FINMILE"}]
    zero_source_float=sum(1 for a in schedule.activities.values() if a.source_total_float is not None and abs(a.source_total_float)<1e-9)
    near_source_float=sum(1 for a in schedule.activities.values() if a.source_total_float is not None and 0<a.source_total_float<=10)

    if positive_lags:
        issues.append(ReviewIssue("POSITIVE_LAG_AUDIT",Severity.INFO,f"{len(positive_lags)} relationship(s) contain positive lag.",evidence="P6 TASKPRED lag_hr_cnt",impact="Large or repeated lags can hide waiting periods and reduce transparency.",required_action="Review material positive lags and confirm they represent valid planning logic."))
    if negative_lags:
        issues.append(ReviewIssue("NEGATIVE_LAG",Severity.WARNING,f"{len(negative_lags)} relationship(s) contain negative lag.",evidence="P6 TASKPRED lag_hr_cnt",impact="Leads can create optimistic or difficult-to-audit logic.",required_action="Justify or replace negative lags with explicit activities where practical."))
    if compound:
        issues.append(ReviewIssue("COMPOUND_LOGIC_AUDIT",Severity.INFO,f"{compound} predecessor/successor pair(s) use more than one relationship type.",evidence="P6 TASKPRED",impact="SS/FF combinations may be valid but require review for transparent sequencing.",required_action="Review compound relationship pairs for necessity and driving effect."))
    if constraints:
        issues.append(ReviewIssue("CONSTRAINT_AUDIT",Severity.INFO,f"{len(constraints)} activity/milestone record(s) contain a primary P6 constraint.",evidence="P6 TASK cstr_type",impact="Constraints may affect calculated float and criticality.",required_action="Confirm each constraint is contractually or technically justified."))
    if long_acts:
        issues.append(ReviewIssue("LONG_DURATION_AUDIT",Severity.INFO,f"{len(long_acts)} non-milestone activity record(s) exceed 30 calendar-normalized working days.",evidence="P6 target_drtn_hr_cnt / activity calendar day_hr_cnt",impact="Long activities may reduce progress transparency; legitimate LOE/procurement activities should be distinguished.",required_action="Review long-duration construction activities separately from LOE and long-lead procurement."))
    if schedule.calendars:
        issues.append(ReviewIssue("CALENDAR_CPM_PENDING",Severity.WARNING,"Source calendars were preserved, but deterministic CPM is not yet calendar/exception aware.",evidence=f"{len(schedule.calendars)} P6 calendar(s) parsed including raw clndr_data",impact="Independent CPM dates/float must not yet be presented as equivalent to Primavera P6.",required_action="Use source P6 float/dates for baseline review until calendar-aware CPM is verified."))

    metrics={"relationship_types":dict(rel_types),"positive_lag_count":len(positive_lags),"negative_lag_count":len(negative_lags),"compound_logic_pair_count":compound,"constraint_count":len(constraints),"long_duration_count":len(long_acts),"source_zero_float_count":zero_source_float,"source_near_critical_0_to_10_count":near_source_float}
    return issues,metrics

def review_programme(schedule: Schedule, programme_type: str="Updated") -> ProgrammeReview:
    issues=validate_schedule(schedule)
    audit_issues,audit_metrics=_baseline_audits(schedule)
    issues.extend(audit_issues)
    cpm=None
    try: cpm=calculate_cpm(schedule)
    except NetworkCycleError as exc:
        issues.append(ReviewIssue("CIRCULAR_LOGIC",Severity.CRITICAL,str(exc),impact="CPM results cannot be relied upon",required_action="Correct circular logic and resubmit"))
    errors=[i for i in issues if i.severity in {Severity.ERROR,Severity.CRITICAL}]
    warnings=[i for i in issues if i.severity==Severity.WARNING]
    recommendation="Revise & Resubmit" if errors else ("Accept with Comments" if warnings else "Accept")
    result={"source_p6":audit_metrics}
    if cpm:
        result["deterministic_network_check"]={"project_finish_day":cpm.project_finish,"critical_activities":cpm.critical_activities,"near_critical_activities":cpm.near_critical_activities,"negative_float_activities":cpm.negative_float_activities,"calendar_aware":False}
    return ProgrammeReview(
        facts={"project_id":schedule.project_id,"project_name":schedule.project_name,"programme_type":programme_type,"activity_count":len(schedule.activities),"relationship_count":len(schedule.relationships),"calendar_count":len(schedule.calendars),"source_type":schedule.source_type,"source_metadata":schedule.metadata},
        calculated_results=result,
        data_exceptions=[asdict(i) for i in issues],
        analysis=[f"{len(errors)} error/critical issue(s); {len(warnings)} warning(s).","P6 source dates/float remain authoritative for date-based comparison until calendar-aware CPM verification is complete."],
        risks=["Programme reliability is reduced until error/critical data exceptions are resolved."] if errors else [],
        recommendation=recommendation,
        required_actions=sorted({i.required_action for i in issues if i.required_action}),
        confidence="low" if errors else ("medium" if warnings else "high"),
    )
