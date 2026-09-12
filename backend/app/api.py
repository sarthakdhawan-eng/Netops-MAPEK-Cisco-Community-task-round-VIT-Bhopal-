"""Small SQLite-backed API for the NetOps control room.

The API deliberately uses the standard library so the existing backend remains
portable. It persists incidents, analyst notes, and audit events in SQLite.
"""

from __future__ import annotations

import json
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "netops.db"
SESSION_TTL = 60 * 60 * 8
FRONTEND_ORIGINS = {origin.strip() for origin in os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173,http://127.0.0.1:4173").split(",") if origin.strip()}

INCIDENTS = [
    {"id": "INC-2048", "title": "Core router saturation", "device": "R-core", "type": "Operational", "severity": "High", "confidence": 96, "age": "04 min", "metric": "CPU 95%", "detail": "Queue depth is rising across two downstream edges.", "action": "Reroute traffic", "risk": 18},
    {"id": "INC-2047", "title": "East ingress packet loss", "device": "E-14", "type": "Operational", "severity": "Medium", "confidence": 89, "age": "11 min", "metric": "Loss 6.8%", "detail": "Loss is sustained above baseline on the east ingress path.", "action": "Rate limit", "risk": 27},
    {"id": "INC-2045", "title": "Unexpected scan pattern", "device": "FW-02", "type": "Security", "severity": "Critical", "confidence": 93, "age": "18 min", "metric": "12.4k req/s", "detail": "Sequential port access detected from multiple source ranges.", "action": "Block source IPs", "risk": 61},
]


DEVICES = [
    {"name": "R-core", "role": "Core router", "host": "192.168.1.1", "method": "ping", "state": "Degraded", "cpu": 95, "latency": 182, "tone": "warn"},
    {"name": "E-14", "role": "Edge gateway", "host": "192.168.1.14", "method": "https", "state": "Watch", "cpu": 71, "latency": 84, "tone": "watch"},
    {"name": "E-19", "role": "Edge gateway", "host": "192.168.1.19", "method": "ping", "state": "Healthy", "cpu": 38, "latency": 31, "tone": "good"},
    {"name": "FW-02", "role": "Security firewall", "host": "192.168.1.2", "method": "https", "state": "Investigate", "cpu": 82, "latency": 66, "tone": "critical"},
]

TELEMETRY_SEED = {
    "24h": {"label": "Last 24 hours", "cpu": [32, 45, 58, 71, 82, 95], "loss": [0.4, 1.1, 2.2, 4.2, 6.8, 2.9], "throughput": [42, 58, 74, 88, 96, 78]},
    "7d": {"label": "Last 7 days", "cpu": [44, 52, 61, 58, 66, 71], "loss": [0.8, 1.1, 2.4, 6.8, 3.2, 1.2], "throughput": [55, 62, 71, 88, 79, 60]},
    "30d": {"label": "Last 30 days", "cpu": [38, 47, 52, 56, 64, 69], "loss": [0.6, 1.4, 2.1, 3.4, 1.7, 1.1], "throughput": [50, 63, 72, 84, 74, 66]},
}


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                message TEXT NOT NULL,
                tone TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analyst_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS devices (
                name TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                range_name TEXT NOT NULL,
                series TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device TEXT NOT NULL,
                cpu REAL NOT NULL,
                loss REAL NOT NULL,
                throughput REAL NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                action TEXT NOT NULL,
                risk INTEGER NOT NULL,
                simulated_passed INTEGER NOT NULL,
                decision TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        for incident in INCIDENTS:
            connection.execute(
                "INSERT OR IGNORE INTO incidents (id, payload, updated_at) VALUES (?, ?, ?)",
                (incident["id"], json.dumps(incident), time.time()),
            )
        for device in DEVICES:
            connection.execute(
                "INSERT OR REPLACE INTO devices (name, payload, updated_at) VALUES (?, ?, ?)",
                (device["name"], json.dumps(device), time.time()),
            )
        for range_name, series in TELEMETRY_SEED.items():
            row = connection.execute("SELECT id FROM telemetry WHERE range_name = ?", (range_name,)).fetchone()
            if not row:
                connection.execute(
                    "INSERT INTO telemetry (range_name, series, updated_at) VALUES (?, ?, ?)",
                    (range_name, json.dumps(series), time.time()),
                )


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None and len(password) < 10:
        raise ValueError("Password must be at least 10 characters")
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), actual_salt, 240_000)
    return actual_salt.hex(), digest.hex()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticated_user(handler: BaseHTTPRequestHandler, connection: sqlite3.Connection) -> sqlite3.Row | None:
    raw_token = handler.headers.get("Authorization", "")
    if not raw_token.startswith("Bearer "):
        return None
    token_hash = hash_token(raw_token[7:].strip())
    row = connection.execute(
        "SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
        (token_hash, time.time()),
    ).fetchone()
    return row


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    request_origin = handler.headers.get("Origin", "")
    allowed_origin = request_origin if request_origin in FRONTEND_ORIGINS else next(iter(FRONTEND_ORIGINS), "")
    handler.send_header("Access-Control-Allow-Origin", allowed_origin)
    handler.send_header("Vary", "Origin")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_OPTIONS(self) -> None:
        json_response(self, {})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        with connect() as connection:
            user = authenticated_user(self, connection)
            if path in {"/api/state", "/api/profile", "/api/devices", "/api/telemetry", "/api/analytics"} and not user:
                json_response(self, {"error": "Authentication required"}, 401)
                return
            if path == "/api/health":
                json_response(self, {"status": "ok", "database": str(DB_PATH), "connected": True})
                return
            if path == "/api/state":
                incidents = [json.loads(row["payload"]) for row in connection.execute("SELECT payload FROM incidents ORDER BY updated_at DESC")]
                events = [dict(row) for row in connection.execute("SELECT source, message, tone, created_at FROM audit_events ORDER BY id DESC LIMIT 8")]
                devices = [json.loads(row["payload"]) for row in connection.execute("SELECT payload FROM devices ORDER BY name")]
                json_response(self, {"connected": True, "incidents": incidents, "events": events, "devices": devices})
                return
            if path == "/api/profile":
                json_response(self, {"name": user["display_name"], "email": user["email"], "role": "Network lead", "workspace": "Northstar / Production", "access": "Production control"})
                return
            if path == "/api/devices":
                devices = [json.loads(row["payload"]) for row in connection.execute("SELECT payload FROM devices ORDER BY name")]
                json_response(self, {"devices": devices, "connected": True})
                return
            if path in {"/api/telemetry", "/api/analytics"}:
                query = dict(part.split("=", 1) if "=" in part else (part, "") for part in parsed.query.split("&") if part)
                range_name = query.get("range", "24h")
                row = connection.execute("SELECT series FROM telemetry WHERE range_name = ?", (range_name,)).fetchone()
                if not row:
                    json_response(self, {"error": "Unknown telemetry range"}, 400)
                    return
                series = json.loads(row["series"])
                json_response(self, {"range": range_name, "label": series["label"], "cpu": series["cpu"], "loss": series["loss"], "throughput": series["throughput"]})
                return
        json_response(self, {"error": "Route not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            json_response(self, {"error": "Request body must be valid JSON"}, 400)
            return

        with connect() as connection:
            if path == "/api/signup":
                email = str(payload.get("email", "")).strip().lower()
                display_name = str(payload.get("display_name", "")).strip()
                password = str(payload.get("password", ""))
                if not email or "@" not in email or not display_name:
                    json_response(self, {"error": "Name and a valid email are required"}, 400)
                    return
                try:
                    salt, password_hash = hash_password(password)
                except ValueError as error:
                    json_response(self, {"error": str(error)}, 400)
                    return
                try:
                    connection.execute(
                        "INSERT INTO users (email, display_name, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                        (email, display_name, salt, password_hash, time.time()),
                    )
                except sqlite3.IntegrityError:
                    json_response(self, {"error": "An account with that email already exists"}, 409)
                    return
                json_response(self, {"created": True}, 201)
                return
            if path == "/api/login":
                email = str(payload.get("email", "")).strip().lower()
                password = str(payload.get("password", ""))
                user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                if not user:
                    json_response(self, {"error": "Email or password is incorrect"}, 401)
                    return
                _, candidate_hash = hash_password(password or " ", bytes.fromhex(user["password_salt"]))
                if not hmac.compare_digest(candidate_hash, user["password_hash"]):
                    json_response(self, {"error": "Email or password is incorrect"}, 401)
                    return
                token = secrets.token_urlsafe(32)
                connection.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (hash_token(token), user["id"], time.time() + SESSION_TTL))
                json_response(self, {"token": token, "user": {"name": user["display_name"], "email": user["email"]}})
                return
            if path == "/api/logout":
                raw_token = self.headers.get("Authorization", "")
                if raw_token.startswith("Bearer "):
                    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(raw_token[7:].strip()),))
                json_response(self, {"logged_out": True})
                return
            user = authenticated_user(self, connection)
            if not user:
                json_response(self, {"error": "Authentication required"}, 401)
                return
            if path == "/api/analyst":
                from .rca import classify_security, root_cause
                from .planner import plan, risk_score
                incident_id = payload.get("incident_id")
                evidence = str(payload.get("evidence", "")).strip()
                row = connection.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone()
                if not row:
                    json_response(self, {"error": "Incident not found"}, 404)
                    return
                incident = json.loads(row["payload"])
                security = classify_security(incident.get("metric", ""), incident.get("detail", ""))
                cause = root_cause([{"device": incident.get("device", ""), "anomaly": True, "score": float(incident.get("confidence", 80))}])
                candidates = plan(security["category"], incident.get("severity", "Medium"))
                scored = [{"action": action, **risk_score(action, incident.get("severity", "Medium"), security["category"])} for action in candidates]
                best = min(scored, key=lambda item: item["risk"])
                evidence_note = f" Operator evidence received for review: {evidence[:500]}." if evidence else " No operator evidence was supplied, so open the inspection guide and collect the requested device observations before taking action."
                answer = (f"{security['category']} event on {incident['device']}: {security['reason']}. {cause['reason']} with {cause['confidence']}% confidence.{evidence_note} Recommended containment is {best['action'].lower()} at {best['risk']}% risk; simulation is required before approval. The agent is read-only and cannot access or change the device without an approved execution path.")
                connection.execute("INSERT INTO analyst_notes (incident_id, answer, created_at) VALUES (?, ?, ?)", (incident_id, answer, time.time()))
                connection.execute("INSERT INTO audit_events (source, message, tone, created_at) VALUES (?, ?, ?, ?)", ("AI analyst", f"Generated assessment for {incident_id}", "good", time.time()))
                json_response(self, {"incident_id": incident_id, "answer": answer, "confidence": cause["confidence"], "recommended_action": best["action"], "category": security["category"], "evidence_received": bool(evidence), "next_step": "Run safety simulation" if evidence else "Collect operator evidence", "candidates": scored})
                return
            if path == "/api/events":
                source = str(payload.get("source", "Operator"))
                message = str(payload.get("message", "")).strip()
                tone = str(payload.get("tone", "muted"))
                if not message:
                    json_response(self, {"error": "Event message is required"}, 400)
                    return
                connection.execute("INSERT INTO audit_events (source, message, tone, created_at) VALUES (?, ?, ?, ?)", (source, message, tone, time.time()))
                json_response(self, {"saved": True})
                return
            if path == "/api/simulate":
                from .planner import decide, risk_score, simulate
                incident_id = str(payload.get("incident_id", ""))
                row = connection.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone() if incident_id else None
                if not row:
                    json_response(self, {"error": "Incident not found"}, 404)
                    return
                incident = json.loads(row["payload"])
                action = str(payload.get("action", "")).strip()
                if not action:
                    json_response(self, {"error": "Action is required"}, 400)
                    return
                category = "Security" if incident.get("type") == "Security" else "Operational"
                current_cpu = 95.0 if incident.get("device") == "R-core" else 70.0
                scored = risk_score(action, incident.get("severity", "High"), category)
                result = simulate(action, current_cpu, capacity_margin=float(payload.get("capacity_margin", 25.0)))
                decision = decide(scored["risk"], result["passed"], category)
                connection.execute("INSERT INTO decisions (incident_id, action, risk, simulated_passed, decision, created_at) VALUES (?, ?, ?, ?, ?, ?)", (incident_id or "adhoc", action, scored["risk"], int(result["passed"]), decision, time.time()))
                connection.execute("INSERT INTO audit_events (source, message, tone, created_at) VALUES (?, ?, ?, ?)", ("Simulator", f"{action} for {incident_id or 'adhoc'}: {result['reason']} -> {decision}", "good" if result["passed"] else "critical", time.time()))
                json_response(self, {"incident_id": incident_id, "action": action, "risk": scored["risk"], "factors": scored["factors"], "predicted_cpu": result["predicted_cpu"], "passed": result["passed"], "reason": result["reason"], "decision": decision})
                return
            if path == "/api/decide":
                from .planner import decide_action
                incident_id = str(payload.get("incident_id", "")).strip()
                row = connection.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone() if incident_id else None
                if not row:
                    json_response(self, {"error": "Incident not found"}, 404)
                    return
                incident = json.loads(row["payload"])
                action = str(payload.get("action", "")).strip()
                if not action:
                    json_response(self, {"error": "Action is required"}, 400)
                    return
                latest = connection.execute(
                    "SELECT risk, simulated_passed, decision FROM decisions WHERE incident_id = ? AND action = ? ORDER BY id DESC LIMIT 1",
                    (incident_id, action),
                ).fetchone()
                if not latest or not latest["simulated_passed"]:
                    json_response(self, {"error": "A passing server-side simulation is required"}, 409)
                    return
                decision = decide_action(int(latest["risk"]), True, "Security" if incident.get("type") == "Security" else "Operational")
                connection.execute("INSERT INTO decisions (incident_id, action, risk, simulated_passed, decision, created_at) VALUES (?, ?, ?, ?, ?, ?)", (incident_id, action, int(latest["risk"]), 1, decision, time.time()))
                json_response(self, {"decision": decision, "incident_id": incident_id, "action": action, "risk": int(latest["risk"])})
                return
            if path == "/api/inject-fault":
                from .detection import detect_device
                device = str(payload.get("device", "R-core")).strip()
                known_devices = {row["name"] for row in connection.execute("SELECT name FROM devices")}
                if device not in known_devices:
                    json_response(self, {"error": "Unknown device"}, 400)
                    return
                cpu = [float(value) for value in payload.get("cpu", [40, 42, 44, 43, 45, 95, 96, 97])]
                loss = [float(value) for value in payload.get("loss", [0.4, 0.5, 0.6, 0.5, 0.7, 6.8, 7.1, 6.9])]
                throughput = [float(value) for value in payload.get("throughput", [50, 55, 60, 58, 62, 88, 90, 89])]
                verdict = detect_device(cpu, loss, throughput)
                for value_cpu, value_loss, value_tp in zip(cpu, loss, throughput):
                    connection.execute("INSERT INTO telemetry_history (device, cpu, loss, throughput, created_at) VALUES (?, ?, ?, ?, ?)", (device, value_cpu, value_loss, value_tp, time.time()))
                if verdict["anomaly"]:
                    incident_id = f"INC-{device}-{int(time.time()) % 100000}"
                    incident = {"id": incident_id, "title": f"{device} saturation detected", "device": device, "type": "Operational", "severity": "High", "confidence": 93, "age": "00 min", "metric": f"CPU {cpu[-1]}%", "detail": "; ".join(verdict["signals"]) or "Statistical detector fired.", "action": "Reroute traffic", "risk": 28}
                    connection.execute("INSERT OR IGNORE INTO incidents (id, payload, updated_at) VALUES (?, ?, ?)", (incident_id, json.dumps(incident), time.time()))
                    connection.execute("INSERT INTO audit_events (source, message, tone, created_at) VALUES (?, ?, ?, ?)", ("Detector", f"Anomaly sustained on {device}", "warn", time.time()))
                    json_response(self, {"detected": True, "incident_id": incident_id, "verdict": verdict}, 201)
                else:
                    json_response(self, {"detected": False, "verdict": verdict})
                return
        json_response(self, {"error": "Route not found"}, 404)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"NetOps API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
