from datetime import date, datetime, timedelta
import pytest
from ai_project_office.planning.models import Calendar, Activity, Relationship, Schedule
from ai_project_office.planning.calendars import WorkingCalendar, CalendarError, parse_calendar, resolve_calendars
from ai_project_office.planning.calendar_cpm import calculate_calendar_cpm
from ai_project_office.planning.reconciliation import reconcile_p6
from ai_project_office.planning.parsers.xer import parse_xer


def raw_calendar(week, exceptions=()):
    def shifts(periods):
        return ''.join(f'(0||{n}(s|{a}|f|{b})())' for n,(a,b) in enumerate(periods))
    days=''.join(f'(0||{d}()({shifts(periods)}))' for d,periods in week.items())
    ex=''.join(f'(0||{n}(d|{(d-date(1899,12,30)).days})({shifts(p)}))' for n,(d,p) in enumerate(exceptions))
    return f'(0||CalendarData()((0||DaysOfWeek()({days}))(0||Exceptions()({ex}))))'


def source_calendar(days=5, hours=8):
    week={d: [('08:00',f'{8+hours:02d}:00')] if d in range(2,2+days) or days==7 else [] for d in range(1,8)}
    # Six-day week Monday through Saturday.
    if days==6: week[7]=[('08:00',f'{8+hours:02d}:00')]
    return Calendar('C','Deliberately misleading name',hours,days*hours,raw_calendar(week))

@pytest.mark.parametrize('days,hours',[(5,8),(6,10),(7,10)])
def test_weekly_profiles(days,hours):
    c=parse_calendar(source_calendar(days,hours))
    assert c.weekly_hours==days*hours
    assert c.is_working_time(datetime(2026,1,5,9))
    assert c.is_working_time(datetime(2026,1,4,9))==(days==7)


def test_split_shift_and_holiday():
    c=WorkingCalendar('C',{i:((7*60,12*60),(13*60,18*60)) for i in range(5)},
                      {date(2026,1,6):()})
    assert c.add_working_hours(datetime(2026,1,5,7),15)==datetime(2026,1,7,12)
    assert not c.is_working_time(datetime(2026,1,5,12,30))
    assert c.subtract_working_hours(datetime(2026,1,7,12),15)==datetime(2026,1,5,7)
    assert c.working_hours_between(datetime(2026,1,5,7),datetime(2026,1,7,12))==15
    assert c.working_hours_between(datetime(2026,1,7,12),datetime(2026,1,5,7))==-15


def test_working_and_nonworking_exceptions():
    s=source_calendar()
    s.raw_data=raw_calendar({d:[('08:00','16:00')] if d in range(2,7) else [] for d in range(1,8)},
                           [(date(2026,1,4),[('09:00','12:00')]),(date(2026,1,5),[])])
    c=parse_calendar(s)
    assert c.add_working_hours(datetime(2026,1,4,9),4)==datetime(2026,1,6,9)
    assert c.is_working_time(datetime(2026,1,4,10))
    assert not c.is_working_time(datetime(2026,1,5,10))


def test_friday_nonworking():
    c=WorkingCalendar('C',{i:((480,960),) if i!=4 else () for i in range(7)})
    assert c.add_working_hours(datetime(2026,1,8,8),9)==datetime(2026,1,10,9)


def test_calendar_conflict_is_recorded():
    s=source_calendar(7,8); s.hours_per_week=40
    assert parse_calendar(s).issues[0]['code']=='CALENDAR_HOURS_MISMATCH'


def test_inheritance():
    base=source_calendar()
    child=Calendar('D','child',8,40,'(0||CalendarData()((0||Exceptions()((0||0(d|46027)())))))',{'base_calendar_id':'C'})
    c=resolve_calendars({'C':base,'D':child})['D']
    assert c.week==parse_calendar(base).week
    assert len(c.exceptions)==1


def test_circular_calendar_inheritance():
    a=source_calendar(); a.metadata['base_calendar_id']='C'
    with pytest.raises(CalendarError): resolve_calendars({'C':a})

@pytest.mark.parametrize('raw',['raw','(0||CalendarData()(',raw_calendar({1:[('08:00','16:00'),('15:00','18:00')]}),raw_calendar({1:[('22:00','06:00')]})])
def test_invalid_calendars_refused(raw):
    with pytest.raises(CalendarError): parse_calendar(Calendar('C','x',raw_data=raw))


def test_shift_boundaries_and_zero():
    c=parse_calendar(source_calendar())
    end=datetime(2026,1,5,16)
    assert c.next_working_time(end)==datetime(2026,1,6,8)
    assert c.previous_working_time(datetime(2026,1,6,8))==end
    assert c.add_working_hours(end,0)==end
    assert c.add_working_hours(end,-8)==datetime(2026,1,5,8)


def network(rel='FS',lag=0,calendar_b=None):
    ca=source_calendar()
    calendars={'C':ca}
    if calendar_b: calendars[calendar_b.id]=calendar_b
    return Schedule('P','Synthetic',{'A':Activity('A','A',1,calendar_id='C',metadata={'target_duration_hours':8}),
        'B':Activity('B','B',1,calendar_id=calendar_b.id if calendar_b else 'C',metadata={'target_duration_hours':8})},
        [Relationship('A','B',rel,lag/8,lag)],calendars=calendars)

@pytest.mark.parametrize('rel,lag,start,finish',[
    ('FS',0,(6,8),(6,16)),('FS',8,(7,8),(7,16)),('FS',-4,(5,12),(6,12)),
    ('SS',4,(5,12),(6,12)),('FF',4,(5,12),(6,12)),('SF',8,(5,8),(5,16))])
def test_calendar_relationships(rel,lag,start,finish):
    s=network(rel,lag)
    r=calculate_calendar_cpm(s,project_start=datetime(2026,1,5,8),lag_calendar_policy='predecessor')
    b=r.activities['B']
    assert b.start==datetime(2026,1,start[0],start[1])
    assert b.finish==datetime(2026,1,finish[0],finish[1])
    assert r.p6_equivalent is False
    assert s.activities['A'].es is None


def test_multiple_calendars():
    cb=source_calendar(7,10); cb.id='D'
    s=network('FS',0,cb)
    r=calculate_calendar_cpm(s,project_start=datetime(2026,1,9,8),lag_calendar_policy='predecessor')
    assert r.activities['B'].finish==datetime(2026,1,10,14)


def test_negative_float_and_milestone():
    s=network(); s.activities['B'].metadata.update(target_duration_hours=0,task_type='TT_FinMile')
    r=calculate_calendar_cpm(s,project_start=datetime(2026,1,5,8),lag_calendar_policy='predecessor',required_finish=datetime(2026,1,5,12))
    assert r.activities['A'].total_float_hours==-4
    assert r.activities['B'].finish==r.activities['B'].start

@pytest.mark.parametrize('change',[{'actual_start':datetime(2026,1,5,8)},{'constraint_date':datetime(2026,1,5,8)}])
def test_unsupported_scheduling_refused(change):
    s=network()
    for key,value in change.items(): setattr(s.activities['A'],key,value)
    with pytest.raises(ValueError): calculate_calendar_cpm(s,project_start=datetime(2026,1,5,8),lag_calendar_policy='predecessor')


def test_reconciliation_does_not_use_target_dates():
    s=network()
    r=calculate_calendar_cpm(s,project_start=datetime(2026,1,5,8),lag_calendar_policy='predecessor')
    assert reconcile_p6(s,r)[0]['classification']=='CALCULATION NOT COMPARABLE'
    s.activities['A'].metadata.update(source={'early_start_date':'2026-01-05 08:00','early_end_date':'2026-01-05 16:00'},total_float_hours=0)
    assert reconcile_p6(s,r)[0]['classification']=='MATCH'


def write_xer(tmp_path,tasks,projects='1\tP'):
    p=tmp_path/'synthetic.xer'
    p.write_text('%T\tPROJECT\n%F\tproj_id\tproj_short_name\n'+''.join('%R\t'+row+'\n' for row in projects.split('\n'))+
                 '%T\tTASK\n%F\ttask_id\ttask_code\ttask_name\tproj_id\tphys_complete_pct\ttarget_drtn_hr_cnt\n'+tasks)
    return p


def test_small_physical_progress_not_multiplied(tmp_path):
    s=parse_xer(write_xer(tmp_path,'%R\t1\tA\tA\t1\t0.5\t8\n'))
    assert s.activities['A'].percent_complete==0.5
    assert s.activities['A'].metadata['target_duration_hours']==8
    assert s.activities['A'].metadata['duration_conversion_available'] is False
    assert s.metadata['data_exceptions'][0]['code']=='MISSING_DURATION_CONVERSION'


def test_mult_project_requires_selection(tmp_path):
    p=write_xer(tmp_path,'%R\t1\tA\tA\t1\t0\t8\n%R\t2\tB\tB\t2\t0\t8\n','1\tP\n2\tQ')
    with pytest.raises(ValueError): parse_xer(p)
    assert set(parse_xer(p,project_id='2').activities)=={'B'}


def test_duplicate_codes_refused(tmp_path):
    p=write_xer(tmp_path,'%R\t1\tA\tA\t1\t0\t8\n%R\t2\tA\tB\t1\t0\t8\n')
    with pytest.raises(ValueError): parse_xer(p)


def test_broken_xer_relationship_preserved(tmp_path):
    p=write_xer(tmp_path,'%R\t1\tA\tA\t1\t0\t8\n')
    with p.open('a') as f:
        f.write('%T\tTASKPRED\n%F\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n%R\t1\t999\tPR_FS\t0\n')
    s=parse_xer(p)
    assert len(s.relationships)==1
    assert any(e['code']=='UNRESOLVED_RELATIONSHIP' for e in s.metadata['data_exceptions'])


def test_progress_comparison_new_fields():
    from ai_project_office.planning.progress import compare_programmes
    b=network(); u=network()
    u.activities['A'].calendar_id='D'
    u.activities['A'].metadata['constraint_type']='CS_MSO'
    r=compare_programmes(b,u)
    assert r.activity_changes[0]['calendar_id']=={'baseline':'C','update':'D'}
    assert 'constraint_type' in r.activity_changes[0]


def test_100_crews_do_not_override_material_ceiling():
    from ai_project_office.planning.recovery import analyse_recovery
    inputs=dict(remaining_quantity=1200,target_date=date(2026,1,10),start_date=date(2026,1,1),
                production_per_crew_per_day=20,material_cap_per_day=60,testing_days=2)
    low=analyse_recovery(**inputs,available_crews=3)
    high=analyse_recovery(**inputs,available_crews=100)
    assert high.practical_resource_ceiling==3
    assert high.earliest_achievable_finish==low.earliest_achievable_finish=='2026-01-22'
    assert high.recoverable_by_target is False
    assert high.recoverability_date=='2025-12-20'


def test_zero_crews_and_gate():
    from ai_project_office.planning.recovery import analyse_recovery
    r=analyse_recovery(remaining_quantity=100,start_date=date(2026,1,1),target_date=date(2026,1,10),
                      production_per_crew_per_day=20,available_crews=0,material_available_date=date(2026,1,5))
    assert r.earliest_achievable_finish is None
    assert r.recoverable_by_target is False
    assert r.available_days==6


def test_recovery_nonworking_days_sequence_and_testing():
    from ai_project_office.planning.recovery import analyse_recovery
    r=analyse_recovery(remaining_quantity=80,start_date=date(2026,1,9),target_date=date(2026,1,20),
                      production_per_crew_per_day=40,available_crews=10,sequence_cap_per_day=20,
                      testing_days=2,working_weekdays=(0,1,2,3,4))
    assert r.earliest_achievable_finish=='2026-01-16'
    assert r.practical_resource_ceiling==1


def test_eot_unverified_claimed_impact_not_supported():
    from ai_project_office.planning.eot import assess_eot, DelayEvent
    r=assess_eot([DelayEvent('E','event',critical_path_impact_days=10)])
    assert r.technically_supported_days is None


def test_eot_multiple_event_days_not_summed():
    from ai_project_office.planning.eot import assess_eot, DelayEvent
    events=[DelayEvent(str(i),'event',evidence_refs=['R'],affected_activities=['A'],
                       critical_path_impact_days=10,impact_verified=True) for i in range(2)]
    assert assess_eot(events).technically_supported_days is None


def test_monthly_source_not_overwritten():
    from ai_project_office.planning.monthly_report import review_monthly_report
    report={'planned_percent':50,'actual_percent':40,'variance':1}
    r=review_monthly_report(report)
    assert report['variance']==1
    assert r.extracted['variance']==1
    assert r.extracted['calculated_variance']==-10
    assert any(i['code']=='REPORTED_VARIANCE_MISMATCH' for i in r.inconsistencies)


def test_partial_cost_loading():
    from ai_project_office.planning.baseline import assess_baseline
    s=network(); s.metadata.update(resource_assignment_count=10,cost_assignment_count=1,target_cost_sum=100)
    assert assess_baseline(s).loading['status']=='partially_cost_loaded'


def test_agent_calendar_calculation_blocks_unsupported_file(tmp_path):
    from ai_project_office.planning.api import run_planning_task
    p=write_xer(tmp_path,'%R\t1\tA\tA\t1\t0\t8\n')
    r=run_planning_task('calendar_reconciliation',path=p,project_start=datetime(2026,1,5),lag_calendar_policy='predecessor')
    assert r['status']=='blocked'
    assert r['human_decision_required']


@pytest.mark.parametrize('horizon',[7,14,30])
def test_lookahead_source_dates_and_readiness(horizon):
    from ai_project_office.planning.monitoring import lookahead
    s=network()
    s.activities['A'].metadata['source']={'early_start_date':'2026-01-05 08:00','early_end_date':'2026-01-06 16:00'}
    r=lookahead(s,as_of=datetime(2026,1,6,8),horizon_days=horizon)
    assert r['activities'][0]['flags']==['DELAYED START','DUE TO FINISH']
    assert r['activities'][0]['constraint_evidence_status']=='UNKNOWN'
    assert any(x['code']=='SITE_CONSTRAINT_RECORDS_MISSING' for x in r['data_exceptions'])


def test_executive_summary_missing_progress_stays_unknown():
    from ai_project_office.planning.monitoring import executive_summary
    r=executive_summary(network())
    assert r['calculated_results']=={'variance':None,'trend':'UNKNOWN'}
    assert len(r['data_exceptions'])==5


def test_executive_summary_trend_calculated_from_controlled_input():
    from ai_project_office.planning.monitoring import executive_summary
    metrics={'planned_percent':50,'actual_percent':40,'previous_variance':-15}
    r=executive_summary(network(),controlled_metrics=metrics)
    assert r['calculated_results']=={'variance':-10,'trend':'RECOVERING'}
    assert metrics=={'planned_percent':50,'actual_percent':40,'previous_variance':-15}
