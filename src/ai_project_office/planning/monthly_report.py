from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(slots=True)
class MonthlyReportReview:
    extracted: dict
    inconsistencies: list[dict]
    actions: list[str]
    trend: str
    human_decision_required: bool=True

def review_monthly_report(report: dict[str,Any], programme: dict[str,Any]|None=None,
                          previous_report: dict[str,Any]|None=None) -> MonthlyReportReview:
    """Cross-check already-extracted monthly-report facts. Never invent missing values."""
    p=programme or {}; prev=previous_report or {}; issues=[]; actions=[]
    planned=report.get("planned_percent"); actual=report.get("actual_percent")
    if planned is not None and actual is not None:
        report["variance"]=actual-planned
    if p.get("planned_percent") is not None and planned is not None and abs(p["planned_percent"]-planned)>0.01:
        issues.append({"code":"PLANNED_PERCENT_MISMATCH","report":planned,"programme":p["planned_percent"]})
    if p.get("actual_percent") is not None and actual is not None and abs(p["actual_percent"]-actual)>0.01:
        issues.append({"code":"ACTUAL_PERCENT_MISMATCH","report":actual,"programme":p["actual_percent"]})
    rf=report.get("forecast_finish"); pf=p.get("forecast_finish")
    if rf and pf and rf!=pf: issues.append({"code":"FORECAST_FINISH_MISMATCH","report":rf,"programme":pf})
    constraints=set(report.get("constraints") or []); pconstraints=set(p.get("constraints") or [])
    omitted=sorted(pconstraints-constraints)
    if omitted: issues.append({"code":"PROGRAMME_CONSTRAINTS_OMITTED","items":omitted})
    if report.get("recovery_commitment") and not report.get("recovery_basis"):
        issues.append({"code":"UNSUPPORTED_RECOVERY_COMMITMENT"})
    if planned is None or actual is None:
        issues.append({"code":"MISSING_PROGRESS_PERCENTAGE"}); actions.append("Confirm planned and actual progress for the reporting cut-off.")
    prev_var=prev.get("variance")
    cur_var=report.get("variance")
    if prev_var is not None and cur_var is not None:
        if cur_var>prev_var: trend="Recovering"
        elif cur_var<prev_var: trend="Deteriorating"
        else: trend="Maintaining"
    else: trend="Insufficient Data"
    if issues: actions.append("Reconcile monthly-report statements against the controlled programme and supporting records.")
    return MonthlyReportReview(dict(report),issues,actions,trend)

def monthly_review_to_dict(result: MonthlyReportReview)->dict:
    return asdict(result)
