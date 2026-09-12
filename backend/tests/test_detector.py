import pytest
from app.state import NetworkState, Device
from app.detector import AnomalyDetector, MetricHistory


class TestMetricHistory:
    def test_initialization(self):
        history = MetricHistory()
        mean, std, z = history.update(50.0)
        assert mean == 50.0
        assert std == 0.0
        assert z == 0.0
        assert history.initialized

    def test_baseline_collection(self):
        history = MetricHistory(window_size=5)
        for i in range(5):
            history.update(50.0 + i)
        mean, std, z = history.update(50.0)
        assert abs(mean - 52.0) < 0.1
        assert std > 0

    def test_z_score_on_spike(self):
        history = MetricHistory(window_size=10)
        for _ in range(10):
            history.update(50.0)
        mean, std, z = history.update(95.0, is_anomalous=True)
        assert abs(mean - 50.0) < 0.1
        assert z > 3.0


class TestAnomalyDetector:
    def setup_method(self):
        self.detector = AnomalyDetector()
        self.state = NetworkState()
        self.device = Device(id="R-core", name="Core Router", role="core", cpu=50.0)
        self.state.add_device(self.device)

    def test_no_anomaly_normal_operation(self):
        for _ in range(5):
            self.device.cpu = 50.0
            anomalies = self.detector.detect(self.state)
        assert len(anomalies) == 0

    def test_sustained_cpu_anomaly(self):
        for _ in range(5):
            self.device.cpu = 50.0
            self.detector.detect(self.state)
        for _ in range(3):
            self.device.cpu = 95.0
            anomalies = self.detector.detect(self.state)
        assert len(anomalies) > 0
        assert anomalies[0].metric == "cpu"
        assert anomalies[0].device_id == "R-core"
        assert anomalies[0].z_score > 2.5

    def test_abs_threshold_triggers(self):
        for _ in range(5):
            self.device.cpu = 50.0
            self.detector.detect(self.state)
        for _ in range(2):
            self.device.cpu = 95.0
            anomalies = self.detector.detect(self.state)
        assert len(anomalies) > 0

    def test_false_positive_single_spike_suppressed(self):
        for _ in range(5):
            self.device.cpu = 50.0
            self.detector.detect(self.state)
        self.device.cpu = 95.0
        anomalies = self.detector.detect(self.state)
        assert len(anomalies) == 0
        self.device.cpu = 50.0
        self.detector.detect(self.state)

    def test_multiple_metrics_tracked_independently(self):
        self.device.mem = 50.0
        self.device.loss = 1.0
        for _ in range(5):
            self.detector.detect(self.state)
        for _ in range(2):
            self.device.cpu = 95.0
            anomalies = self.detector.detect(self.state)
        cpu_anomalies = [a for a in anomalies if a.metric == "cpu"]
        mem_anomalies = [a for a in anomalies if a.metric == "mem"]
        assert len(cpu_anomalies) > 0
        assert len(mem_anomalies) == 0

    def test_severity_classification(self):
        for _ in range(5):
            self.device.cpu = 50.0
            self.detector.detect(self.state)
        for _ in range(2):
            self.device.cpu = 95.0
            self.detector.detect(self.state)
        anomalies = self.detector.detect(self.state)
        assert anomalies[0].severity in ["medium", "high", "critical"]