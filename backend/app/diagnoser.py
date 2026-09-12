from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from .state import NetworkState, Diagnosis, Device, Anomaly
import uuid
import time


@dataclass
class SuspiciousPattern:
    device_id: str
    pattern_type: str
    indicators: List[str]
    confidence: float


class NetworkDiagnoser:
    def __init__(self):
        self.ops_indicators = {
            "high_cpu_sustained": ["cpu > 85% sustained", "queue_depth growing"],
            "high_mem_sustained": ["mem > 90% sustained", "swap activity"],
            "high_loss_congestion": ["loss > 5%", "latency spiking", "queue buildup"],
        }
        self.security_indicators = {
            "syn_flood": ["SYN packets from many sources", "half-open connections", "spoofed sources"],
            "port_scan": ["connection attempts to many ports", "sequential port access", "short-lived connections"],
            "spoofed_traffic": ["packets from impossible sources", "invalid TTL patterns", "asymmetric routing"],
            "ddos_volume": ["traffic volume > 10x baseline", "many source IPs", "single target"],
        }

    def diagnose(self, state: NetworkState, anomalies: List[Anomaly]) -> List[Diagnosis]:
        if not anomalies:
            return []

        device_anomalies: Dict[str, List[Anomaly]] = {}
        for anomaly in anomalies:
            if anomaly.device_id not in device_anomalies:
                device_anomalies[anomaly.device_id] = []
            device_anomalies[anomaly.device_id].append(anomaly)

        root_causes = self._find_root_causes(state, device_anomalies)
        diagnoses = []

        for root_device_id, (anomaly_ids, affected_devices, diagnosis_type, confidence, reasoning) in root_causes.items():
            diagnosis = Diagnosis(
                id=str(uuid.uuid4())[:8],
                timestamp=time.time(),
                root_cause_device=root_device_id,
                anomaly_ids=anomaly_ids,
                diagnosis_type=diagnosis_type,
                confidence=confidence,
                reasoning=reasoning,
                affected_devices=affected_devices,
            )
            diagnoses.append(diagnosis)
            state.diagnoses.append(diagnosis)

        return diagnoses

    def _find_root_causes(
        self,
        state: NetworkState,
        device_anomalies: Dict[str, List[Anomaly]]
    ) -> Dict[str, Tuple[List[str], List[str], str, float, List[str]]]:
        root_causes = {}
        processed = set()

        for device_id, anomalies in device_anomalies.items():
            if device_id in processed:
                continue

            device = state.get_device(device_id)
            if not device:
                continue

            affected = self._get_affected_downstream(state, device_id, processed)
            all_anomaly_ids = []
            for aid in affected:
                if aid in device_anomalies:
                    all_anomaly_ids.extend([a.id for a in device_anomalies[aid]])
            if device_id in device_anomalies:
                all_anomaly_ids.extend([a.id for a in device_anomalies[device_id]])

            diagnosis_type, confidence, reasoning = self._classify_and_reason(
                state, device_id, anomalies, affected, device_anomalies
            )

            root_causes[device_id] = (all_anomaly_ids, list(affected) + [device_id], diagnosis_type, confidence, reasoning)
            processed.add(device_id)
            processed.update(affected)

        return root_causes

    def _get_affected_downstream(
        self,
        state: NetworkState,
        device_id: str,
        exclude: Set[str]
    ) -> Set[str]:
        affected = set()
        device = state.get_device(device_id)
        if not device:
            return affected

        for neighbor_id in device.neighbors:
            if neighbor_id in exclude:
                continue
            neighbor = state.get_device(neighbor_id)
            if not neighbor:
                continue
            if neighbor.role in ["edge", "access", "leaf"]:
                affected.add(neighbor_id)
                affected.update(self._get_affected_downstream(state, neighbor_id, exclude))

        return affected

    def _classify_and_reason(
        self,
        state: NetworkState,
        root_id: str,
        root_anomalies: List[Anomaly],
        affected: Set[str],
        all_device_anomalies: Dict[str, List[Anomaly]]
    ) -> Tuple[str, float, List[str]]:
        device = state.get_device(root_id)
        if not device:
            return "unknown", 0.0, ["No device data"]

        reasoning = [f"Root cause candidate: {device.name} ({root_id})"]
        metrics = [a.metric for a in root_anomalies]
        reasoning.append(f"Anomalous metrics: {', '.join(metrics)}")

        cpu_anom = any(a.metric == "cpu" and a.severity in ["high", "critical"] for a in root_anomalies)
        mem_anom = any(a.metric == "mem" and a.severity in ["high", "critical"] for a in root_anomalies)
        loss_anom = any(a.metric == "loss" for a in root_anomalies)
        queue_anom = any(a.metric == "queue_depth" for a in root_anomalies)

        ops_score = 0.0
        sec_score = 0.0

        if cpu_anom or mem_anom:
            ops_score += 0.3
            reasoning.append("Resource exhaustion detected (CPU/MEM) — typical operational failure")

        if loss_anom and queue_anom:
            ops_score += 0.3
            reasoning.append("Congestion pattern: loss + queue buildup — operational overload")

        if len(affected) >= 2:
            ops_score += 0.2
            reasoning.append(f"Cascading to {len(affected)} downstream devices — consistent with bottleneck at {device.name}")

        if device.metadata.get("syn_rate", 0) > 1000:
            sec_score += 0.5
            reasoning.append("High SYN rate detected — possible SYN flood")

        if device.metadata.get("unique_src_ports", 0) > 50:
            sec_score += 0.5
            reasoning.append("Many unique source ports — possible port scan")

        if device.metadata.get("spoofed_sources", 0) > 10:
            sec_score += 0.5
            reasoning.append("Spoofed source IPs detected — security event")

        if device.metadata.get("traffic_volume_ratio", 1.0) > 10.0:
            sec_score += 0.5
            reasoning.append("Traffic volume 10x baseline — possible DDoS")

        if sec_score >= 0.5:
            diagnosis_type = "security"
            confidence = min(0.9, sec_score)
            reasoning.append(f"Security indicators present (score: {sec_score:.2f}) — classified as security event")
        elif ops_score >= 0.3:
            diagnosis_type = "operational"
            confidence = min(0.9, ops_score)
            reasoning.append(f"Operational indicators dominate (score: {ops_score:.2f}) — classified as operational failure")
        else:
            diagnosis_type = "unknown"
            confidence = 0.3
            reasoning.append("Insufficient evidence for clear classification")

        return diagnosis_type, confidence, reasoning