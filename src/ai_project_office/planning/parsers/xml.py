from __future__ import annotations
import xml.etree.ElementTree as ET
from pathlib import Path
from ..models import Activity, Relationship, Schedule

def _local(tag): return tag.split("}")[-1]
def _child_text(el,name,default=""):
    for c in el:
        if _local(c.tag)==name: return c.text or default
    return default

def parse_p6_xml(path: str|Path) -> Schedule:
    root=ET.parse(path).getroot(); activities={}; obj_to_code={}
    for el in root.iter():
        if _local(el.tag)=="Activity":
            oid=_child_text(el,"ObjectId"); code=_child_text(el,"Id",oid)
            try: dur=float(_child_text(el,"PlannedDuration","0") or 0)
            except ValueError: dur=0
            activities[code]=Activity(code,_child_text(el,"Name"),dur)
            obj_to_code[oid]=code
    rels=[]
    for el in root.iter():
        if _local(el.tag)=="Relationship":
            p=obj_to_code.get(_child_text(el,"PredecessorActivityObjectId")); s=obj_to_code.get(_child_text(el,"SuccessorActivityObjectId"))
            typ=_child_text(el,"Type","Finish to Start")
            typ={"Finish to Start":"FS","Start to Start":"SS","Finish to Finish":"FF","Start to Finish":"SF"}.get(typ,typ)
            try: lag=float(_child_text(el,"Lag","0") or 0)
            except ValueError: lag=0
            if p and s: rels.append(Relationship(p,s,typ,lag))
    return Schedule(Path(path).stem,Path(path).stem,activities,rels,source_type="P6 XML")

def parse_msp_xml(path: str|Path) -> Schedule:
    root=ET.parse(path).getroot(); activities={}; uid_to_id={}
    for el in root.iter():
        if _local(el.tag)=="Task":
            uid=_child_text(el,"UID"); aid=_child_text(el,"ID",uid); name=_child_text(el,"Name")
            duration=0.0
            activities[aid]=Activity(aid,name,duration,metadata={"uid":uid,"duration_source":_child_text(el,"Duration")})
            uid_to_id[uid]=aid
    rels=[]
    type_map={"0":"FF","1":"FS","2":"SF","3":"SS"}
    for el in root.iter():
        if _local(el.tag)!="Task": continue
        sid=_child_text(el,"ID")
        for c in el:
            if _local(c.tag)=="PredecessorLink":
                p=uid_to_id.get(_child_text(c,"PredecessorUID")); typ=type_map.get(_child_text(c,"Type","1"),"FS")
                if p and sid: rels.append(Relationship(p,sid,typ,0))
    return Schedule(Path(path).stem,Path(path).stem,activities,rels,source_type="MS Project XML",metadata={"warning":"Native .MPP is not supported; export Microsoft Project XML."})
