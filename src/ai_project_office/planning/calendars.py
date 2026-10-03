"""P6 detailed calendars. Naive datetimes represent project-local wall time.
No calendar-name inference. Intervals are half-open; finishes may equal shift end.
P6 day 1 is Sunday. Exception dates are OLE days from 1899-12-30.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import math
import re

class CalendarError(ValueError):
    pass

def _nodes(text: str) -> list[str]:
    depth = 0
    start = 0
    nodes = []
    for i, ch in enumerate(text):
        if ch == '(':
            if depth == 0: start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0: raise CalendarError('Unbalanced clndr_data')
            if depth == 0: nodes.append(text[start:i+1])
    if depth: raise CalendarError('Unbalanced clndr_data')
    return nodes

def _section(raw: str, name: str) -> str | None:
    marker = name + '()('
    pos = raw.find(marker)
    if pos < 0: return None
    start = pos + len(marker) - 1
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == '(': depth += 1
        elif raw[i] == ')':
            depth -= 1
            if depth == 0: return raw[start+1:i]
    raise CalendarError('Unbalanced calendar section ' + name)

def _periods(node: str) -> tuple[tuple[int, int], ...]:
    pairs = re.findall(r's\|(\d{2}:\d{2})\|f\|(\d{2}:\d{2})', node)
    result = []
    for s, f in pairs:
        def minute(v):
            h, m = map(int, v.split(':'))
            if m >= 60 or h > 24 or (h == 24 and m): raise CalendarError('Invalid shift time')
            return h * 60 + m
        a, b = minute(s), minute(f)
        if b <= a: raise CalendarError('Overnight/zero shift requires explicit split at midnight')
        result.append((a, b))
    result.sort()
    if any(b > c for (_, b), (c, _) in zip(result, result[1:])):
        raise CalendarError('Overlapping work periods')
    if 's|' in node and not pairs: raise CalendarError('Malformed shift')
    return tuple(result)

@dataclass
class WorkingCalendar:
    id: str
    week: dict[int, tuple[tuple[int, int], ...]]
    exceptions: dict[date, tuple[tuple[int, int], ...]] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    search_days: int = 36600

    @property
    def weekly_hours(self) -> float:
        return sum(b-a for periods in self.week.values() for a,b in periods)/60

    def intervals(self, day: date) -> list[tuple[datetime, datetime]]:
        periods = self.exceptions.get(day, self.week.get(day.weekday(), ()))
        origin = datetime.combine(day, datetime.min.time())
        return [(origin+timedelta(minutes=a), origin+timedelta(minutes=b)) for a,b in periods]

    def is_working_time(self, value: datetime) -> bool:
        self._check(value)
        return any(a <= value < b for a,b in self.intervals(value.date()))

    def _check(self, value: datetime):
        if value.tzinfo is not None: raise CalendarError('Use project-local naive datetime')

    def next_working_time(self, value: datetime) -> datetime:
        self._check(value)
        for n in range(self.search_days):
            for a,b in self.intervals(value.date()+timedelta(days=n)):
                if b > value: return max(a,value)
        raise CalendarError('No working time inside search horizon')

    def previous_working_time(self, value: datetime) -> datetime:
        self._check(value)
        for n in range(self.search_days):
            for a,b in reversed(self.intervals(value.date()-timedelta(days=n))):
                if a < value: return min(b,value)
        raise CalendarError('No previous working time inside search horizon')

    def add_working_hours(self, value: datetime, hours: float) -> datetime:
        if not math.isfinite(hours): raise CalendarError('Hours must be finite')
        self._check(value)
        if hours < 0: return self.subtract_working_hours(value, -hours)
        if hours == 0: return value
        cursor = value
        remaining = hours * 3600
        for _ in range(self.search_days*24):
            cursor = self.next_working_time(cursor)
            end = next(b for a,b in self.intervals(cursor.date()) if a <= cursor < b)
            available = (end-cursor).total_seconds()
            if remaining <= available+1e-8: return cursor+timedelta(seconds=remaining)
            remaining -= available
            cursor = end
        raise CalendarError('Working duration exceeds search horizon')

    def subtract_working_hours(self, value: datetime, hours: float) -> datetime:
        if not math.isfinite(hours): raise CalendarError('Hours must be finite')
        self._check(value)
        if hours < 0: return self.add_working_hours(value, -hours)
        if hours == 0: return value
        cursor = value
        remaining = hours * 3600
        for _ in range(self.search_days*24):
            cursor = self.previous_working_time(cursor)
            start = next(a for a,b in self.intervals(cursor.date()) if a < cursor <= b)
            available = (cursor-start).total_seconds()
            if remaining <= available+1e-8: return cursor-timedelta(seconds=remaining)
            remaining -= available
            cursor = start
        raise CalendarError('Working duration exceeds search horizon')

    def working_hours_between(self, start: datetime, finish: datetime) -> float:
        self._check(start); self._check(finish)
        if finish < start: return -self.working_hours_between(finish,start)
        days = (finish.date()-start.date()).days
        if days > self.search_days: raise CalendarError('Interval exceeds search horizon')
        return sum(max(0,(min(b,finish)-max(a,start)).total_seconds())
                   for n in range(days+1) for a,b in self.intervals(start.date()+timedelta(days=n)))/3600

def parse_calendar(calendar, base: WorkingCalendar | None = None) -> WorkingCalendar:
    raw = calendar.raw_data or ''
    # Validate entire grammar's balanced delimiters before extracting sections.
    _nodes(raw)
    section = _section(raw,'DaysOfWeek')
    week = dict(base.week) if base else {}
    if section is not None:
        for node in _nodes(section):
            match = re.match(r'\(\d+\|\|([1-7])\(\)',node)
            if not match: raise CalendarError('Unsupported weekday record')
            day = (int(match[1])+5)%7
            if day in week and not base: raise CalendarError('Duplicate weekday')
            week[day] = _periods(node)
    if set(week) != set(range(7)): raise CalendarError('Incomplete weekly calendar; base required')
    exceptions = dict(base.exceptions) if base else {}
    section = _section(raw,'Exceptions')
    if section is not None:
        seen = set()
        for node in _nodes(section):
            match = re.search(r'\(d\|(-?\d+)\)',node)
            if not match: raise CalendarError('Unsupported exception date')
            day = date(1899,12,30)+timedelta(days=int(match[1]))
            if day in seen: raise CalendarError('Duplicate exception date')
            seen.add(day)
            exceptions[day] = _periods(node)
    result = WorkingCalendar(calendar.id,week,exceptions)
    if calendar.hours_per_week is not None and abs(calendar.hours_per_week-result.weekly_hours)>0.01:
        result.issues.append({'code':'CALENDAR_HOURS_MISMATCH','calendar_id':calendar.id,
                             'source_weekly_hours':calendar.hours_per_week,'detailed_weekly_hours':result.weekly_hours})
    return result

def resolve_calendars(calendars) -> dict[str, WorkingCalendar]:
    result = {}
    visiting = set()
    def resolve(cid):
        if cid in result: return result[cid]
        if cid in visiting: raise CalendarError('Circular base-calendar inheritance')
        if cid not in calendars: raise CalendarError('Missing base calendar '+cid)
        visiting.add(cid)
        source = calendars[cid]
        base_id = source.metadata.get('base_calendar_id')
        base = resolve(base_id) if base_id and base_id != '0' else None
        result[cid] = parse_calendar(source,base)
        visiting.remove(cid)
        return result[cid]
    for cid in calendars: resolve(cid)
    return result
