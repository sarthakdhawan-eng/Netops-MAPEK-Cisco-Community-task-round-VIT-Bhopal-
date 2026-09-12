import pytest
from app.state import NetworkState, Device
from app.diagnoser import NetworkDiagnoser
from app.detector import AnomalyDetector
from app.action_planner import ActionPlanner, ACTION_POLICY_TABLE


class TestActionPlanner:
    def setup_method(self):
        self.planner = ActionPlanner()
        self.state = NetworkState()
        self.detector = AnomalyDetector()
        self.diagnoser = NetworkDiagnoser()

        core = Device(id="R-core", name="Core Router", role="core", cpu=50.0, neighbors=["E1", "E2", "E3", "R-standby"])
        e1 = Device(id="E1", name="Edge 1", role="edge", cpu=30.0, neighbors=["R-core"])
        e2 = Device(id="E2", name="Edge 2", role="edge", cpu=30.0, neighbors=["R-core"])
        e3 = Device(id="E3", name="Edge 3", role="edge", cpu=30.0, neighbors=["R-core"])
        standby = Device(id="R-standby", name="Standby Core", role="core", cpu=10.0, neighbors=["R-core"], metadata={"is_standby": True})

        self.state.add_device(core)
        self.state.add_device(e1)
        self.state.add_device(e2)
        self.state.add_device(e3)
        self.state.add_device(standby)

    def test_no_actions_for_unknown_diagnosis(self):
        from app.state import Diagnosis
        diagnosis = Diagnosis(
            id="diag-1", timestamp=0, root_cause_device="R-core",
            anomaly_ids=[], diagnosis_type="unknown", confidence=0.3,
            reasoning=[], affected_devices=[]
        )
        actions = self.planner.plan(self.state, diagnosis)
        assert len(actions) == 0

    def test_operational_failure_generates_reroute_and_rate_limit(self):
        self.state.get_device("R-core").cpu = 95.0
        self.state.get_device("R-core").queue_depth = 2000

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1

        actions = self.planner.plan(self.state, diagnoses[0])
        action_types = {a.action_type for a in actions}
        assert "reroute_traffic" in action_types
        assert "rate_limit" in action_types
        assert "restart_service" in action_types

    def test_security_diagnosis_generates_block_ip_and_isolate(self):
        core = self.state.get_device("R-core")
        core.cpu = 95.0
        core.metadata["syn_rate"] = 5000

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].diagnosis_type == "security"

        actions = self.planner.plan(self.state, diagnoses[0])
        action_types = {a.action_type for a in actions}
        assert "block_ip" in action_types
        assert "isolate_device" in action_types
        assert "rate_limit" in action_types

    def test_failover_only_for_core_with_standby(self):
        core = self.state.get_device("R-core")
        core.cpu = 95.0
        core.queue_depth = 2000

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        actions = self.planner.plan(self.state, diagnoses[0])
        action_types = {a.action_type for a in actions}
        assert "failover" in action_types

        failover_action = next(a for a in actions if a.action_type == "failover")
        assert "R-standby" in failover_action.parameters.get("standby_id", "")

    def test_actions_have_required_fields(self):
        self.state.get_device("R-core").cpu = 95.0

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        actions = self.planner.plan(self.state, diagnoses[0])

        for action in actions:
            assert action.id
            assert action.action_type in ACTION_POLICY_TABLE
            assert action.target_device in self.state.devices
            assert isinstance(action.preconditions, list)
            assert isinstance(action.effects, list)
            assert isinstance(action.blast_radius, list)
            assert isinstance(action.reversible, bool)
            assert action.rollback_plan
            assert action.target_device in action.blast_radius

    def test_blast_radius_includes_neighbors_for_reroute(self):
        self.state.get_device("R-core").cpu = 95.0

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        actions = self.planner.plan(self.state, diagnoses[0])

        reroute = next(a for a in actions if a.action_type == "reroute_traffic")
        assert "E1" in reroute.blast_radius or "E2" in reroute.blast_radius or "E3" in reroute.blast_radius

    def test_policy_table_immutable(self):
        original = ACTION_POLICY_TABLE["reroute_traffic"]["risk_base"]
        ACTION_POLICY_TABLE["reroute_traffic"]["risk_base"] = 999
        assert self.planner.get_action_policy("reroute_traffic")["risk_base"] == 999
        ACTION_POLICY_TABLE["reroute_traffic"]["risk_base"] = original