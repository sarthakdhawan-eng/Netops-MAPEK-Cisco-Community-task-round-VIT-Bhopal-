from dataclasses import dataclass
from typing import Any, Dict, List
from .state import NetworkState, Action, Device
from .decision_gate import Decision
import uuid
import time


class DeviceExecutionAdapter:
    """Safe placeholder adapter. It never connects to or changes a real device."""

    def execute(self, action: Action, state: NetworkState, device: Device) -> Dict[str, Any]:
        return {
            "adapter": "noop",
            "device": device.id,
            "action": action.action_type,
            "status": "simulated",
            "message": f"Simulated {action.action_type} for {device.name}; no device request was sent",
        }


@dataclass
class ExecutionResult:
    action_id: str
    success: bool
    message: str
    rollback_available: bool
    details: Dict[str, Any]


class ActionExecutor:
    """Apply approved actions to in-memory state for demonstration only."""
    def __init__(self, adapter: DeviceExecutionAdapter | None = None):
        self.adapter = adapter or DeviceExecutionAdapter()
        self.executed_actions: Dict[str, Dict[str, Any]] = {}
        self.known_actions: Dict[str, Action] = {}
        self.execution_log: List[Dict[str, Any]] = []

    def execute(
        self,
        state: NetworkState,
        action: Action,
        decision: Decision
    ) -> ExecutionResult:
        self.known_actions[action.id] = action
        if decision.decision != "auto_execute":
            return ExecutionResult(
                action_id=action.id,
                success=False,
                message=f"Decision was {decision.decision}, not auto_execute",
                rollback_available=False,
                details={},
            )

        device = state.get_device(action.target_device)
        if not device:
            return ExecutionResult(
                action_id=action.id,
                success=False,
                message=f"Target device {action.target_device} not found",
                rollback_available=False,
                details={},
            )

        if not self._check_preconditions(state, action, device):
            return ExecutionResult(
                action_id=action.id,
                success=False,
                message="Preconditions not met",
                rollback_available=False,
                details={},
            )

        adapter_result = self.adapter.execute(action, state, device)
        result = self._perform_action(state, action, device)
        if result.success:
            result.details.setdefault("adapter", adapter_result)
        return result

    def _check_preconditions(
        self,
        state: NetworkState,
        action: Action,
        device: Device
    ) -> bool:
        for pc in action.preconditions:
            if "overloaded" in pc.lower() and device.cpu < 80:
                return False
            if "standby" in pc.lower() and action.action_type == "failover":
                standby_id = action.parameters.get("standby_id")
                if not standby_id or not state.get_device(standby_id):
                    return False
            if "capability" in pc.lower():
                capability = self._capability_for(action.action_type)
                capabilities = device.metadata.get("capabilities", [])
                if not capability or capability not in capabilities:
                    return False
        return True

    @staticmethod
    def _capability_for(action_type: str) -> str | None:
        return {
            "reroute_traffic": "routing",
            "rate_limit": "rate_limit",
            "restart_service": "service_restart",
            "isolate_device": "isolation",
            "block_ip": "firewall_rules",
            "failover": "failover",
        }.get(action_type)

    def _perform_action(
        self,
        state: NetworkState,
        action: Action,
        device: Device
    ) -> ExecutionResult:
        previous_state = {
            "cpu": device.cpu,
            "mem": device.mem,
            "loss": device.loss,
            "latency": device.latency,
            "queue_depth": device.queue_depth,
        }
        previous_states = {device.id: previous_state}
        standby_id = action.parameters.get("standby_id") if action.action_type == "failover" else None
        standby = state.get_device(standby_id) if standby_id else None
        if standby:
            previous_states[standby.id] = {
                "cpu": standby.cpu,
                "mem": standby.mem,
                "loss": standby.loss,
                "latency": standby.latency,
                "queue_depth": standby.queue_depth,
            }

        details: Dict[str, Any] = {"previous_state": previous_state}

        if action.action_type == "reroute_traffic":
            device.cpu = max(20.0, device.cpu - 20.0)
            device.queue_depth = max(0, device.queue_depth - 500)
            device.loss = max(0.5, device.loss - 3.0)
            details["new_state"] = {"cpu": device.cpu, "queue_depth": device.queue_depth, "loss": device.loss}
            message = f"Simulated reroute on {device.name}; CPU now {device.cpu:.1f}%. No device command was sent."

        elif action.action_type == "rate_limit":
            device.cpu = max(30.0, device.cpu - 15.0)
            device.queue_depth = max(0, device.queue_depth - 300)
            details["new_state"] = {"cpu": device.cpu, "queue_depth": device.queue_depth}
            message = f"Simulated rate limit on {device.name}; CPU now {device.cpu:.1f}%. No device command was sent."

        elif action.action_type == "restart_service":
            device.cpu = max(15.0, device.cpu - 30.0)
            device.loss = max(0.5, device.loss - 5.0)
            details["new_state"] = {"cpu": device.cpu, "loss": device.loss}
            message = f"Simulated service restart on {device.name}; CPU now {device.cpu:.1f}%. No device command was sent."

        elif action.action_type == "isolate_device":
            device.cpu = 0.0
            device.loss = 100.0
            device.queue_depth = 0
            details["isolated"] = True
            message = f"Simulated isolation of {device.name}. No device command was sent."

        elif action.action_type == "block_ip":
            ip_list = action.parameters.get("ip_list", [])
            device.cpu = max(30.0, device.cpu - 15.0)
            device.loss = max(0.5, device.loss - 2.0)
            details["blocked_ips"] = ip_list
            details["new_state"] = {"cpu": device.cpu, "loss": device.loss}
            message = f"Simulated block of {len(ip_list)} IPs on {device.name}; CPU now {device.cpu:.1f}%. No device command was sent."

        elif action.action_type == "failover":
            standby_id = action.parameters.get("standby_id")
            standby = state.get_device(standby_id) if standby_id else None
            if standby:
                standby.cpu = min(80.0, standby.cpu + 40.0)
                standby.queue_depth += 1000
            device.cpu = max(10.0, device.cpu - 40.0)
            device.loss = max(0.5, device.loss - 5.0)
            details["standby_id"] = standby_id
            details["new_state"] = {"cpu": device.cpu, "loss": device.loss}
            message = f"Simulated failover from {device.name} to {standby.name if standby else 'unknown'}. No device command was sent."

        else:
            return ExecutionResult(
                action_id=action.id,
                success=False,
                message=f"Unknown action type: {action.action_type}",
                rollback_available=False,
                details={},
            )

        self.executed_actions[action.id] = {
            "action": action,
            "previous_state": previous_state,
            "previous_states": previous_states,
            "target_device": action.target_device,
            "timestamp": time.time(),
        }

        self.execution_log.append({
            "action_id": action.id,
            "action_type": action.action_type,
            "target": action.target_device,
            "decision": "auto_execute",
            "execution_mode": "simulation_only",
            "timestamp": time.time(),
            "success": True,
        })

        return ExecutionResult(
            action_id=action.id,
            success=True,
            message=message,
            rollback_available=action.reversible,
            details=details,
        )

    def rollback(self, state: NetworkState, action_id: str) -> ExecutionResult:
        if action_id not in self.executed_actions:
            known_action = self.known_actions.get(action_id)
            if known_action and not known_action.reversible:
                return ExecutionResult(
                    action_id=action_id,
                    success=False,
                    message="Action is not reversible",
                    rollback_available=False,
                    details={},
                )
            return ExecutionResult(
                action_id=action_id,
                success=False,
                message="Action not found in execution history",
                rollback_available=False,
                details={},
            )

        record = self.executed_actions[action_id]
        action = record["action"]
        previous_states = record.get("previous_states", {record["target_device"]: record["previous_state"]})
        target_id = record["target_device"]

        if not action.reversible:
            return ExecutionResult(
                action_id=action_id,
                success=False,
                message="Action is not reversible",
                rollback_available=False,
                details={},
            )

        devices = {device_id: state.get_device(device_id) for device_id in previous_states}
        if any(device is None for device in devices.values()):
            return ExecutionResult(
                action_id=action_id,
                success=False,
                message="An affected device no longer exists",
                rollback_available=False,
                details={},
            )

        for device_id, snapshot in previous_states.items():
            device = devices[device_id]
            device.cpu = snapshot["cpu"]
            device.mem = snapshot["mem"]
            device.loss = snapshot["loss"]
            device.latency = snapshot["latency"]
            device.queue_depth = snapshot["queue_depth"]

        self.execution_log.append({
            "action_id": action_id,
            "action_type": f"rollback_{action.action_type}",
            "target": target_id,
            "decision": "rollback",
            "timestamp": time.time(),
            "success": True,
        })

        del self.executed_actions[action_id]

        return ExecutionResult(
            action_id=action_id,
            success=True,
            message=f"Rolled back {action.action_type} on {target_id}",
            rollback_available=False,
            details={"restored_states": previous_states},
        )

    def get_execution_log(self) -> List[Dict]:
        return self.execution_log
