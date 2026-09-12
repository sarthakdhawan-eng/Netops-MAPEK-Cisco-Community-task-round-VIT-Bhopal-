from typing import Any, Dict, List, Optional
from .state import NetworkState, Action, Device, Diagnosis
import uuid
import time


ACTION_POLICY_TABLE = {
    "reroute_traffic": {
        "description": "Reroute traffic away from overloaded device to alternate paths",
        "preconditions": ["target device overloaded", "alternate path exists"],
        "effects": ["reduces load on target", "increases load on alternate path"],
        "blast_radius": ["target device", "alternate path devices"],
        "reversible": True,
        "rollback_plan": "Restore original routing tables",
        "risk_base": 0.2,
        "applicable_roles": ["core", "edge"],
        "applicable_types": ["operational"],
    },
    "rate_limit": {
        "description": "Apply rate limiting on traffic to/from affected device",
        "preconditions": ["traffic volume exceeds threshold", "rate limiting capability exists"],
        "effects": ["reduces incoming traffic", "may drop legitimate traffic"],
        "blast_radius": ["target device", "traffic sources"],
        "reversible": True,
        "rollback_plan": "Remove rate limit rules",
        "risk_base": 0.25,
        "applicable_roles": ["core", "edge", "access"],
        "applicable_types": ["operational", "security"],
    },
    "restart_service": {
        "description": "Restart affected network service on device",
        "preconditions": ["service is in degraded state", "restart capability exists"],
        "effects": ["may restore service", "brief service interruption"],
        "blast_radius": ["target device"],
        "reversible": False,
        "rollback_plan": "Service restart cannot be undone; monitor for recovery",
        "risk_base": 0.5,
        "applicable_roles": ["core", "edge", "access"],
        "applicable_types": ["operational"],
    },
    "isolate_device": {
        "description": "Isolate device from network (quarantine)",
        "preconditions": ["device compromised or critically failing", "isolation capability exists"],
        "effects": ["stops threat spread", "device loses all connectivity"],
        "blast_radius": ["target device", "downstream dependents"],
        "reversible": True,
        "rollback_plan": "Restore network connectivity and ACLs",
        "risk_base": 0.7,
        "applicable_roles": ["core", "edge", "access"],
        "applicable_types": ["security"],
    },
    "block_ip": {
        "description": "Block malicious IP addresses at firewall",
        "preconditions": ["malicious IPs identified", "firewall management capability exists"],
        "effects": ["stops attack traffic", "may block legitimate if false positive"],
        "blast_radius": ["blocked IPs", "target device"],
        "reversible": True,
        "rollback_plan": "Remove firewall block rules",
        "risk_base": 0.3,
        "applicable_roles": ["core", "edge", "access"],
        "applicable_types": ["security"],
    },
    "failover": {
        "description": "Failover to standby device/cluster",
        "preconditions": ["standby available", "failover mechanism configured"],
        "effects": ["transfers traffic to standby", "brief interruption during switchover"],
        "blast_radius": ["target device", "standby device", "all traffic"],
        "reversible": True,
        "rollback_plan": "Failback to primary when healthy",
        "risk_base": 0.4,
        "applicable_roles": ["core"],
        "applicable_types": ["operational"],
    },
}


class ActionPlanner:
    def __init__(self):
        self.policy_table = ACTION_POLICY_TABLE

    def plan(self, state: NetworkState, diagnosis: Diagnosis) -> List[Action]:
        device = state.get_device(diagnosis.root_cause_device)
        if not device:
            return []

        applicable = self._get_applicable_actions(diagnosis, device)
        actions = []

        for action_type in applicable:
            policy = self.policy_table[action_type]
            target_devices = self._determine_targets(state, diagnosis, action_type, device)

            for target_id in target_devices:
                action = Action(
                    id=str(uuid.uuid4())[:8],
                    timestamp=time.time(),
                    action_type=action_type,
                    target_device=target_id,
                    parameters=self._get_parameters(state, diagnosis, action_type, target_id),
                    preconditions=policy["preconditions"].copy(),
                    effects=policy["effects"].copy(),
                    blast_radius=self._compute_blast_radius(state, target_id, action_type),
                    reversible=policy["reversible"],
                    rollback_plan=policy["rollback_plan"],
                )
                actions.append(action)
                state.actions.append(action)

        return actions

    def _get_applicable_actions(self, diagnosis: Diagnosis, device: Device) -> List[str]:
        applicable = []
        for action_type, policy in self.policy_table.items():
            if device.role in policy["applicable_roles"]:
                if diagnosis.diagnosis_type in policy["applicable_types"]:
                    applicable.append(action_type)
        return applicable

    def _determine_targets(
        self,
        state: NetworkState,
        diagnosis: Diagnosis,
        action_type: str,
        device: Device
    ) -> List[str]:
        targets = [diagnosis.root_cause_device]

        if action_type == "reroute_traffic":
            for neighbor_id in device.neighbors:
                neighbor = state.get_device(neighbor_id)
                if neighbor and neighbor.role in ["edge", "access"]:
                    targets.append(neighbor_id)

        return targets

    def _get_parameters(
        self,
        state: NetworkState,
        diagnosis: Diagnosis,
        action_type: str,
        target_id: str
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"diagnosis_id": diagnosis.id}
        device = state.get_device(target_id)

        if action_type == "reroute_traffic":
            params["alternate_paths"] = self._find_alternate_paths(state, target_id)
        elif action_type == "rate_limit":
            params["rate_limit_mbps"] = 100
            params["direction"] = "inbound"
        elif action_type == "restart_service":
            params["service_name"] = "routing_daemon"
        elif action_type == "isolate_device":
            params["isolation_level"] = "full"
        elif action_type == "block_ip":
            params["ip_list"] = device.metadata.get("malicious_ips", []) if device else []
        elif action_type == "failover":
            params["standby_id"] = self._find_standby(state, target_id)

        return params

    def _compute_blast_radius(self, state: NetworkState, target_id: str, action_type: str) -> List[str]:
        blast = [target_id]
        device = state.get_device(target_id)
        if not device:
            return blast

        if action_type in ["reroute_traffic", "failover"]:
            blast.extend(device.neighbors)

        if action_type == "isolate_device":
            blast.extend(self._get_downstream_devices(state, target_id))

        return blast

    def _find_alternate_paths(self, state: NetworkState, device_id: str) -> List[str]:
        device = state.get_device(device_id)
        if not device:
            return []
        paths = []
        for neighbor_id in device.neighbors:
            neighbor = state.get_device(neighbor_id)
            if neighbor and neighbor.role != device.role:
                paths.append(neighbor_id)
        return paths

    def _find_standby(self, state: NetworkState, device_id: str) -> Optional[str]:
        device = state.get_device(device_id)
        if not device:
            return None
        for neighbor_id in device.neighbors:
            neighbor = state.get_device(neighbor_id)
            if neighbor and neighbor.metadata.get("is_standby"):
                return neighbor_id
        return None

    def _get_downstream_devices(self, state: NetworkState, device_id: str) -> List[str]:
        downstream = []
        device = state.get_device(device_id)
        if not device:
            return downstream
        for neighbor_id in device.neighbors:
            neighbor = state.get_device(neighbor_id)
            if neighbor and neighbor.role in ["edge", "access", "leaf"]:
                downstream.append(neighbor_id)
                downstream.extend(self._get_downstream_devices(state, neighbor_id))
        return downstream

    def get_action_policy(self, action_type: str) -> Optional[Dict]:
        return self.policy_table.get(action_type)