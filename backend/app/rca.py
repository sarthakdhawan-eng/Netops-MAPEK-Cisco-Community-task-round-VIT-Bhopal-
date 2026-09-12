"""Root-cause and security classification (stdlib only)."""
from __future__ import annotations

TOPOLOGY = {"R-core": ["E-14", "E-19"], "E-14": ["R-core"], "E-19": ["R-core"], "FW-02": ["R-core"]}
CENTRAL_DEVICES = {"R-core"}

def classify_security(metric: str, detail: str, request_rate: float = 0.0) -> dict:
    text = f"{metric} {detail}".lower()
    scan_terms = ("scan", "port access", "source ranges", "req/s", "brute")
    if request_rate >= 5000 or sum(term in text for term in scan_terms) >= 2:
        return {"category": "Security", "reason": "Sequential access from multiple sources at high request rate"}
    return {"category": "Operational", "reason": "Signature matches congestion/failure rather than intrusion"}

def root_cause(candidates: list[dict]) -> dict:
    """Prefer a central device when it and downstream devices alarm together."""
    anomalous = [item for item in candidates if item.get("anomaly")]
    if not anomalous:
        return {"device": "", "reason": "No anomalous device", "confidence": 0}
    central = [item for item in anomalous if item["device"] in CENTRAL_DEVICES]
    if central and len(anomalous) > 1:
        downstream = sorted(item["device"] for item in anomalous if item["device"] not in CENTRAL_DEVICES)
        return {"device": central[0]["device"], "reason": f"Central overload explains downstream symptoms on {', '.join(downstream)}", "confidence": 94}
    best = max(anomalous, key=lambda item: item.get("score", 0.0))
    return {"device": best["device"], "reason": "Single-device anomaly without cascade evidence", "confidence": 88}
