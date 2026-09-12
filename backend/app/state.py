from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from copy import deepcopy
import time
import uuid


@dataclass
class Device:
    id: str
    name: str
    role: str
    cpu: float = 0.0
    mem: float = 0.0
    loss: float = 0.0
    latency: float = 0.0
    queue_depth: int = 0
    neighbors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "cpu": self.cpu,
            "mem": self.mem,
            "loss": self.loss,
            "latency": self.latency,
            "queue_depth": self.queue_depth,
            "neighbors": self.neighbors,
            "metadata": self.metadata,
        }


@dataclass
class Link:
    source: str
    target: str
    utilization: float = 0.0
    errors: int = 0
    capacity: float = 100.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "utilization": self.utilization,
            "errors": self.errors,
            "capacity": self.capacity,
        }


@dataclass
class Event:
    id: str
    timestamp: float
    device_id: str
    type: str
    severity: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass
class Anomaly:
    id: str
    timestamp: float
    device_id: str
    metric: str
    expected: float
    observed: float
    z_score: float
    severity: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "metric": self.metric,
            "expected": self.expected,
            "observed": self.observed,
            "z_score": self.z_score,
            "severity": self.severity,
        }


@dataclass
class Diagnosis:
    id: str
    timestamp: float
    root_cause_device: str
    anomaly_ids: List[str]
    diagnosis_type: str
    confidence: float
    reasoning: List[str]
    affected_devices: List[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "root_cause_device": self.root_cause_device,
            "anomaly_ids": self.anomaly_ids,
            "diagnosis_type": self.diagnosis_type,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "affected_devices": self.affected_devices,
        }


@dataclass
class Action:
    id: str
    timestamp: float
    action_type: str
    target_device: str
    parameters: Dict[str, Any]
    preconditions: List[str]
    effects: List[str]
    blast_radius: List[str]
    reversible: bool
    rollback_plan: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "target_device": self.target_device,
            "parameters": self.parameters,
            "preconditions": self.preconditions,
            "effects": self.effects,
            "blast_radius": self.blast_radius,
            "reversible": self.reversible,
            "rollback_plan": self.rollback_plan,
        }


@dataclass
class SimulationResult:
    action_id: str
    safe: bool
    predicted_metrics: Dict[str, Dict[str, float]]
    new_violations: List[str]
    reasoning: List[str]

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "safe": self.safe,
            "predicted_metrics": self.predicted_metrics,
            "new_violations": self.new_violations,
            "reasoning": self.reasoning,
        }


@dataclass
class Decision:
    id: str
    timestamp: float
    action_id: str
    decision: str
    risk_score: float
    simulation: SimulationResult
    reasoning: List[str]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action_id": self.action_id,
            "decision": self.decision,
            "risk_score": self.risk_score,
            "simulation": self.simulation.to_dict(),
            "reasoning": self.reasoning,
        }


class NetworkState:
    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.links: Dict[str, Link] = {}
        self.events: List[Event] = []
        self.anomalies: List[Anomaly] = []
        self.diagnoses: List[Diagnosis] = []
        self.actions: List[Action] = []
        self.decisions: List[Decision] = []
        self.tick: int = 0
        self.history: List[Dict[str, Any]] = []

    def add_device(self, device: Device) -> None:
        self.devices[device.id] = device

    def add_link(self, link: Link) -> None:
        key = f"{link.source}-{link.target}"
        self.links[key] = link

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)

    def get_neighbors(self, device_id: str) -> List[Device]:
        device = self.devices.get(device_id)
        if not device:
            return []
        return [self.devices[nid] for nid in device.neighbors if nid in self.devices]

    def clone(self) -> "NetworkState":
        new_state = NetworkState()
        new_state.devices = {k: deepcopy(v) for k, v in self.devices.items()}
        new_state.links = {k: deepcopy(v) for k, v in self.links.items()}
        new_state.events = deepcopy(self.events)
        new_state.anomalies = deepcopy(self.anomalies)
        new_state.diagnoses = deepcopy(self.diagnoses)
        new_state.actions = deepcopy(self.actions)
        new_state.decisions = deepcopy(self.decisions)
        new_state.tick = self.tick
        new_state.history = deepcopy(self.history)
        return new_state

    def snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "devices": {k: v.to_dict() for k, v in self.devices.items()},
            "links": {k: v.to_dict() for k, v in self.links.items()},
            "events": [e.to_dict() for e in self.events[-50:]],
            "anomalies": [a.to_dict() for a in self.anomalies[-20:]],
            "diagnoses": [d.to_dict() for d in self.diagnoses[-10:]],
            "actions": [a.to_dict() for a in self.actions[-10:]],
            "decisions": [d.to_dict() for d in self.decisions[-10:]],
        }

    def record_history(self) -> None:
        self.history.append(self.snapshot())
        if len(self.history) > 100:
            self.history.pop(0)