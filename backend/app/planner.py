"""Action planner, risk scoring, simulation, and approval policy."""
from __future__ import annotations

ACTIONS = {
    "Reroute traffic": {"blast": 30, "reversible": True, "effect": -28.0},
    "Rate limit": {"blast": 20, "reversible": True, "effect": -12.0},
    "Block source IPs": {"blast": 55, "reversible": True, "effect": -8.0},
    "Failover": {"blast": 45, "reversible": False, "effect": -35.0},
    "Isolate device": {"blast": 80, "reversible": False, "effect": -45.0},
}

def plan(category: str, severity: str) -> list[str]:
    if category == "Security":
        return ["Block source IPs", "Rate limit", "Isolate device"]
    if severity == "Critical":
        return ["Failover", "Reroute traffic", "Rate limit"]
    return ["Reroute traffic", "Rate limit", "Failover"]

def risk_score(action: str, severity: str, category: str) -> dict:
    spec = ACTIONS.get(action, {"blast": 40, "reversible": True, "effect": -10.0})
    severity_weight = {"Low": 5, "Medium": 15, "High": 25, "Critical": 35}.get(severity, 15)
    reversibility = 0 if spec["reversible"] else 20
    security_uplift = 10 if category == "Security" and action == "Isolate device" else 0
    score = min(95, int(spec["blast"] * 0.5 + severity_weight * 0.5 + reversibility + security_uplift))
    factors = [f"Blast radius {spec['blast']}%", f"Severity {severity}", "Reversible" if spec["reversible"] else "Irreversible"]
    return {"risk": score, "factors": factors, "reversible": spec["reversible"]}

def simulate(action: str, current_cpu: float, capacity_margin: float = 25.0) -> dict:
    spec = ACTIONS.get(action, {"effect": -10.0, "reversible": True})
    predicted = max(5.0, current_cpu + spec["effect"])
    overload = predicted > (100.0 - capacity_margin)
    # Unsafe-remediation guard: failover while spare capacity is thin creates a new failure.
    unsafe = action == "Failover" and capacity_margin < 20.0
    passed = (not overload) and (not unsafe)
    reason = "Predicted load remains within safe capacity"
    if unsafe:
        reason = "Blocked: failover target lacks spare capacity and would cascade"
    elif overload:
        reason = "Blocked: predicted load exceeds safe capacity margin"
    return {"passed": passed, "predicted_cpu": round(predicted, 1), "reason": reason, "unsafe": unsafe}

def decide_action(risk: int, simulated_passed: bool, category: str) -> str:
    """Single source of truth for the approval gate used by both the API and the pipeline.

    This avoids the production crash caused by the UI calling /api/decide while the
    planner exposes only decide() instead of the actual runtime entry point name.
    """
    if not simulated_passed:
        return "rejected"
    if category == "Security" and risk >= 60:
        return "approval"
    if risk < 20:
        return "auto"
    if risk <= 50:
        return "approval"
    return "rejected"


def decide(risk: int, simulated_passed: bool, category: str) -> str:
    return decide_action(risk, simulated_passed, category)
