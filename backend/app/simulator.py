from dataclasses import dataclass
from typing import Dict, List, Optional
from .state import NetworkState, Device, Action, SimulationResult
import copy


@dataclass
class SimulatedDeviceState:
    cpu: float
    mem: float
    loss: float
    latency: float
    queue_depth: int


class NetworkSimulator:
    def __init__(self, state: NetworkState):
        self.original_state = state
        self.simulation_ticks = 5

    def simulate_action(self, action: Action) -> SimulationResult:
        sim_state = self.original_state.clone()
        target_device = sim_state.get_device(action.target_device)
        if not target_device:
            return SimulationResult(
                action_id=action.id,
                safe=False,
                predicted_metrics={},
                new_violations=["Target device not found"],
                reasoning=["Simulation aborted: target device missing"],
            )

        predicted = self._run_simulation(sim_state, action, target_device)
        violations = self._check_violations(sim_state, predicted)
        safe = len(violations) == 0

        reasoning = self._generate_reasoning(action, predicted, violations, safe)

        return SimulationResult(
            action_id=action.id,
            safe=safe,
            predicted_metrics=predicted,
            new_violations=violations,
            reasoning=reasoning,
        )

    def _run_simulation(
        self,
        sim_state: NetworkState,
        action: Action,
        target_device: Device
    ) -> Dict[str, Dict[str, float]]:
        predicted = {}
        device_initial = self._capture_device_state(target_device)

        for tick in range(self.simulation_ticks):
            self._apply_action_effects(sim_state, action, target_device, tick)
            self._propagate_effects(sim_state, target_device, tick)

            for device_id, device in sim_state.devices.items():
                if device_id not in predicted:
                    predicted[device_id] = {}
                predicted[device_id][f"cpu_t{tick}"] = device.cpu
                predicted[device_id][f"loss_t{tick}"] = device.loss
                predicted[device_id][f"queue_t{tick}"] = device.queue_depth

        return predicted

    def _capture_device_state(self, device: Device) -> SimulatedDeviceState:
        return SimulatedDeviceState(
            cpu=device.cpu,
            mem=device.mem,
            loss=device.loss,
            latency=device.latency,
            queue_depth=device.queue_depth,
        )

    def _apply_action_effects(
        self,
        sim_state: NetworkState,
        action: Action,
        target_device: Device,
        tick: int
    ) -> None:
        if action.action_type == "reroute_traffic":
            target_device.cpu = max(20.0, target_device.cpu - 15.0 * (tick + 1) / self.simulation_ticks)
            target_device.queue_depth = max(0, target_device.queue_depth - 200 * (tick + 1))
            target_device.loss = max(0.5, target_device.loss - 2.0 * (tick + 1) / self.simulation_ticks)

        elif action.action_type == "rate_limit":
            target_device.cpu = max(30.0, target_device.cpu - 10.0 * (tick + 1) / self.simulation_ticks)
            target_device.queue_depth = max(0, target_device.queue_depth - 100 * (tick + 1))

        elif action.action_type == "restart_service":
            if tick < 2:
                target_device.cpu = min(95.0, target_device.cpu + 10.0)
                target_device.loss = min(20.0, target_device.loss + 5.0)
            else:
                target_device.cpu = max(20.0, target_device.cpu - 20.0 * (tick - 1) / (self.simulation_ticks - 2))
                target_device.loss = max(0.5, target_device.loss - 3.0 * (tick - 1) / (self.simulation_ticks - 2))

        elif action.action_type == "isolate_device":
            target_device.cpu = 0.0
            target_device.loss = 100.0
            target_device.queue_depth = 0
            for neighbor_id in target_device.neighbors:
                neighbor = sim_state.get_device(neighbor_id)
                if neighbor:
                    neighbor.loss = min(100.0, neighbor.loss + 50.0)

        elif action.action_type == "block_ip":
            target_device.cpu = max(30.0, target_device.cpu - 10.0 * (tick + 1) / self.simulation_ticks)
            target_device.loss = max(0.5, target_device.loss - 1.0 * (tick + 1) / self.simulation_ticks)

        elif action.action_type == "failover":
            standby_id = action.parameters.get("standby_id")
            if standby_id:
                standby = sim_state.get_device(standby_id)
                if standby:
                    standby.cpu = min(80.0, standby.cpu + 30.0)
                    standby.queue_depth += 500
            target_device.cpu = max(10.0, target_device.cpu - 30.0)
            target_device.loss = max(0.5, target_device.loss - 2.0 * (tick + 1) / self.simulation_ticks)

    def _propagate_effects(
        self,
        sim_state: NetworkState,
        target_device: Device,
        tick: int
    ) -> None:
        for neighbor_id in target_device.neighbors:
            neighbor = sim_state.get_device(neighbor_id)
            if not neighbor:
                continue

            if neighbor.role in ["edge", "access"]:
                if target_device.cpu > 80.0:
                    neighbor.cpu = min(90.0, neighbor.cpu + 5.0)
                    neighbor.loss = min(15.0, neighbor.loss + 2.0)
                elif target_device.cpu < 50.0:
                    neighbor.cpu = max(20.0, neighbor.cpu - 3.0)
                    neighbor.loss = max(0.5, neighbor.loss - 1.0)

    def _check_violations(self, sim_state: NetworkState, predicted: Dict) -> List[str]:
        violations = []
        for device_id, device in sim_state.devices.items():
            if device.cpu > 95.0:
                violations.append(f"{device_id}: CPU critical ({device.cpu:.1f}%)")
            if device.loss > 20.0:
                violations.append(f"{device_id}: Loss critical ({device.loss:.1f}%)")
            if device.queue_depth > 5000:
                violations.append(f"{device_id}: Queue depth critical ({device.queue_depth})")
            if device.mem > 95.0:
                violations.append(f"{device_id}: Memory critical ({device.mem:.1f}%)")
        return violations

    def _generate_reasoning(
        self,
        action: Action,
        predicted: Dict,
        violations: List[str],
        safe: bool
    ) -> List[str]:
        reasoning = [f"Simulated {action.action_type} on {action.target_device} for {self.simulation_ticks} ticks"]
        target = self.original_state.get_device(action.target_device)
        if target:
            reasoning.append(f"Initial: CPU={target.cpu:.1f}%, Loss={target.loss:.1f}%, Queue={target.queue_depth}")

        if action.target_device in predicted:
            final_tick = self.simulation_ticks - 1
            pred = predicted[action.target_device]
            cpu_key = f"cpu_t{final_tick}"
            loss_key = f"loss_t{final_tick}"
            if cpu_key in pred:
                reasoning.append(f"Predicted final: CPU={pred[cpu_key]:.1f}%, Loss={pred.get(loss_key, 0):.1f}%")

        if violations:
            reasoning.append(f"VIOLATIONS: {', '.join(violations)}")
        else:
            reasoning.append("No new violations predicted — action appears safe")

        return reasoning


def simulate_action(state: NetworkState, action: Action) -> SimulationResult:
    simulator = NetworkSimulator(state)
    return simulator.simulate_action(action)