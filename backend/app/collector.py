"""Device collector for the NetOps control room."""
from __future__ import annotations
import argparse
import json
import sqlite3
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from .api import DB_PATH, connect, init_db

@dataclass
class DeviceTarget:
    name: str
    host: str
    method: str = "ping"
    metrics_url: str = ""
    role: str = ""

DEFAULT_DEVICES = [
    DeviceTarget(name="R-core", host="192.168.1.1", method="ping", role="Core router"),
    DeviceTarget(name="E-14", host="192.168.1.14", method="https", role="Edge gateway"),
    DeviceTarget(name="E-19", host="192.168.1.19", method="ping", role="Edge gateway"),
    DeviceTarget(name="FW-02", host="192.168.1.2", method="https", role="Security firewall"),
]
CPU_CRITICAL = 90.0
LOSS_CRITICAL = 5.0

def ping_latency_ms(host: str, timeout_s: int = 2) -> float | None:
    flag = "-n" if subprocess.os.name == "nt" else "-c"
    timeout_flag = "-w" if subprocess.os.name == "nt" else "-W"
    try:
        completed = subprocess.run(["ping", flag, "1", timeout_flag, str(timeout_s), host], capture_output=True, text=True, timeout=timeout_s + 2)
    except (OSError, subprocess.SubprocessError):
        return None
    output = completed.stdout.lower()
    for token in ("average =", "avg =", "time="):
        if token in output:
            try:
                chunk = output.split(token, 1)[1].split("ms")[0].strip().split()[-1]
                return float(chunk.replace(",", "."))
            except (IndexError, ValueError):
                continue
    return None if completed.returncode != 0 else 1.0

def fetch_https_metrics(url: str, timeout_s: int = 5) -> dict:
    if not url:
        return {}
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except Exception:
        return {}

def classify(cpu: float, loss: float, latency: float | None) -> tuple[str, str]:
    if cpu >= CPU_CRITICAL or loss >= LOSS_CRITICAL:
        return ("Degraded" if cpu >= CPU_CRITICAL else "Investigate", "critical" if loss >= LOSS_CRITICAL else "warn")
    if cpu >= 70 or (latency or 0) >= 80:
        return ("Watch", "watch")
    return ("Healthy", "good")

def load_devices(config_path: str | None) -> list[DeviceTarget]:
    from pathlib import Path
    if not config_path:
        return list(DEFAULT_DEVICES)
    path = Path(config_path)
    if not path.exists():
        return list(DEFAULT_DEVICES)
    devices: list[DeviceTarget] = []
    current: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            if current.get("name"):
                devices.append(DeviceTarget(name=current.get("name", ""), host=current.get("host", ""), method=current.get("method", "ping"), metrics_url=current.get("metrics_url", ""), role=current.get("role", "")))
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif ":" in stripped and not stripped.startswith("#"):
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
    if current.get("name"):
        devices.append(DeviceTarget(name=current.get("name", ""), host=current.get("host", ""), method=current.get("method", "ping"), metrics_url=current.get("metrics_url", ""), role=current.get("role", "")))
    return devices or list(DEFAULT_DEVICES)

def collect_once(target: DeviceTarget) -> dict:
    latency = ping_latency_ms(target.host)
    metrics = fetch_https_metrics(target.metrics_url) if target.method == "https" else {}
    cpu = float(metrics.get("cpu", 40.0))
    loss = float(metrics.get("loss", 0.4))
    if latency is None:
        latency = float(metrics.get("latency_ms", 35.0))
    state, tone = classify(cpu, loss, latency)
    return {"name": target.name, "role": target.role or "Managed device", "host": target.host, "method": target.method, "state": state, "cpu": round(cpu, 1), "latency": round(latency, 1), "tone": tone, "loss": round(loss, 2)}

def store_reading(connection, reading: dict) -> None:
    connection.execute("INSERT OR REPLACE INTO devices (name, payload, updated_at) VALUES (?, ?, ?)", (reading["name"], json.dumps(reading), time.time()))
    connection.execute("INSERT INTO telemetry_history (device, cpu, loss, throughput, created_at) VALUES (?, ?, ?, ?, ?)", (reading["name"], float(reading["cpu"]), float(reading.get("loss", 0.4)), float(reading.get("throughput", 60.0)), time.time()))
    connection.execute("INSERT INTO audit_events (source, message, tone, created_at) VALUES (?, ?, ?, ?)", ("Collector", f"{reading['name']}: CPU {reading['cpu']}% / {reading['latency']} ms", reading["tone"], time.time()))
    history = [row["cpu"] for row in connection.execute("SELECT cpu FROM telemetry_history WHERE device = ? ORDER BY id DESC LIMIT 8", (reading["name"],)).fetchall()][::-1]
    losses = [row["loss"] for row in connection.execute("SELECT loss FROM telemetry_history WHERE device = ? ORDER BY id DESC LIMIT 8", (reading["name"],)).fetchall()][::-1]
    if len(history) >= 4:
        from .detection import detect_series
        verdict = detect_series(history)
        loss_verdict = detect_series(losses)
        if verdict["anomaly"] or loss_verdict["anomaly"]:
            incident_id = f"INC-{reading['name']}-{int(time.time()) % 100000}"
            incident = {"id": incident_id, "title": f"{reading['name']} saturation detected", "device": reading["name"], "type": "Operational", "severity": "High", "confidence": 92, "age": "00 min", "metric": f"CPU {reading['cpu']}%", "detail": verdict["reason"], "action": "Reroute traffic", "risk": 28}
            connection.execute("INSERT OR IGNORE INTO incidents (id, payload, updated_at) VALUES (?, ?, ?)", (incident_id, json.dumps(incident), time.time()))

def poll_once(config: str | None) -> int:
    init_db()
    targets = load_devices(config)
    print(f"Collector database: {DB_PATH}")
    with connect() as connection:
        for target in targets:
            reading = collect_once(target)
            store_reading(connection, reading)
            print(f"{reading['name']} ({reading['host']}): CPU {reading['cpu']}% latency {reading['latency']} ms -> {reading['state']}")
    return 0

def main() -> None:
    parser = argparse.ArgumentParser(description="Poll controlled devices and store telemetry")
    parser.add_argument("--config", default=None, help="Path to devices YAML file")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between polls in loop mode")
    parser.add_argument("--once", action="store_true", help="Poll a single time and exit")
    parser.add_argument("--loop", action="store_true", help="Poll continuously")
    args = parser.parse_args()
    if args.loop:
        init_db()
        while True:
            poll_once(args.config)
            time.sleep(args.interval)
    else:
        poll_once(args.config)

if __name__ == "__main__":
    main()

