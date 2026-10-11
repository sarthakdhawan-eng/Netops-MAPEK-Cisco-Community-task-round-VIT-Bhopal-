"""Action planner, risk scoring, simulation, and approval policy."""
from __future__ import annotations

ACTIONS = {
    "Reroute traffic": {"blast": 30, "reversible": True, "effect": -28.0},
    "Rate limit": {"blast": 20, "reversible": True, "effect": -12.0},
    "Block source IPs": {"blast": 55, "reversible": True, "effect": -8.0},
    "Failover": {"blast": 45, "reversible": True, "effect": -35.0},
    "Isolate device": {"blast": 80, "reversible": True, "effect": -45.0},
}

def plan(category: str, severity: str) -> list[str]:
    if category == "Security":
        return ["Block source IPs", "Rate limit", "Isolate device"]
    if severity == "Critical":
        return ["Failover", "Reroute traffic", "Rate limit"]
    return ["Reroute traffic", "Rate limit", "Failover"]

def risk_score(action: str, severity: str, category: str) -> dict:
    if action not in ACTIONS:
        raise ValueError(f"Unsupported action: {action}")
    spec = ACTIONS[action]
    severity_weight = {"Low": 5, "Medium": 15, "High": 25, "Critical": 35}.get(severity, 15)
    reversibility = 0 if spec["reversible"] else 20
    security_uplift = 10 if category == "Security" and action == "Isolate device" else 0
    score = min(95, int(spec["blast"] * 0.5 + severity_weight * 0.5 + reversibility + security_uplift))
    factors = [f"Blast radius {spec['blast']}%", f"Severity {severity}", "Reversible" if spec["reversible"] else "Irreversible"]
    return {"risk": score, "factors": factors, "reversible": spec["reversible"]}

def simulate(action: str, current_cpu: float, capacity_margin: float = 25.0) -> dict:
    if action not in ACTIONS:
        raise ValueError(f"Unsupported action: {action}")
    if not 0 <= capacity_margin <= 100:
        raise ValueError("capacity_margin must be between 0 and 100")
    spec = ACTIONS[action]
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

def decide_action(risk: int, simulated_passed: bool, category: str, reversible: bool = True) -> str:
    """Return the API policy decision; this does not perform device execution."""
    if not simulated_passed:
        return "rejected"
    if risk >= 70:
        return "rejected"
    if not reversible or (category == "Security" and risk >= 60):
        return "approval"
    if risk < 30:
        return "auto"
    return "approval"


def decide(risk: int, simulated_passed: bool, category: str, reversible: bool = True) -> str:
    return decide_action(risk, simulated_passed, category, reversible)
