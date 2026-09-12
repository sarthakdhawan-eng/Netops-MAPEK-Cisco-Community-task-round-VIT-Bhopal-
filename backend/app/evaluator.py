from dataclasses import dataclass
from typing import Dict, List
from .state import NetworkState, Action, SimulationResult, Diagnosis
from .action_planner import ACTION_POLICY_TABLE


@dataclass
class RiskEvaluation:
    action_id: str
    risk_score: float
    components: Dict[str, float]
    simulation: SimulationResult
    reasoning: List[str]


class RiskEvaluator:
    def __init__(self):
        self.impact_weights = {
            "cpu": 0.3,
            "loss": 0.3,
            "queue_depth": 0.2,
            "mem": 0.2,
        }
        self.blast_radius_multiplier = 0.1
        self.irreversibility_penalty = 0.75
        self.security_multiplier = 0.15

    def evaluate(self, state: NetworkState, action: Action, diagnosis: Diagnosis, simulation: SimulationResult) -> RiskEvaluation:
        components = {}
        reasoning = []

        policy = ACTION_POLICY_TABLE.get(action.action_type, {})
        base_risk = policy.get("risk_base", 0.5)
        components["base_risk"] = base_risk
        reasoning.append(f"Base risk from policy table: {base_risk:.2f}")

        impact = self._calculate_impact(state, action, simulation)
        components["impact"] = impact
        reasoning.append(f"Impact score: {impact:.2f}")

        blast = self._calculate_blast_risk(action)
        components["blast_radius"] = blast
        reasoning.append(f"Blast radius risk: {blast:.2f} ({len(action.blast_radius)} devices affected)")

        irreversibility = 0.0 if action.reversible else self.irreversibility_penalty
        components["irreversibility"] = irreversibility
        if not action.reversible:
            reasoning.append(f"Irreversible action penalty: +{irreversibility:.2f}")

        security_bonus = self.security_multiplier if diagnosis.diagnosis_type == "security" else 0.0
        components["security_context"] = security_bonus
        if security_bonus > 0:
            reasoning.append(f"Security event context bonus: +{security_bonus:.2f}")

        sim_penalty = 0.0
        if not simulation.safe:
            sim_penalty = 0.4
            components["simulation_failure"] = sim_penalty
            reasoning.append(f"SIMULATION UNSAFE: +{sim_penalty:.2f} — {', '.join(simulation.new_violations[:2])}")
        else:
            components["simulation_failure"] = 0.0
            reasoning.append("Simulation predicts safe outcome")

        risk_score = (
            base_risk * 0.25 +
            impact * 0.25 +
            blast * 0.15 +
            irreversibility * 0.2 +
            security_bonus * 0.05 +
            sim_penalty * 0.1
        )
        risk_score = min(1.0, max(0.0, risk_score))

        return RiskEvaluation(
            action_id=action.id,
            risk_score=risk_score,
            components=components,
            simulation=simulation,
            reasoning=reasoning,
        )

    def _calculate_impact(
        self,
        state: NetworkState,
        action: Action,
        simulation: SimulationResult
    ) -> float:
        device = state.get_device(action.target_device)
        if not device:
            return 0.5

        severity = 0.0
        if device.cpu > 90:
            severity += self.impact_weights["cpu"]
        if device.loss > 10:
            severity += self.impact_weights["loss"]
        if device.queue_depth > 2000:
            severity += self.impact_weights["queue_depth"]
        if device.mem > 90:
            severity += self.impact_weights["mem"]

        if simulation.safe:
            severity *= 0.7

        return min(1.0, severity)

    def _calculate_blast_risk(self, action: Action) -> float:
        blast_count = len(action.blast_radius)
        if blast_count <= 1:
            return 0.1
        elif blast_count <= 3:
            return 0.3
        elif blast_count <= 6:
            return 0.5
        else:
            return 0.7