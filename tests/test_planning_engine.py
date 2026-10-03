from ai_project_office.planning.models import Activity, Relationship, Schedule
from ai_project_office.planning.cpm import calculate_cpm, NetworkCycleError
from ai_project_office.planning.validation import validate_schedule
from ai_project_office.planning.programme_review import review_programme
import pytest

def sched(acts,rels):
    return Schedule("P1","Test",{a.id:a for a in acts},rels)

def test_simple_fs():
    s=sched([Activity("A","A",5),Activity("B","B",3)],[Relationship("A","B")])
    r=calculate_cpm(s); assert r.project_finish==8; assert set(r.critical_activities)=={"A","B"}

def test_parallel_paths():
    s=sched([Activity("A","A",5),Activity("B","B",3),Activity("C","C",2)],[Relationship("A","C"),Relationship("B","C")])
    r=calculate_cpm(s); assert r.project_finish==7; assert "A" in r.critical_activities; assert "B" not in r.critical_activities

def test_ss():
    s=sched([Activity("A","A",5),Activity("B","B",4)],[Relationship("A","B","SS",2)])
    assert calculate_cpm(s).project_finish==6

def test_ff():
    s=sched([Activity("A","A",5),Activity("B","B",2)],[Relationship("A","B","FF",1)])
    assert calculate_cpm(s).project_finish==6

def test_sf_supported():
    s=sched([Activity("A","A",5),Activity("B","B",2)],[Relationship("A","B","SF",3)])
    assert calculate_cpm(s).project_finish>=5

def test_positive_lag():
    s=sched([Activity("A","A",5),Activity("B","B",2)],[Relationship("A","B","FS",3)])
    assert calculate_cpm(s).project_finish==10

def test_negative_lag():
    s=sched([Activity("A","A",5),Activity("B","B",2)],[Relationship("A","B","FS",-2)])
    assert calculate_cpm(s).project_finish==5

def test_cycle_refused():
    s=sched([Activity("A","A",1),Activity("B","B",1)],[Relationship("A","B"),Relationship("B","A")])
    with pytest.raises(NetworkCycleError): calculate_cpm(s)

def test_broken_relationship_flagged():
    s=sched([Activity("A","A",1)],[Relationship("X","A")])
    assert "BROKEN_REL" in {i.code for i in validate_schedule(s)}

def test_isolated_flagged():
    s=sched([Activity("A","A",1),Activity("B","B",1)],[])
    assert sum(i.code=="ISOLATED" for i in validate_schedule(s))==2

def test_open_ends_flagged():
    s=sched([Activity("A","A",1),Activity("B","B",1)],[Relationship("A","B")])
    codes={i.code for i in validate_schedule(s)}
    assert "OPEN_START" in codes and "OPEN_FINISH" in codes

def test_invalid_progress():
    s=sched([Activity("A","A",1,percent_complete=110)],[])
    assert "INVALID_PROGRESS" in {i.code for i in validate_schedule(s)}

def test_negative_duration():
    s=sched([Activity("A","A",-1)],[])
    assert "NEGATIVE_DURATION" in {i.code for i in validate_schedule(s)}

def test_duplicate_relationship():
    rel=Relationship("A","B")
    s=sched([Activity("A","A",1),Activity("B","B",1)],[rel,rel])
    assert "DUPLICATE_REL" in {i.code for i in validate_schedule(s)}

def test_review_requires_human_decision():
    s=sched([Activity("A","A",1)],[])
    assert review_programme(s).human_decision_required is True

def test_review_revise_on_error():
    s=sched([Activity("A","A",-1)],[])
    assert review_programme(s).recommendation=="Revise & Resubmit"

def test_empty_schedule():
    assert calculate_cpm(sched([],[])).project_finish==0

def test_near_critical():
    s=sched([Activity("A","A",5),Activity("B","B",4),Activity("C","C",1)],[Relationship("A","C"),Relationship("B","C")])
    r=calculate_cpm(s,2); assert "B" in r.near_critical_activities

def test_milestone_zero_duration():
    s=sched([Activity("A","A",2),Activity("M","Milestone",0)],[Relationship("A","M")])
    assert calculate_cpm(s).project_finish==2

def test_relationship_type_invalid():
    s=sched([Activity("A","A",1),Activity("B","B",1)],[Relationship("A","B","XX")])
    assert "INVALID_REL_TYPE" in {i.code for i in validate_schedule(s)}

def test_multiple_critical_paths():
    s=sched([Activity("A","A",2),Activity("B","B",2),Activity("C","C",1),Activity("D","D",1)],[Relationship("A","C"),Relationship("B","D")])
    r=calculate_cpm(s); assert set(r.critical_activities)=={"A","B","C","D"}

def test_source_float_preserved():
    a=Activity("A","A",1,source_total_float=-3)
    calculate_cpm(sched([a],[])); assert a.source_total_float==-3


def test_relationship_preserves_lag_hours():
    r=Relationship("A","B","FS",2.0,16.0)
    assert r.lag==2.0 and r.lag_hours==16.0

def test_baseline_review_marks_cpm_not_calendar_aware():
    from ai_project_office.planning.models import Calendar
    s=sched([Activity("A","A",1)],[])
    s.calendars={"1":Calendar("1","7 day",8,56,"raw")}
    review=review_programme(s,"Baseline")
    assert review.calculated_results["deterministic_network_check"]["calendar_aware"] is False
    assert "CALENDAR_CPM_PENDING" in {x["code"] for x in review.data_exceptions}

def test_xer_parser_uses_activity_calendar_hours(tmp_path):
    from ai_project_office.planning.parsers.xer import parse_xer
    p=tmp_path/"sample.xer"
    p.write_text(
        "%T\tPROJECT\n%F\tproj_id\tproj_short_name\tclndr_id\n%R\t1\tTest\t10\n"
        "%T\tCALENDAR\n%F\tclndr_id\tclndr_name\tday_hr_cnt\tweek_hr_cnt\tclndr_data\n%R\t10\tTen Hour\t10\t70\traw\n"
        "%T\tTASK\n%F\ttask_id\ttask_code\ttask_name\tclndr_id\ttarget_drtn_hr_cnt\tremain_drtn_hr_cnt\tphys_complete_pct\ttotal_float_hr_cnt\n%R\t100\tA\tActivity A\t10\t100\t100\t0\t20\n"
        "%T\tTASKPRED\n%F\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n",
        encoding="utf-8")
    s=parse_xer(p)
    assert s.activities["A"].duration==10
    assert s.activities["A"].source_total_float==2
    assert s.calendars["10"].hours_per_day==10


def test_calendar_profile_detects_weekly_hours():
    from ai_project_office.planning.parsers.xer import _calendar_profile
    raw="DaysOfWeek() (0||1()(0||0(s|08:00|f|16:00)())) (0||2()(0||0(s|08:00|f|16:00)())) VIEW("
    assert _calendar_profile(raw)["parsed_weekly_hours"]==16

def test_calendar_hours_mismatch_is_flagged():
    from ai_project_office.planning.models import Calendar
    s=sched([Activity("A","A",1)],[])
    s.calendars={"1":Calendar("1","Named 7 days",8,40,"raw",{"parsed_weekly_hours":56,"exception_count":0})}
    review=review_programme(s,"Baseline")
    assert "CALENDAR_HOURS_MISMATCH" in {x["code"] for x in review.data_exceptions}


def test_xer_parser_preserves_wbs_and_activity_codes(tmp_path):
    from ai_project_office.planning.parsers.xer import parse_xer
    p=tmp_path/"codes.xer"
    p.write_text(
        "%T\tPROJECT\n%F\tproj_id\tproj_short_name\n%R\t1\tTest\n"
        "%T\tPROJWBS\n%F\twbs_id\twbs_short_name\twbs_name\tparent_wbs_id\n%R\t20\tUTIL\tUtilities\t\n"
        "%T\tACTVTYPE\n%F\tactv_code_type_id\tactv_code_type\n%R\t30\tDiscipline\n"
        "%T\tACTVCODE\n%F\tactv_code_id\tactv_code_type_id\tactv_code_name\tshort_name\n%R\t40\t30\tChilled Water\tCHW\n"
        "%T\tTASK\n%F\ttask_id\ttask_code\ttask_name\twbs_id\ttarget_drtn_hr_cnt\n%R\t100\tA\tInstall pipe\t20\t8\n"
        "%T\tTASKACTV\n%F\ttask_id\tactv_code_type_id\tactv_code_id\n%R\t100\t30\t40\n"
        "%T\tTASKPRED\n%F\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n",
        encoding="utf-8")
    s=parse_xer(p)
    assert s.activities["A"].metadata["wbs_name"]=="Utilities"
    assert s.activities["A"].metadata["activity_codes"][0]["code"]=="CHW"
    assert s.metadata["wbs_records"]["20"]["short_name"]=="UTIL"
