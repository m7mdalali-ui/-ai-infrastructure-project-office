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
