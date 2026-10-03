"""Independent baseline CPM, explicitly not P6-equivalent.
Lag calendar policy must be supplied; progressed schedules and unimplemented
P6 constraint/task types are refused instead of approximated silently.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from .calendars import CalendarError, resolve_calendars
from .cpm import NetworkCycleError
from .models import Schedule

@dataclass
class CalculatedActivity:
    start: datetime
    finish: datetime
    late_start: datetime | None = None
    late_finish: datetime | None = None
    total_float_hours: float | None = None
    free_float_hours: float | None = None
    critical: bool = False

@dataclass
class CalendarCPMResult:
    project_finish: datetime
    activities: dict[str, CalculatedActivity]
    calendar_aware: bool = True
    p6_equivalent: bool = False
    assumptions: list[str] = field(default_factory=list)
    data_exceptions: list[dict] = field(default_factory=list)


def calculate_calendar_cpm(schedule: Schedule, *, project_start: datetime,
                           lag_calendar_policy: str,
                           required_finish: datetime | None = None) -> CalendarCPMResult:
    if lag_calendar_policy not in {'predecessor','successor'}:
        raise ValueError('Explicit predecessor/successor lag calendar policy required')
    if not schedule.activities: raise ValueError('Empty schedule')
    calendars = resolve_calendars(schedule.calendars)
    acts = schedule.activities
    succ = {i:[] for i in acts}; pred = {i:[] for i in acts}
    indeg = {i:0 for i in acts}; duration = {}; cal = {}
    for i,a in acts.items():
        if a.actual_start or a.actual_finish or a.percent_complete or a.metadata.get('status') not in {None,'','TK_NotStart'}:
            raise ValueError('Progressed scheduling is not implemented: '+i)
        if a.metadata.get('constraint_type') or a.metadata.get('constraint_type_2') or a.constraint_date:
            raise ValueError('Constraint semantics are not yet implemented: '+i)
        if a.metadata.get('task_type') not in {None,'','TT_Task','TT_Rsrc','TT_Mile','TT_StartMile','TT_FinMile'}:
            raise ValueError('Unsupported task type: '+i)
        if a.metadata.get('task_type') == 'TT_Rsrc':
            raise ValueError('Resource-dependent scheduling is not implemented: '+i)
        if a.calendar_id not in calendars: raise CalendarError('Missing activity calendar: '+i)
        cal[i] = calendars[a.calendar_id]
        hours = a.metadata.get('target_duration_hours')
        if hours is None:
            hpd = schedule.calendars[a.calendar_id].hours_per_day
            if hpd is None: raise CalendarError('No documented duration conversion: '+i)
            hours = a.duration*hpd
        if hours < 0: raise ValueError('Negative duration: '+i)
        if a.metadata.get('task_type') in {'TT_Mile','TT_StartMile','TT_FinMile'} and hours:
            raise ValueError('Milestone has nonzero duration: '+i)
        duration[i] = hours
    for r in schedule.relationships:
        if r.predecessor_id not in acts or r.successor_id not in acts:
            raise ValueError('Broken relationship; calculation refused')
        if r.type not in {'FS','SS','FF','SF'}: raise ValueError('Unsupported relationship type')
        if r.lag_hours is None: raise ValueError('Explicit relationship lag hours required')
        succ[r.predecessor_id].append(r); pred[r.successor_id].append(r); indeg[r.successor_id]+=1
    queue=deque(sorted(i for i in acts if not indeg[i])); order=[]
    while queue:
        i=queue.popleft(); order.append(i)
        for r in succ[i]:
            indeg[r.successor_id]-=1
            if not indeg[r.successor_id]: queue.append(r.successor_id)
    if len(order)!=len(acts): raise NetworkCycleError('Circular logic; calculation refused')
    rows={}
    def lagcal(r): return cal[r.predecessor_id if lag_calendar_policy=='predecessor' else r.successor_id]
    def bound(r, p):
        anchor=p.finish if r.type[0]=='F' else p.start
        return lagcal(r).add_working_hours(anchor,r.lag_hours)
    for i in order:
        start = cal[i].next_working_time(project_start)
        for r in pred[i]:
            limit=bound(r,rows[r.predecessor_id])
            candidate=limit if r.type[1]=='S' else cal[i].subtract_working_hours(limit,duration[i])
            start=max(start,candidate)
        if duration[i]: start=cal[i].next_working_time(start)
        rows[i]=CalculatedActivity(start,cal[i].add_working_hours(start,duration[i]))
    finish=max(x.finish for x in rows.values())
    deadline=required_finish or finish
    for i in reversed(order):
        latest=cal[i].subtract_working_hours(deadline,duration[i])
        for r in succ[i]:
            s=rows[r.successor_id]
            anchor=s.late_start if r.type[1]=='S' else s.late_finish
            limit=lagcal(r).subtract_working_hours(anchor,r.lag_hours)
            candidate=cal[i].subtract_working_hours(limit,duration[i]) if r.type[0]=='F' else limit
            latest=min(latest,candidate)
        row=rows[i]
        row.late_start=latest
        row.late_finish=cal[i].add_working_hours(latest,duration[i])
        row.total_float_hours=cal[i].working_hours_between(row.start,latest)
        row.critical=row.total_float_hours<=1e-7
        row.free_float_hours=min((cal[i].working_hours_between(bound(r,row),
            rows[r.successor_id].start if r.type[1]=='S' else rows[r.successor_id].finish)
            for r in succ[i]),default=cal[i].working_hours_between(row.finish,finish))
    return CalendarCPMResult(finish,rows,assumptions=[
        'Baseline only; no resource leveling; project-local wall time.',
        'Lag calendar policy: '+lag_calendar_policy+'; requires human confirmation.'],
        data_exceptions=[issue for c in calendars.values() for issue in c.issues])
