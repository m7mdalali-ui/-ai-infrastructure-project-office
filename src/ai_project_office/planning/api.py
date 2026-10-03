from __future__ import annotations
from .agent import SeniorPlanningAgent, response_to_dict

agent=SeniorPlanningAgent()

def run_planning_task(task:str, **payload):
    routes={
        "baseline_review":lambda:agent.baseline_review(payload["path"]),
        "update_review":lambda:agent.update_review(payload["baseline_path"],payload["update_path"]),
        "recovery_analysis":lambda:agent.recovery_analysis(**payload),
        "monthly_report_review":lambda:agent.monthly_report_review(payload["report"],payload.get("programme"),payload.get("previous_report")),
        "eot_assessment":lambda:agent.eot_assessment(payload["events"],payload.get("claimed_days")),
    }
    if task not in routes:
        raise ValueError(f"Unsupported planning task: {task}")
    return response_to_dict(routes[task]())
