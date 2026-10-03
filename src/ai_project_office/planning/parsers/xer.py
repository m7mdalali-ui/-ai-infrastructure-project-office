from __future__ import annotations
from pathlib import Path
from ..models import Activity, Relationship, Schedule

def parse_xer(path: str|Path) -> Schedule:
    tables={}; table=None; fields=[]
    for raw in Path(path).read_text(encoding="utf-8",errors="replace").splitlines():
        parts=raw.split("\t")
        if not parts: continue
        if parts[0]=="%T": table=parts[1]; tables.setdefault(table,[])
        elif parts[0]=="%F": fields=parts[1:]
        elif parts[0]=="%R" and table:
            tables[table].append(dict(zip(fields,parts[1:])))
    activities={}
    for r in tables.get("TASK",[]):
        aid=r.get("task_code") or r.get("task_id")
        if not aid: continue
        dur=float(r.get("target_drtn_hr_cnt") or r.get("remain_drtn_hr_cnt") or 0)/8.0
        pc=float(r.get("phys_complete_pct") or 0)
        if pc<=1: pc*=100
        activities[aid]=Activity(aid,r.get("task_name",""),dur,percent_complete=pc,wbs=r.get("wbs_id"),metadata={"xer_task_id":r.get("task_id")})
    by_internal={a.metadata.get("xer_task_id"):a.id for a in activities.values()}
    rels=[]
    type_map={"PR_FS":"FS","PR_SS":"SS","PR_FF":"FF","PR_SF":"SF","FS":"FS","SS":"SS","FF":"FF","SF":"SF"}
    for r in tables.get("TASKPRED",[]):
        p=by_internal.get(r.get("pred_task_id")); s=by_internal.get(r.get("task_id"))
        if p and s: rels.append(Relationship(p,s,type_map.get(r.get("pred_type","FS"),r.get("pred_type","FS")),float(r.get("lag_hr_cnt") or 0)/8.0))
    proj=tables.get("PROJECT",[{}])[0]
    return Schedule(str(proj.get("proj_id","")),proj.get("proj_short_name","XER Project"),activities,rels,source_type="P6 XER",metadata={"tables":sorted(tables)})
