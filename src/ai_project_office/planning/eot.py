from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Any

@dataclass(slots=True)
class DelayEvent:
    event_id: str
    description: str
    start: date|datetime|None=None
    end: date|datetime|None=None
    notice_ref: str|None=None
    claimed_days: float|None=None
    affected_activities: list[str]|None=None
    evidence_refs: list[str]|None=None
    responsibility: str|None=None
    critical_path_impact_days: float|None=None
    concurrency_days: float|None=None
    mitigation_days: float|None=None
    impact_verified: bool=False

@dataclass(slots=True)
class EOTTechnicalAssessment:
    claimed_days: float|None
    technically_supported_days: float|None
    delay_events: list[dict]
    missing_evidence: list[dict]
    concurrency_identified: bool
    planning_position: str
    commercial_entitlement_required: bool=True
    human_decision_required: bool=True

def assess_eot(events:list[DelayEvent], claimed_days:float|None=None)->EOTTechnicalAssessment:
    missing=[]; supported=0.0; support_complete=True; concurrency=False
    rows=[]
    if len(events)>1:
        # Scalar event impacts cannot demonstrate net project delay or resolve overlap.
        support_complete=False
        missing.append({"missing":"window_based_net_impact","description":"Multiple event impacts must not be summed without a reconciled critical-path/window assessment."})
    for e in events:
        if not e.impact_verified:
            missing.append({"event_id":e.event_id,"missing":"human_verified_technical_impact"})
            support_complete=False
        if not e.evidence_refs or not e.affected_activities:
            support_complete=False
        for value in (e.claimed_days,e.critical_path_impact_days,e.concurrency_days,e.mitigation_days):
            if value is not None and value<0: raise ValueError("Negative delay days")
        if not e.notice_ref: missing.append({"event_id":e.event_id,"missing":"notice_ref"})
        if not e.evidence_refs: missing.append({"event_id":e.event_id,"missing":"contemporaneous_evidence"})
        if not e.affected_activities: missing.append({"event_id":e.event_id,"missing":"affected_activities"})
        if e.critical_path_impact_days is None:
            missing.append({"event_id":e.event_id,"missing":"critical_path_impact"}); support_complete=False
        else:
            conc=max(e.concurrency_days or 0,0); mitigation=max(e.mitigation_days or 0,0)
            concurrency=concurrency or conc>0
            supported += max(e.critical_path_impact_days-conc-mitigation,0)
        rows.append(asdict(e))
    technical=round(supported,3) if support_complete and events else None
    if not events: position="Insufficient Data"
    elif technical is None: position="Technical time impact cannot yet be determined"
    elif claimed_days is not None and technical<claimed_days: position="Claimed time exceeds currently demonstrated technical impact"
    else: position="Technical time impact calculated; contractual entitlement requires Commercial review"
    return EOTTechnicalAssessment(claimed_days,technical,rows,missing,concurrency,position)

def eot_to_dict(result:EOTTechnicalAssessment)->dict:
    return asdict(result)
