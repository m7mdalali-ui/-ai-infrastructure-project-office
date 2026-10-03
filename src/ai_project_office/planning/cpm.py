from __future__ import annotations
from collections import deque
from .models import Schedule, CPMResult

class NetworkCycleError(ValueError): pass

def _offsets(rel_type: str, pred_d: float, succ_d: float, lag: float) -> tuple[float,float]:
    t=rel_type.upper()
    # Forward: successor ES >= predecessor ES + forward offset.
    # Backward constraint uses same start-to-start inequality.
    if t=="FS": return pred_d+lag, pred_d+lag
    if t=="SS": return lag, lag
    if t=="FF": return pred_d+lag-succ_d, pred_d+lag-succ_d
    if t=="SF": return lag-succ_d, lag-succ_d
    raise ValueError(f"Unsupported relationship type: {rel_type}")

def calculate_cpm(schedule: Schedule, near_critical_threshold: float=5.0) -> CPMResult:
    acts=schedule.activities
    if not acts: return CPMResult(0,[],[],[],[])
    succ={i:[] for i in acts}; pred={i:[] for i in acts}; indeg={i:0 for i in acts}
    for r in schedule.relationships:
        if r.predecessor_id not in acts or r.successor_id not in acts: continue
        succ[r.predecessor_id].append(r); pred[r.successor_id].append(r); indeg[r.successor_id]+=1
    q=deque(sorted(i for i,d in indeg.items() if d==0)); order=[]
    while q:
        u=q.popleft(); order.append(u)
        for r in succ[u]:
            indeg[r.successor_id]-=1
            if indeg[r.successor_id]==0: q.append(r.successor_id)
    if len(order)!=len(acts): raise NetworkCycleError("Circular logic detected; CPM calculation refused.")
    for i in order:
        a=acts[i]; a.es=0.0
        for r in pred[i]:
            p=acts[r.predecessor_id]
            off,_=_offsets(r.type,p.duration,a.duration,r.lag)
            a.es=max(a.es,(p.es or 0)+off)
        a.ef=a.es+a.duration
    finish=max(a.ef or 0 for a in acts.values())
    for i in reversed(order):
        a=acts[i]
        if not succ[i]: a.ls=finish-a.duration
        else:
            candidates=[]
            for r in succ[i]:
                s=acts[r.successor_id]
                _,off=_offsets(r.type,a.duration,s.duration,r.lag)
                candidates.append((s.ls or 0)-off)
            a.ls=min(candidates)
        a.lf=a.ls+a.duration
        a.total_float=a.ls-(a.es or 0)
        if succ[i]:
            starts=[]
            for r in succ[i]:
                s=acts[r.successor_id]; off,_=_offsets(r.type,a.duration,s.duration,r.lag)
                starts.append((s.es or 0)-((a.es or 0)+off))
            a.free_float=min(starts)
        else: a.free_float=finish-(a.ef or 0)
        a.critical=abs(a.total_float)<=1e-9
        a.near_critical=(not a.critical) and a.total_float <= near_critical_threshold
    return CPMResult(finish,[i for i,a in acts.items() if a.critical],[i for i,a in acts.items() if a.near_critical],[i for i,a in acts.items() if (a.total_float or 0)<0],order)
