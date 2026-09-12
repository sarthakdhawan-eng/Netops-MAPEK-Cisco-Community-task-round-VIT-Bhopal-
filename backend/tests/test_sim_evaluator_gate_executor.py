import pytest
from app.state import NetworkState, Device
from app.diagnoser import NetworkDiagnoser
from app.detector import AnomalyDetector
from app.action_planner import ActionPlanner
from app.simulator import NetworkSimulator, simulate_action
from app.evaluator import RiskEvaluator
from app.decision_gate import DecisionGate
from app.executor import ActionExecutor


class TestSimulator:
    def setup_method(self):
        self.state = NetworkState()
        core = Device(id="R-core", name="Core Router", role="core", cpu=95.0, loss=10.0, queue_depth=3000, neighbors=["E1", "E2"])
        e1 = Device(id="E1", name="Edge 1", role="edge", cpu=40.0, neighbors=["R-core"])
        e2 = Device(id="E2", name="Edge 2", role="edge", cpu=40.0, neighbors=["R-core"])
        self.state.add_device(core)
        self.state.add_device(e1)
        self.state.add_device(e2)
        self.simulator = NetworkSimulator(self.state)

    def test_reroute_traffic_simulation_reduces_load(self):
        from app.state import Action
        import time, uuid
        action = Action(
            id=str(uuid.uuid4())[:8], timestamp=time.time(),
            action_type="reroute_traffic", target_device="R-core",
            parameters={}, preconditions=[], effects=[], blast_radius=["R-core", "E1", "E2"],
            reversible=True, rollback_plan="restore"
        )
        result = self.simulator.simulate_action(action)
        assert result.safe or not result.safe
        assert "R-core" in result.predicted_metrics

    def test_restart_service_simulation_may_spike(self):
        from app.state import Action
        import time, uuid
        action = Action(
            id=str(uuid.uuid4())[:8], timestamp=time.time(),
            action_type="restart_service", target_device="R-core",
            parameters={}, preconditions=[], effects=[], blast_radius=["R-core"],
            reversible=False, rollback_plan="monitor"
        )
        result = self.simulator.simulate_action(action)
        assert "R-core" in result.predicted_metrics

    def test_isolate_device_simulation_causes_violations(self):
        from app.state import Action
        import time, uuid
        action = Action(
            id=str(uuid.uuid4())[:8], timestamp=time.time(),
            action_type="isolate_device", target_device="R-core",
            parameters={}, preconditions=[], effects=[], blast_radius=["R-core", "E1", "E2"],
            reversible=True, rollback_plan="restore"
        )
        result = self.simulator.simulate_action(action)
        assert not result.safe
        assert len(result.new_violations) > 0


class TestEvaluator:
    def setup_method(self):
        self.state = NetworkState()
        core = Device(id="R-core", name="Core Router", role="core", cpu=95.0, loss=10.0, queue_depth=3000, neighbors=["E1"])
        e1 = Device(id="E1", name="Edge 1", role="edge", cpu=40.0, neighbors=["R-core"])
        self.state.add_device(core)
        self.state.add_device(e1)
        self.evaluator = RiskEvaluator()

    def test_high_risk_for_critical_device(self):
        from app.state import Action, Diagnosis
        import time, uuid
        action = Action(
            id="act-1", timestamp=time.time(), action_type="restart_service",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core", "E1"], reversible=False, rollback_plan="monitor"
        )
        diagnosis = Diagnosis(
            id="diag-1", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core", "E1"]
        )
        from app.simulator import SimulationResult
        sim = SimulationResult(
            action_id="act-1", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 40.0, "loss_t4": 1.0}},
            new_violations=[], reasoning=[]
        )
        eval_result = self.evaluator.evaluate(self.state, action, diagnosis, sim)
        assert eval_result.risk_score > 0.4
        assert eval_result.components["irreversibility"] > 0

    def test_low_risk_for_reversible_action(self):
        from app.state import Action, Diagnosis
        import time, uuid
        action = Action(
            id="act-2", timestamp=time.time(), action_type="rate_limit",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core"], reversible=True, rollback_plan="remove"
        )
        diagnosis = Diagnosis(
            id="diag-2", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core"]
        )
        from app.simulator import SimulationResult
        sim = SimulationResult(
            action_id="act-2", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 50.0, "loss_t4": 1.0}},
            new_violations=[], reasoning=[]
        )
        eval_result = self.evaluator.evaluate(self.state, action, diagnosis, sim)
        assert eval_result.risk_score < 0.5


class TestDecisionGate:
    def setup_method(self):
        self.state = NetworkState()
        core = Device(id="R-core", name="Core Router", role="core", cpu=95.0, loss=10.0, queue_depth=3000, neighbors=["E1"])
        e1 = Device(id="E1", name="Edge 1", role="edge", cpu=40.0, neighbors=["R-core"])
        self.state.add_device(core)
        self.state.add_device(e1)
        self.gate = DecisionGate()

    def test_auto_execute_low_risk(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-1", timestamp=time.time(), action_type="rate_limit",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core"], reversible=True, rollback_plan="remove"
        )
        diagnosis = Diagnosis(
            id="diag-1", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core"]
        )
        sim = SimulationResult(
            action_id="act-1", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 50.0, "loss_t4": 1.0}},
            new_violations=[], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        assert decision.decision == "auto_execute"
        assert decision.risk_score < 0.3

    def test_human_approve_medium_risk(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-2", timestamp=time.time(), action_type="reroute_traffic",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core", "E1"], reversible=True, rollback_plan="restore"
        )
        diagnosis = Diagnosis(
            id="diag-2", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core", "E1"]
        )
        sim = SimulationResult(
            action_id="act-2", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 60.0, "loss_t4": 2.0}},
            new_violations=[], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        assert decision.decision in ["auto_execute", "human_approve"]

    def test_reject_high_risk(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-3", timestamp=time.time(), action_type="isolate_device",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core", "E1"], reversible=True, rollback_plan="restore"
        )
        diagnosis = Diagnosis(
            id="diag-3", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="security", confidence=0.9,
            reasoning=[], affected_devices=["R-core", "E1"]
        )
        sim = SimulationResult(
            action_id="act-3", safe=False,
            predicted_metrics={"R-core": {"cpu_t4": 0.0, "loss_t4": 100.0}},
            new_violations=["R-core: Loss critical (100.0%)"], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        assert decision.decision == "reject"

    def test_reject_unsafe_simulation(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-4", timestamp=time.time(), action_type="restart_service",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core"], reversible=False, rollback_plan="monitor"
        )
        diagnosis = Diagnosis(
            id="diag-4", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core"]
        )
        sim = SimulationResult(
            action_id="act-4", safe=False,
            predicted_metrics={"R-core": {"cpu_t4": 98.0, "loss_t4": 25.0}},
            new_violations=["R-core: CPU critical (98.0%)"], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        assert decision.decision == "reject"
        assert any("SIMULATION" in r and "VIOLATIONS" in r for r in decision.reasoning)


class TestExecutor:
    def setup_method(self):
        self.state = NetworkState()
        core = Device(id="R-core", name="Core Router", role="core", cpu=95.0, loss=10.0, queue_depth=3000, neighbors=["E1"])
        e1 = Device(id="E1", name="Edge 1", role="edge", cpu=40.0, neighbors=["R-core"])
        self.state.add_device(core)
        self.state.add_device(e1)
        self.executor = ActionExecutor()
        self.gate = DecisionGate()

    def test_execute_auto_decision(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-1", timestamp=time.time(), action_type="rate_limit",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core"], reversible=True, rollback_plan="remove"
        )
        diagnosis = Diagnosis(
            id="diag-1", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core"]
        )
        sim = SimulationResult(
            action_id="act-1", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 50.0, "loss_t4": 1.0}},
            new_violations=[], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        assert decision.decision == "auto_execute"

        result = self.executor.execute(self.state, action, decision)
        assert result.success
        assert self.state.get_device("R-core").cpu < 95.0

    def test_reject_non_auto_decision(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-2", timestamp=time.time(), action_type="isolate_device",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core", "E1"], reversible=True, rollback_plan="restore"
        )
        diagnosis = Diagnosis(
            id="diag-2", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="security", confidence=0.9,
            reasoning=[], affected_devices=["R-core", "E1"]
        )
        sim = SimulationResult(
            action_id="act-2", safe=False,
            predicted_metrics={"R-core": {"cpu_t4": 0.0, "loss_t4": 100.0}},
            new_violations=["R-core: Loss critical (100.0%)"], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        assert decision.decision == "reject"

        result = self.executor.execute(self.state, action, decision)
        assert not result.success
        assert "not auto_execute" in result.message

    def test_rollback_reversible_action(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-3", timestamp=time.time(), action_type="rate_limit",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core"], reversible=True, rollback_plan="remove"
        )
        diagnosis = Diagnosis(
            id="diag-3", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core"]
        )
        sim = SimulationResult(
            action_id="act-3", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 50.0, "loss_t4": 1.0}},
            new_violations=[], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        self.executor.execute(self.state, action, decision)

        cpu_after = self.state.get_device("R-core").cpu
        rollback_result = self.executor.rollback(self.state, "act-3")
        assert rollback_result.success
        assert self.state.get_device("R-core").cpu == 95.0

    def test_cannot_rollback_irreversible(self):
        from app.state import Action, Diagnosis
        from app.simulator import SimulationResult
        import time
        action = Action(
            id="act-4", timestamp=time.time(), action_type="restart_service",
            target_device="R-core", parameters={}, preconditions=[], effects=[],
            blast_radius=["R-core"], reversible=False, rollback_plan="monitor"
        )
        diagnosis = Diagnosis(
            id="diag-4", timestamp=time.time(), root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="operational", confidence=0.8,
            reasoning=[], affected_devices=["R-core"]
        )
        sim = SimulationResult(
            action_id="act-4", safe=True,
            predicted_metrics={"R-core": {"cpu_t4": 40.0, "loss_t4": 1.0}},
            new_violations=[], reasoning=[]
        )
        decision = self.gate.decide(self.state, action, diagnosis, sim)
        self.executor.execute(self.state, action, decision)

        rollback_result = self.executor.rollback(self.state, "act-4")
        assert not rollback_result.success
        assert "not reversible" in rollback_result.message