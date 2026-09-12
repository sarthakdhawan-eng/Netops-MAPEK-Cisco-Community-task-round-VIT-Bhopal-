from dataclasses import dataclass, field
from typing import Dict, List
from .state import NetworkState, Anomaly
import uuid
import time
import statistics


@dataclass
class MetricHistory:
    baseline_values: List[float] = field(default_factory=list)
    window_size: int = 10
    initialized: bool = False

    def update(self, value: float, is_anomalous: bool = False) -> tuple:
        if not is_anomalous and len(self.baseline_values) < self.window_size:
            self.baseline_values.append(value)
            self.initialized = True
            return value, 0.0, 0.0

        if len(self.baseline_values) < 3:
            return value, 0.0, 0.0

        self.initialized = True
        mean = statistics.mean(self.baseline_values)
        std = statistics.stdev(self.baseline_values) if len(self.baseline_values) > 1 else 1.0
        std = max(std, 1.0)
        z_score = (value - mean) / std
        return mean, std, z_score

    def get_baseline_stats(self) -> tuple:
        if len(self.baseline_values) < 2:
            return 0.0, 1e-6
        return statistics.mean(self.baseline_values), statistics.stdev(self.baseline_values)


class AnomalyDetector:
    METRICS = ["cpu", "mem", "loss", "latency", "queue_depth"]
    THRESHOLDS = {
        "cpu": {"z": 2.5, "sustained_ticks": 2, "abs_threshold": 85.0},
        "mem": {"z": 2.5, "sustained_ticks": 2, "abs_threshold": 90.0},
        "loss": {"z": 2.0, "sustained_ticks": 2, "abs_threshold": 5.0},
        "latency": {"z": 2.5, "sustained_ticks": 2, "abs_threshold": 200.0},
        "queue_depth": {"z": 2.5, "sustained_ticks": 2, "abs_threshold": 1000},
    }

    def __init__(self):
        self.histories: Dict[str, Dict[str, MetricHistory]] = {}
        self.sustained_counts: Dict[str, Dict[str, int]] = {}

    def _get_history(self, device_id: str, metric: str) -> MetricHistory:
        if device_id not in self.histories:
            self.histories[device_id] = {}
        if metric not in self.histories[device_id]:
            self.histories[device_id][metric] = MetricHistory()
        return self.histories[device_id][metric]

    def _get_sustained_count(self, device_id: str, metric: str) -> int:
        if device_id not in self.sustained_counts:
            self.sustained_counts[device_id] = {}
        if metric not in self.sustained_counts[device_id]:
            self.sustained_counts[device_id][metric] = 0
        return self.sustained_counts[device_id][metric]

    def _increment_sustained(self, device_id: str, metric: str) -> int:
        if device_id not in self.sustained_counts:
            self.sustained_counts[device_id] = {}
        if metric not in self.sustained_counts[device_id]:
            self.sustained_counts[device_id][metric] = 0
        self.sustained_counts[device_id][metric] += 1
        return self.sustained_counts[device_id][metric]

    def _reset_sustained(self, device_id: str, metric: str) -> None:
        if device_id in self.sustained_counts and metric in self.sustained_counts[device_id]:
            self.sustained_counts[device_id][metric] = 0

    def detect(self, state: NetworkState) -> List[Anomaly]:
        anomalies = []
        for device in state.devices.values():
            for metric in self.METRICS:
                value = getattr(device, metric, 0.0)
                history = self._get_history(device.id, metric)

                threshold = self.THRESHOLDS[metric]
                abs_exceeded = value > threshold["abs_threshold"]

                mean, std, z_score = history.update(value, is_anomalous=abs_exceeded)
                z_exceeded = abs(z_score) > threshold["z"]

                if z_exceeded or abs_exceeded:
                    sustained = self._increment_sustained(device.id, metric)
                else:
                    self._reset_sustained(device.id, metric)
                    sustained = 0

                triggered = sustained >= threshold["sustained_ticks"] and (abs_exceeded or z_exceeded)

                if triggered:
                    severity = "critical" if abs(z_score) > 3.5 else "high" if abs(z_score) > 2.5 else "medium"
                    if abs_exceeded and z_score == 0:
                        severity = "high"
                    anomaly = Anomaly(
                        id=str(uuid.uuid4())[:8],
                        timestamp=time.time(),
                        device_id=device.id,
                        metric=metric,
                        expected=round(mean, 2),
                        observed=round(value, 2),
                        z_score=round(z_score, 2),
                        severity=severity,
                    )
                    anomalies.append(anomaly)
                    state.anomalies.append(anomaly)

        return anomalies