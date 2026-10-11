from dataclasses import dataclass
from typing import Dict, List, Optional
from .state import NetworkState, Action, Decision, Diagnosis, SimulationResult
from .evaluator import RiskEvaluator, RiskEvaluation
import uuid
import time


@dataclass
class DecisionGateResult:
    decision: str
    risk_score: float
    reasoning: List[str]
    requires_approval: bool


class DecisionGate:
    AUTO_THRESHOLD = 0.3
    REJECT_THRESHOLD = 0.7

    def __init__(self):
        self.evaluator = RiskEvaluator()
        self.auto_count = 0
        self.approve_count = 0
        self.reject_count = 0

    def decide(
        self,
        state: NetworkState,
        action: Action,
        diagnosis: Diagnosis,
        simulation: SimulationResult
    ) -> Decision:
        evaluation = self.evaluator.evaluate(state, action, diagnosis, simulation)
        risk_score = evaluation.risk_score

        if not simulation.safe or risk_score >= self.REJECT_THRESHOLD:
            decision_type = "reject"
            reasoning = evaluation.reasoning + ["SIMULATION PREDICTS VIOLATIONS OR RISK EXCEEDS LIMIT — ACTION REJECTED"]
        elif risk_score < self.AUTO_THRESHOLD and action.reversible:
            decision_type = "auto_execute"
            reasoning = evaluation.reasoning + [
                f"Risk {risk_score:.2f} < {self.AUTO_THRESHOLD} (auto threshold)",
                "Simulation clean and action reversible — eligible for simulated execution"
            ]
        else:
            decision_type = "human_approve"
            reasoning = evaluation.reasoning + [
                f"Risk {risk_score:.2f} in [{self.AUTO_THRESHOLD}, {self.REJECT_THRESHOLD}) — REQUIRES HUMAN APPROVAL"
            ]

        if diagnosis.diagnosis_type == "security" and action.action_type == "isolate_device" and decision_type == "auto_execute":
            decision_type = "human_approve"
            reasoning.append("Security isolation escalated to human approval per policy")

        if decision_type == "auto_execute":
            self.auto_count += 1
        elif decision_type == "human_approve":
            self.approve_count += 1
        else:
            self.reject_count += 1

        decision = Decision(
            id=str(uuid.uuid4())[:8],
            timestamp=time.time(),
            action_id=action.id,
            decision=decision_type,
            risk_score=risk_score,
            simulation=simulation,
            reasoning=reasoning,
        )
        state.decisions.append(decision)

        return decision

    def get_stats(self) -> Dict[str, int]:
        return {
            "auto_executed": self.auto_count,
            "human_approve": self.approve_count,
            "rejected": self.reject_count,
        }
