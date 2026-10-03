from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from .service import import_schedule
from .baseline import assess_baseline, assessment_to_dict
from .progress import compare_programmes, comparison_to_dict
from .recovery import analyse_recovery, recovery_to_dict
from .monthly_report import review_monthly_report, monthly_review_to_dict
from .eot import DelayEvent, assess_eot, eot_to_dict

@dataclass(slots=True)
class PlanningAgentResponse:
    task: str
    status: str
    result: dict[str,Any]
    data_exceptions: list[dict[str,Any]]
    required_actions: list[str]
    human_decision_required: bool=True

class SeniorPlanningAgent:
    """Application-facing orchestration layer. Deterministic engines do calculations;
    language models may explain results but must not replace source facts/calculations.
    """

    def baseline_review(self, path: str|Path) -> PlanningAgentResponse:
        s=import_schedule(path)
        result=assessment_to_dict(assess_baseline(s))
        exceptions=[]
        for c in result["calendars"]:
            if c["hours_mismatch"]:
                exceptions.append({"code":"CALENDAR_HOURS_MISMATCH","calendar_id":c["id"],"name":c["name"]})
        actions=[]
        if exceptions: actions.append("Verify affected P6 calendar definitions before relying on independent date calculations.")
        return PlanningAgentResponse("baseline_review","completed",result,exceptions,actions)

    def update_review(self, baseline_path: str|Path, update_path: str|Path) -> PlanningAgentResponse:
        b=import_schedule(baseline_path); u=import_schedule(update_path)
        result=comparison_to_dict(compare_programmes(b,u))
        return PlanningAgentResponse("update_review","completed",result,result.get("data_exceptions",[]),
            ["Review material logic, duration, progress and float changes before accepting the update."])

    def recovery_analysis(self, **inputs) -> PlanningAgentResponse:
        result=recovery_to_dict(analyse_recovery(**inputs))
        actions=[]
        if not result["recoverable_by_target"]:
            actions.append("Escalate the controlling bottleneck and agree a realistic recovery/forecast scenario.")
        return PlanningAgentResponse("recovery_analysis","completed",result,[],actions)

    def monthly_report_review(self, report:dict, programme:dict|None=None, previous_report:dict|None=None)->PlanningAgentResponse:
        r=monthly_review_to_dict(review_monthly_report(report,programme,previous_report))
        return PlanningAgentResponse("monthly_report_review","completed",r,r["inconsistencies"],r["actions"])

    def eot_assessment(self, events:list[dict], claimed_days:float|None=None)->PlanningAgentResponse:
        parsed=[DelayEvent(**e) for e in events]
        r=eot_to_dict(assess_eot(parsed,claimed_days))
        actions=[]
        if r["missing_evidence"]: actions.append("Obtain missing contemporaneous evidence and critical-path substantiation before final technical time assessment.")
        actions.append("Route contractual entitlement to the Commercial Agent; Planning assessment is technical time only.")
        return PlanningAgentResponse("eot_assessment","completed",r,r["missing_evidence"],actions)

def response_to_dict(response:PlanningAgentResponse)->dict:
    return asdict(response)
