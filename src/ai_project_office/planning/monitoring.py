"""Evidence-led monitoring. Percentages are never inferred from activity counts."""
from __future__ import annotations
from datetime import datetime, timedelta
from .models import Schedule
from .parsers.xer import _date


def activity_dates(activity):
    source=activity.metadata.get('source',{})
    start=_date(source.get('restart_date')) or _date(source.get('early_start_date'))
    finish=_date(source.get('reend_date')) or _date(source.get('early_end_date'))
    if start or finish: return start,finish,'P6 remaining/early dates'
    return activity.planned_start,activity.planned_finish,'source planned dates (forecast not verified)'


def lookahead(schedule: Schedule, *, as_of: datetime, horizon_days: int,
              constraints: dict[str,list[dict]] | None=None) -> dict:
    if horizon_days not in {7,14,30}: raise ValueError('Lookahead must be 7, 14 or 30 days')
    if as_of.tzinfo is not None: raise ValueError('Use project-local naive datetime')
    end=as_of+timedelta(days=horizon_days)
    rows=[]; exceptions=[]
    constraints=constraints or {}
    for aid,a in schedule.activities.items():
        if a.actual_finish: continue
        start,finish,basis=activity_dates(a)
        flags=[]
        if not start or not finish:
            exceptions.append({'code':'MISSING_MONITORING_DATES','activity_id':aid})
        if start and not a.actual_start:
            if start<as_of: flags.append('DELAYED START')
            elif start<end: flags.append('DUE TO START')
        if finish:
            if finish<as_of: flags.append('DELAYED FINISH')
            elif finish<end: flags.append('DUE TO FINISH')
        if flags:
            rows.append({'activity_id':aid,'name':a.name,'start':None if start is None else start.isoformat(),
                         'finish':None if finish is None else finish.isoformat(),'date_basis':basis,
                         'flags':flags,'source_total_float_hours':a.metadata.get('total_float_hours'),
                         'constraints':constraints.get(aid,[]),'constraint_evidence_status':'SUPPLIED' if aid in constraints else 'UNKNOWN'})
    if not constraints: exceptions.append({'code':'SITE_CONSTRAINT_RECORDS_MISSING','description':'Materials, NOCs, inspections, access and resource readiness cannot be verified from schedule dates alone.'})
    return {'project_id':schedule.project_id,'as_of':as_of.isoformat(),'horizon_days':horizon_days,
            'activities':rows,'data_exceptions':exceptions,'human_decision_required':True}


def executive_summary(schedule: Schedule, *, controlled_metrics: dict | None=None) -> dict:
    metrics=dict(controlled_metrics or {})
    # The caller must supply externally calculated/controlled progress and contract dates.
    required=('planned_percent','actual_percent','previous_variance','contract_completion','forecast_completion')
    exceptions=[{'code':'MISSING_CONTROLLED_METRIC','field':key} for key in required if metrics.get(key) is None]
    planned=metrics.get('planned_percent'); actual=metrics.get('actual_percent')
    variance=None if planned is None or actual is None else actual-planned
    prev=metrics.get('previous_variance')
    trend='UNKNOWN' if variance is None or prev is None else ('RECOVERING' if variance>prev else 'DETERIORATING' if variance<prev else 'MAINTAINING')
    critical=[a.id for a in schedule.activities.values() if a.metadata.get('total_float_hours') is not None and a.metadata['total_float_hours']<=0]
    return {'project_id':schedule.project_id,'source_data_date':None if schedule.data_date is None else schedule.data_date.isoformat(),
            'facts':metrics,'calculated_results':{'variance':variance,'trend':trend},
            'source_critical_activity_ids':critical,'critical_path_continuity':'NOT VERIFIED',
            'data_exceptions':exceptions,'human_decision_required':True}
