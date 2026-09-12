import pytest
from app.state import NetworkState, Device
from app.diagnoser import NetworkDiagnoser
from app.detector import AnomalyDetector


class TestNetworkDiagnoser:
    def setup_method(self):
        self.diagnoser = NetworkDiagnoser()
        self.state = NetworkState()
        self.detector = AnomalyDetector()

        core = Device(id="R-core", name="Core Router", role="core", cpu=50.0, neighbors=["E1", "E2", "E3"])
        e1 = Device(id="E1", name="Edge 1", role="edge", cpu=30.0, neighbors=["R-core"])
        e2 = Device(id="E2", name="Edge 2", role="edge", cpu=30.0, neighbors=["R-core"])
        e3 = Device(id="E3", name="Edge 3", role="edge", cpu=30.0, neighbors=["R-core"])

        self.state.add_device(core)
        self.state.add_device(e1)
        self.state.add_device(e2)
        self.state.add_device(e3)

    def test_no_anomalies_no_diagnosis(self):
        diagnoses = self.diagnoser.diagnose(self.state, [])
        assert len(diagnoses) == 0

    def test_single_device_operational_failure(self):
        self.state.get_device("R-core").cpu = 95.0
        self.state.get_device("R-core").queue_depth = 2000

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].root_cause_device == "R-core"
        assert diagnoses[0].diagnosis_type == "operational"
        assert diagnoses[0].confidence >= 0.5
        assert any("Resource exhaustion" in r for r in diagnoses[0].reasoning)

    def test_cascading_failure_identifies_root_core(self):
        self.state.get_device("R-core").cpu = 95.0
        self.state.get_device("R-core").queue_depth = 2000
        self.state.get_device("E1").loss = 10.0
        self.state.get_device("E2").loss = 8.0

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].root_cause_device == "R-core"
        assert "E1" in diagnoses[0].affected_devices
        assert "E2" in diagnoses[0].affected_devices
        assert any("Cascading" in r for r in diagnoses[0].reasoning)

    def test_security_syn_flood_detection(self):
        core = self.state.get_device("R-core")
        core.cpu = 95.0
        core.metadata["syn_rate"] = 5000
        core.metadata["spoofed_sources"] = 50

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].diagnosis_type == "security"
        assert any("SYN flood" in r or "syn_rate" in r for r in diagnoses[0].reasoning)

    def test_security_port_scan_detection(self):
        core = self.state.get_device("R-core")
        core.cpu = 95.0
        core.metadata["unique_src_ports"] = 100

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].diagnosis_type == "security"
        assert any("port scan" in r.lower() for r in diagnoses[0].reasoning)

    def test_ddos_volume_detection(self):
        core = self.state.get_device("R-core")
        core.cpu = 95.0
        core.metadata["traffic_volume_ratio"] = 15.0

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].diagnosis_type == "security"
        assert any("DDoS" in r or "traffic volume" in r for r in diagnoses[0].reasoning)

    def test_edge_device_not_root_when_core_overloaded(self):
        self.state.get_device("R-core").cpu = 95.0
        self.state.get_device("R-core").queue_depth = 2000
        self.state.get_device("E1").cpu = 85.0

        for _ in range(3):
            anomalies = self.detector.detect(self.state)

        diagnoses = self.diagnoser.diagnose(self.state, anomalies)
        assert len(diagnoses) == 1
        assert diagnoses[0].root_cause_device == "R-core"
        assert "E1" in diagnoses[0].affected_devices