from __future__ import annotations
from pathlib import Path
from .parsers import parse_excel, parse_xer, parse_p6_xml, parse_msp_xml
from .programme_review import review_programme

def import_schedule(path: str|Path, *, excel_column_map=None, project_id=None):
    p=Path(path); ext=p.suffix.lower()
    if ext==".xer": return parse_xer(p,project_id=project_id)
    if ext==".xml":
        text=p.read_text(encoding="utf-8",errors="ignore")[:10000]
        return parse_msp_xml(p) if "<Project" in text and ("schemas.microsoft.com/project" in text or "<Tasks" in text) else parse_p6_xml(p)
    if ext in {".xlsx",".xlsm"}:
        if not excel_column_map: raise ValueError("Excel import requires explicit excel_column_map; no column guessing is permitted.")
        return parse_excel(p,excel_column_map)
    if ext==".mpp": raise NotImplementedError("Native MPP is not supported. Export Microsoft Project XML.")
    raise ValueError(f"Unsupported schedule format: {ext}")

def review_file(path, programme_type="Updated", **kwargs):
    return review_programme(import_schedule(path,**kwargs),programme_type)
