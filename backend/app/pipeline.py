"""Standalone MAPE-K demonstration pipeline over in-memory simulated state.

The HTTP API's decision routes are separate and do not invoke this pipeline.
"""

from __future__ import annotations

from .action_planner import ActionPlanner
from .decision_gate import DecisionGate
from .detector import AnomalyDetector
from .diagnoser import NetworkDiagnoser
from .executor import ActionExecutor
from .simulator import NetworkSimulator
from .state import NetworkState


def run_mapek_pipeline(state: NetworkState) -> dict:
    """Run the detect → diagnose → plan → simulate → decide → simulated-apply flow."""
    detector = AnomalyDetector()
    diagnoser = NetworkDiagnoser()
    planner = ActionPlanner()
    simulator = NetworkSimulator(state)
    gate = DecisionGate()
    executor = ActionExecutor()

    sample_count = max(threshold["sustained_ticks"] for threshold in detector.THRESHOLDS.values())
    anomalies = []
    for _ in range(sample_count):
        anomalies = detector.detect(state)
    diagnoses = diagnoser.diagnose(state, anomalies)
    if not diagnoses:
        return {
            "execution_mode": "simulation_only",
            "device_operation_performed": False,
            "diagnosis": None,
            "actions": [],
            "decision": "reject",
            "reason": "No sustained anomalies detected",
            "execution": None,
        }

    diagnosis = diagnoses[0]
    actions = planner.plan(state, diagnosis)
    if not actions:
        return {
            "execution_mode": "simulation_only",
            "device_operation_performed": False,
            "diagnosis": diagnosis.to_dict(),
            "actions": [],
            "decision": "reject",
            "reason": "No applicable actions for diagnosis",
            "execution": None,
        }

    action = actions[0]
    sim_result = simulator.simulate_action(action)
    decision = gate.decide(state, action, diagnosis, sim_result)
    execution = executor.execute(state, action, decision)

    return {
        "execution_mode": "simulation_only",
        "device_operation_performed": False,
        "diagnosis": diagnosis.to_dict(),
        "actions": [a.to_dict() for a in actions],
        "decision": decision.decision,
        "reason": decision.reasoning[-1] if decision.reasoning else "No reasoning",
        "execution": {
            "simulated": execution.success,
            "execution_mode": "simulation_only",
            "message": execution.message,
            "rollback_available": execution.rollback_available,
            "details": execution.details,
        },
    }
