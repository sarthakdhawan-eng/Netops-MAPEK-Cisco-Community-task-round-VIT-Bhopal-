from app.state import NetworkState, Device
from app.planner import decide_action
from app.pipeline import run_mapek_pipeline


def test_decide_action_helper_is_available_and_consistent():
    assert decide_action(18, True, "Operational") in {"auto", "approval"}
    assert decide_action(90, False, "Security") == "rejected"


def test_mapek_pipeline_runs_end_to_end():
    state = NetworkState()
    core = Device(id="R-core", name="R-core", role="core", cpu=95.0, mem=80.0, loss=9.0, latency=180.0, queue_depth=2500, neighbors=["E-14"])
    edge = Device(id="E-14", name="E-14", role="edge", cpu=60.0, mem=50.0, loss=2.0, latency=80.0, queue_depth=200, neighbors=["R-core"])
    state.add_device(core)
    state.add_device(edge)

    result = run_mapek_pipeline(state)

    assert result["decision"] in {"auto_execute", "human_approve", "reject"}
    assert result["diagnosis"]
    assert result["actions"]
