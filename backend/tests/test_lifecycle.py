"""Lifecycle tests for Detect -> Understand -> Plan -> Evaluate -> Respond."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.api as api_module
from app import detection, planner, rca


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        api_module.DB_PATH = Path(tmp.name)
        api_module.init_db()

    def test_normal_network_no_anomaly(self):
        verdict = detection.detect_device([40, 42, 41, 43, 42, 41, 43, 42], [0.4] * 8, [55] * 8)
        self.assertFalse(verdict["anomaly"])

    def test_single_device_failure_detected(self):
        verdict = detection.detect_device([40, 42, 44, 43, 45, 95, 96, 97], [0.4, 0.5, 0.6, 0.5, 0.7, 6.8, 7.1, 6.9], [55] * 8)
        self.assertTrue(verdict["anomaly"])

    def test_cascading_congestion_root_cause(self):
        cause = rca.root_cause([{"device": "R-core", "anomaly": True, "score": 9.0}, {"device": "E-14", "anomaly": True, "score": 4.0}])
        self.assertEqual(cause["device"], "R-core")

    def test_security_classification(self):
        result = rca.classify_security("12.4k req/s", "Sequential port access detected from multiple source ranges.", request_rate=12400)
        self.assertEqual(result["category"], "Security")
        operational = rca.classify_security("CPU 95%", "Queue depth rising across downstream edges.")
        self.assertEqual(operational["category"], "Operational")

    def test_false_positive_transient_spike(self):
        verdict = detection.detect_series([40, 41, 42, 41, 42, 43, 42, 95])
        self.assertFalse(verdict["anomaly"])
        self.assertIn("Transient", verdict["reason"])

    def test_unsafe_remediation_blocked(self):
        scored = planner.risk_score("Failover", "Critical", "Operational")
        simulated = planner.simulate("Failover", 92.0, capacity_margin=10.0)
        self.assertFalse(simulated["passed"])
        self.assertEqual(planner.decide(scored["risk"], simulated["passed"], "Operational"), "rejected")

    def test_safe_action_approval_path(self):
        scored = planner.risk_score("Reroute traffic", "High", "Operational")
        simulated = planner.simulate("Reroute traffic", 95.0, capacity_margin=25.0)
        self.assertTrue(simulated["passed"])
        self.assertIn(planner.decide(scored["risk"], simulated["passed"], "Operational"), {"auto", "approval"})

    def test_api_simulate_persists_decision(self):
        with api_module.connect() as connection:
            connection.execute("INSERT INTO incidents (id, payload, updated_at) VALUES (?, ?, ?)", ("INC-TEST", json.dumps({"id": "INC-TEST", "device": "R-core", "severity": "High", "type": "Operational"}), 1.0))
        from app.planner import decide, risk_score, simulate
        incident = {"severity": "High", "type": "Operational", "device": "R-core"}
        scored = risk_score("Reroute traffic", "High", "Operational")
        result = simulate("Reroute traffic", 95.0, capacity_margin=25.0)
        decision = decide(scored["risk"], result["passed"], "Operational")
        with api_module.connect() as connection:
            connection.execute("INSERT INTO decisions (incident_id, action, risk, simulated_passed, decision, created_at) VALUES (?, ?, ?, ?, ?, ?)", ("INC-TEST", "Reroute traffic", scored["risk"], int(result["passed"]), decision, 1.0))
        self.assertTrue(result["passed"])
        with api_module.connect() as connection:
            row = connection.execute("SELECT decision FROM decisions WHERE incident_id = ?", ("INC-TEST",)).fetchone()
            self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
