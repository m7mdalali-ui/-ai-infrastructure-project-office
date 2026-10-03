from __future__ import annotations
from datetime import datetime
from pathlib import Path
import re
from ..models import Activity, Calendar, Relationship, Schedule

_DATE_FORMATS=("%Y-%m-%d %H:%M","%Y-%m-%d %H:%M:%S","%Y-%m-%d")

def _float(value, default=None):
    try: return float(value)
    except (TypeError,ValueError): return default

def _date(value):
    if not value: return None
    for fmt in _DATE_FORMATS:
        try: return datetime.strptime(value,fmt)
        except ValueError: pass
    return None

def _calendar_profile(raw: str|None) -> dict:
    """Extract auditable weekly work hours and exception count from P6 clndr_data.
    This does not yet perform date arithmetic; it exposes source-calendar quality safely.
    """
    if not raw: return {"parsed_weekly_hours":None,"exception_count":0}
    weekly=0.0
    days=re.search(r"DaysOfWeek\(\)(.*?)(?:VIEW\(|Exceptions\()",raw,re.S)
    if days:
        for start,finish in re.findall(r"s\|(\d\d:\d\d)\|f\|(\d\d:\d\d)",days.group(1)):
            sh,sm=map(int,start.split(":")); fh,fm=map(int,finish.split(":"))
            weekly += (fh+fm/60)-(sh+sm/60)
    exceptions=len(re.findall(r"\(d\|\d+\)",raw))
    return {"parsed_weekly_hours":weekly,"exception_count":exceptions}

def _read_tables(path: str|Path) -> dict[str,list[dict[str,str]]]:
    tables={}; table=None; fields=[]
    for raw in Path(path).read_text(encoding="utf-8",errors="replace").splitlines():
        parts=raw.split("\t")
        if not parts: continue
        if parts[0]=="%T" and len(parts)>1:
            table=parts[1]; tables.setdefault(table,[])
        elif parts[0]=="%F":
            fields=parts[1:]
        elif parts[0]=="%R" and table:
            tables[table].append(dict(zip(fields,parts[1:])))
    return tables

def parse_xer(path: str|Path, *, project_id: str | None = None) -> Schedule:
    tables=_read_tables(path)
    projects=tables.get("PROJECT",[])
    if len(projects)>1 and project_id is None:
        raise ValueError("Multi-project XER requires explicit project_id; import refused to prevent project mixing.")
    selected=[r for r in projects if project_id is None or r.get("proj_id")==project_id]
    if not selected: raise ValueError("Selected project not found in XER")
    proj=selected[0]
    pid=proj.get("proj_id")
    tables={k:[r for r in rows if not r.get("proj_id") or r.get("proj_id")==pid]
            for k,rows in tables.items()}
    if len(projects)>1:
        tasks=tables.get("TASK",[])
        if any(not r.get("proj_id") for r in tasks):
            raise ValueError("Unscoped TASK records in multi-project XER; isolation cannot be verified")
        task_ids={r.get("task_id") for r in tasks}
        tables["TASKACTV"]=[r for r in tables.get("TASKACTV",[]) if r.get("task_id") in task_ids]
        tables["TASKRSRC"]=[r for r in tables.get("TASKRSRC",[]) if r.get("task_id") in task_ids]
        resource_ids={r.get("rsrc_id") for r in tables["TASKRSRC"]}
        tables["RSRC"]=[r for r in tables.get("RSRC",[]) if r.get("rsrc_id") in resource_ids]
        code_ids={r.get("actv_code_id") for r in tables["TASKACTV"]}
        tables["ACTVCODE"]=[r for r in tables.get("ACTVCODE",[]) if r.get("actv_code_id") in code_ids]
        type_ids={r.get("actv_code_type_id") for r in tables["ACTVCODE"]}
        tables["ACTVTYPE"]=[r for r in tables.get("ACTVTYPE",[]) if r.get("actv_code_type_id") in type_ids]
        tables["TASKPRED"]=[r for r in tables.get("TASKPRED",[]) if r.get("task_id") in task_ids]
        calendar_ids={r.get("clndr_id") for r in tasks} | {proj.get("clndr_id")}
        calendar_lookup={r.get("clndr_id"):r for r in tables.get("CALENDAR",[])}
        pending=list(calendar_ids)
        while pending:
            base=calendar_lookup.get(pending.pop(),{}).get("base_clndr_id")
            if base and base!="0" and base not in calendar_ids:
                calendar_ids.add(base);pending.append(base)
        tables["CALENDAR"]=[r for r in tables.get("CALENDAR",[]) if r.get("clndr_id") in calendar_ids]
        # Unknown global tables may contain another project's information; only
        # explicitly scoped P6 tables are retained for multi-project exports.
        allowed={"PROJECT","TASK","TASKPRED","TASKACTV","TASKRSRC","RSRC","ACTVCODE","ACTVTYPE","CALENDAR","PROJWBS"}
        tables={k:v for k,v in tables.items() if k in allowed}
    exceptions=[]

    calendars={}
    for r in tables.get("CALENDAR",[]):
        cid=r.get("clndr_id")
        if not cid: continue
        raw=r.get("clndr_data")
        profile=_calendar_profile(raw)
        calendars[cid]=Calendar(
            id=cid,name=r.get("clndr_name",""),
            hours_per_day=_float(r.get("day_hr_cnt")),
            hours_per_week=_float(r.get("week_hr_cnt")),
            raw_data=raw,
            metadata={"type":r.get("clndr_type"),"base_calendar_id":r.get("base_clndr_id"),**profile,"source":dict(r)}
        )

    wbs={r.get("wbs_id"):r for r in tables.get("PROJWBS",[]) if r.get("wbs_id")}
    code_types={r.get("actv_code_type_id"):r for r in tables.get("ACTVTYPE",[]) if r.get("actv_code_type_id")}
    codes={r.get("actv_code_id"):r for r in tables.get("ACTVCODE",[]) if r.get("actv_code_id")}
    task_codes={}
    for r in tables.get("TASKACTV",[]):
        c=codes.get(r.get("actv_code_id"),{}); ct=code_types.get(r.get("actv_code_type_id"),{})
        task_codes.setdefault(r.get("task_id"),[]).append({"type":ct.get("actv_code_type"),"code":c.get("short_name"),"name":c.get("actv_code_name")})
    activities={}
    internal_to_code={}
    for r in tables.get("TASK",[]):
        aid=r.get("task_code") or r.get("task_id")
        if not aid: continue
        cid=r.get("clndr_id")
        hpd=(calendars.get(cid).hours_per_day if cid in calendars else None) or None
        target_h=_float(r.get("target_drtn_hr_cnt"),0.0) or 0.0
        remain_h=_float(r.get("remain_drtn_hr_cnt"))
        source_tf_h=_float(r.get("total_float_hr_cnt"))
        pc=_float(r.get("phys_complete_pct"),0.0) or 0.0
        if hpd is None:
            exceptions.append({"code":"MISSING_DURATION_CONVERSION","activity_id":aid,"calendar_id":cid})
        if aid in activities:
            raise ValueError("Duplicate activity code in selected project: "+aid)
        a=Activity(
            id=aid,name=r.get("task_name",""),duration=(target_h/hpd if hpd else 0.0),
            remaining_duration=(remain_h/hpd if remain_h is not None and hpd else None),
            percent_complete=pc,actual_start=_date(r.get("act_start_date")),
            actual_finish=_date(r.get("act_end_date")),
            planned_start=_date(r.get("target_start_date")),
            planned_finish=_date(r.get("target_end_date")),
            constraint_date=_date(r.get("cstr_date")),calendar_id=cid,wbs=r.get("wbs_id"),
            source_total_float=(source_tf_h/hpd if source_tf_h is not None and hpd else None),
            metadata={
                "source":dict(r),"remaining_duration_hours":remain_h,"duration_conversion_available":hpd is not None,"xer_task_id":r.get("task_id"),"status":r.get("status_code"),
                "task_type":r.get("task_type"),"duration_type":r.get("duration_type"),
                "constraint_type":r.get("cstr_type"),"constraint_type_2":r.get("cstr_type2"),
                "constraint_date_2":r.get("cstr_date2"),"target_duration_hours":target_h,
                "total_float_hours":source_tf_h,"free_float_hours":_float(r.get("free_float_hr_cnt")),
                "float_path":r.get("float_path"),"float_path_order":r.get("float_path_order"),
                "driving_path_flag":r.get("driving_path_flag"),
                "wbs_name":wbs.get(r.get("wbs_id"),{}).get("wbs_name"),
                "wbs_short_name":wbs.get(r.get("wbs_id"),{}).get("wbs_short_name"),
                "activity_codes":task_codes.get(r.get("task_id"),[]),
            })
        activities[aid]=a
        if r.get("task_id"): internal_to_code[r["task_id"]]=aid

    rels=[]
    type_map={"PR_FS":"FS","PR_SS":"SS","PR_FF":"FF","PR_SF":"SF","FS":"FS","SS":"SS","FF":"FF","SF":"SF"}
    for r in tables.get("TASKPRED",[]):
        p=internal_to_code.get(r.get("pred_task_id")); s=internal_to_code.get(r.get("task_id"))
        if not (p and s):
            exceptions.append({"code":"UNRESOLVED_RELATIONSHIP","source":dict(r)})
            p=p or "UNRESOLVED:"+str(r.get("pred_task_id"))
            s=s or "UNRESOLVED:"+str(r.get("task_id"))
        lag_h=_float(r.get("lag_hr_cnt"),0.0) or 0.0
        pred_cal=calendars.get(activities[p].calendar_id or "" if p in activities else "")
        hpd=(pred_cal.hours_per_day if pred_cal else None) or None
        rels.append(Relationship(p,s,type_map.get(r.get("pred_type","FS"),r.get("pred_type","FS")),lag_h/hpd if hpd else 0.0,lag_h))

    assignments=tables.get("TASKRSRC",[])
    cost_values=[_float(r.get("target_cost")) for r in assignments]
    cost_values=[x for x in cost_values if x is not None]
    data_date=_date(proj.get("last_recalc_date"))
    return Schedule(
        str(proj.get("proj_id","")),proj.get("proj_short_name","XER Project"),
        activities,rels,data_date=data_date,calendars=calendars,source_type="P6 XER",
        metadata={
            "source_project":dict(proj),"source_tables":tables,"data_exceptions":exceptions,
            "tables":sorted(tables),"table_counts":{k:len(v) for k,v in tables.items()},
            "project_calendar_id":proj.get("clndr_id"),"plan_start":proj.get("plan_start_date"),
            "plan_end":proj.get("plan_end_date"),"scheduled_end":proj.get("scd_end_date"),
            "wbs_count":len(wbs),"wbs_records":{k:{"name":v.get("wbs_name"),"short_name":v.get("wbs_short_name"),"parent_wbs_id":v.get("parent_wbs_id")} for k,v in wbs.items()},
            "resource_count":len(tables.get("RSRC",[])),
            "resource_assignment_count":len(assignments),"activity_code_count":len(tables.get("ACTVCODE",[])),
            "activity_code_assignment_count":len(tables.get("TASKACTV",[])),
            "target_cost_sum":sum(cost_values),"cost_assignment_count":len(cost_values),
            "calendar_aware_cpm_ready":False,
        })
