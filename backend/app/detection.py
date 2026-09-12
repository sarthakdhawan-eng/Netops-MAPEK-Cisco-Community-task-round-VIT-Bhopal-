"""Statistical anomaly detection (stdlib only).

Method: EWMA baseline + z-score on residuals with a sustained-window rule.
This separates transient spikes (false positives) from sustained faults.
"""

from __future__ import annotations

import math

EWMA_ALPHA = 0.35
Z_THRESHOLD = 3.0
MIN_SUSTAINED = 3


def ewma(values: list[float], alpha: float = EWMA_ALPHA) -> list[float]:
    baseline: list[float] = []
    running: float | None = None
    for value in values:
        running = value if running is None else alpha * value + (1 - alpha) * running
        baseline.append(running)
    return baseline


def detect_series(values: list[float]) -> dict:
    """Return anomaly verdict for one metric series."""
    if len(values) < 4:
        return {"anomaly": False, "reason": "Insufficient history", "score": 0.0, "index": -1}
    baseline = ewma(values[:-1])
    mean = sum(baseline) / len(baseline)
    variance = sum((point - mean) ** 2 for point in baseline) / max(len(baseline) - 1, 1)
    std = math.sqrt(variance) or 1.0
    latest = values[-1]
    score = abs(latest - mean) / std
    sustained = sum(1 for point in values[-MIN_SUSTAINED:] if abs(point - mean) / std >= 2.0)
    if score >= Z_THRESHOLD and sustained >= MIN_SUSTAINED:
        return {"anomaly": True, "reason": f"Sustained deviation (z={score:.1f} over {sustained} samples)", "score": round(score, 2), "index": len(values) - 1}
    if score >= Z_THRESHOLD:
        return {"anomaly": False, "reason": f"Transient spike (z={score:.1f}); held as false positive", "score": round(score, 2), "index": len(values) - 1}
    return {"anomaly": False, "reason": "Within baseline", "score": round(score, 2), "index": -1}


def detect_device(cpu: list[float], loss: list[float], throughput: list[float]) -> dict:
    cpu_result = detect_series(cpu)
    loss_result = detect_series(loss)
    anomaly = bool(cpu_result["anomaly"] or loss_result["anomaly"])
    signals = []
    if cpu_result["anomaly"]:
        signals.append(f"CPU anomaly: {cpu_result['reason']}")
    if loss_result["anomaly"]:
        signals.append(f"Loss anomaly: {loss_result['reason']}")
    return {"anomaly": anomaly, "signals": signals, "cpu": cpu_result, "loss": loss_result, "throughput_latest": throughput[-1] if throughput else 0.0}
