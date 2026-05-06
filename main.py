"""
MorioCRM — Echtzeit Backend
FastAPI + WebSockets: alle Nutzer sehen Änderungen sofort
Telefonie via Placetel (SIP/WebRTC mit JsSIP)
"""

import json
import asyncio
import os
import threading
from pathlib import Path
from typing import Dict, Set, Optional, List, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
import uuid
import time

# ── PLACETEL ──────────────────────────────────────────────────────────────
PLACETEL_SIP_DOMAIN = os.environ.get("PLACETEL_SIP_DOMAIN", "sip.placetel.de")
PLACETEL_WSS        = os.environ.get("PLACETEL_WSS", "wss://sip.placetel.de/ws")

# Ein SIP-Account pro Nutzer
PLACETEL_USERS = {
    "Tyrone": {"username": os.environ.get("PLACETEL_USER_TYRONE", ""), "password": os.environ.get("PLACETEL_PASS_TYRONE", "")},
    "Kevin":  {"username": os.environ.get("PLACETEL_USER_KEVIN",  ""), "password": os.environ.get("PLACETEL_PASS_KEVIN",  "")},
    "Marc":   {"username": os.environ.get("PLACETEL_USER_MARC",   ""), "password": os.environ.get("PLACETEL_PASS_MARC",   "")},
    "Timo":   {"username": os.environ.get("PLACETEL_USER_TIMO",   ""), "password": os.environ.get("PLACETEL_PASS_TIMO",   "")},
}

PLACETEL_CONFIGURED = bool(any(v["username"] for v in PLACETEL_USERS.values()))

app = FastAPI(title="MorioCRM", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DATENSPEICHER ─────────────────────────────────────────────────────────
DATA_FILE = Path(os.environ.get("DATA_DIR", ".")) / "crm_data.json"

def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return get_demo_data()

_save_lock = threading.Lock()
_save_pending = False

def save_data(data: dict):
    global _save_pending
    if _save_pending:
        return
    _save_pending = True
    snapshot = json.dumps(data, ensure_ascii=False, indent=2)
    def _write():
        global _save_pending
        with _save_lock:
            DATA_FILE.write_text(snapshot, encoding="utf-8")
        _save_pending = False
    threading.Thread(target=_write, daemon=True).start()

def get_demo_data() -> dict:
    return {
        "kunden": [
            {"id": "k1", "name": "Trattoria Bella Italia", "branche": "Restaurant", "kontakt": "Marco Rossi", "email": "marco@bella.de", "tel": "+49 89 123456", "website": "https://bella-italia.de", "status": "aktiv", "mrr": 299, "notizen": "Top-Kunde, will Yelp ausweiten", "seit": "2024-03-15", "createdBy": "Tyrone"},
            {"id": "k2", "name": "Sanitär Müller GmbH", "branche": "Handwerk", "kontakt": "Hans Müller", "email": "mueller@sanitaer.de", "tel": "+49 711 654321", "website": "", "status": "aktiv", "mrr": 199, "notizen": "Fokus Google Bewertungen", "seit": "2024-06-01", "createdBy": "Kevin"},
            {"id": "k3", "name": "Dr. med. Schmidt", "branche": "Medizin", "kontakt": "Dr. Petra Schmidt", "email": "praxis@schmidt.de", "tel": "+49 30 987654", "website": "https://praxis-schmidt.de", "status": "trial", "mrr": 0, "notizen": "Trial bis Ende Monat", "seit": "2024-10-01", "createdBy": "Marc"},
            {"id": "k4", "name": "Auto Ziegler AG", "branche": "Automotive", "kontakt": "Klaus Ziegler", "email": "ziegler@auto.de", "tel": "+49 221 111222", "website": "", "status": "aktiv", "mrr": 499, "notizen": "3 Standorte, Großkunde", "seit": "2024-01-20", "createdBy": "Tyrone"},
            {"id": "k5", "name": "Hotel Seehof", "branche": "Tourismus", "kontakt": "Anna Weber", "email": "weber@seehof.de", "tel": "+49 8151 333444", "website": "https://hotel-seehof.de", "status": "inaktiv", "mrr": 0, "notizen": "Vertrag abgelaufen", "seit": "2023-11-01", "createdBy": "Kevin"},
        ],
        "deals": [
            {"id": "d1", "company": "Zahnarzt Dr. Braun", "contact": "Dr. Braun", "value": 349, "phase": "demo", "prob": 70, "close": "2025-01-15", "notes": "Demo diese Woche"},
            {"id": "d2", "company": "Bäckerei Hoffmann", "contact": "Sandra Hoffmann", "value": 149, "phase": "lead", "prob": 30, "close": "2025-02-10", "notes": "Kaltakquise, interessiert"},
            {"id": "d3", "company": "Reifenservice Kern", "contact": "Dieter Kern", "value": 199, "phase": "angebot", "prob": 80, "close": "2025-01-20", "notes": "Angebot gesendet"},
            {"id": "d4", "company": "Beautystudio Lux", "contact": "Maria Lux", "value": 249, "phase": "kontakt", "prob": 50, "close": "2025-02-01", "notes": "Follow-up geplant"},
            {"id": "d5", "company": "Steuerbüro Fischer", "contact": "Michael Fischer", "value": 399, "phase": "gewonnen", "prob": 100, "close": "2024-11-30", "notes": "Abschluss! Onboarding läuft"},
        ],
        "kamps": [],
        "tasks": [],
        "calls": [],
        "contacts": [],
        "activities": []
    }

DB = load_data()

# ── WEBSOCKET MANAGER ─────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user: str):
        await websocket.accept()
        self.connections[user] = websocket

    def disconnect(self, user: str):
        self.connections.pop(user, None)

    async def broadcast(self, message: dict, exclude: str = None):
        dead = []
        for user, ws in self.connections.items():
            if user == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(user)
        for u in dead:
            self.connections.pop(u, None)

    async def send_to(self, user: str, message: dict):
        ws = self.connections.get(user)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.connections.pop(user, None)

    def online_users(self) -> list:
        return list(self.connections.keys())

mgr = ConnectionManager()

# ── WEBSOCKET ENDPOINT ────────────────────────────────────────────────────
@app.websocket("/ws/{user}")
async def websocket_endpoint(websocket: WebSocket, user: str):
    await mgr.connect(websocket, user)
    await websocket.send_json({"type": "init", "data": DB, "online": mgr.online_users()})
    await mgr.broadcast({"type": "user_joined", "user": user, "online": mgr.online_users()}, exclude=user)
    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")
            if msg_type == "update":
                collection = msg.get("collection")
                payload = msg.get("payload")
                actor = msg.get("user", user)
                if collection and payload is not None:
                    DB[collection] = payload
                    save_data(DB)
                if msg.get("activity"):
                    act = msg["activity"]
                    act["time"] = "gerade eben"
                    DB["activities"].insert(0, act)
                    DB["activities"] = DB["activities"][:50]
                    save_data(DB)
                await mgr.broadcast({
                    "type": "update", "collection": collection,
                    "payload": DB.get(collection), "activities": DB.get("activities"),
                    "action": msg.get("action", "update"), "user": actor,
                    "online": mgr.online_users()
                }, exclude=user)
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        mgr.disconnect(user)
        await mgr.broadcast({"type": "user_left", "user": user, "online": mgr.online_users()})

# ── REST API ──────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "online": mgr.online_users(), "kunden": len(DB.get("kunden", []))}

@app.get("/api/data")
def get_all():
    return DB

@app.post("/api/reset")
def reset_data():
    global DB
    DB = get_demo_data()
    save_data(DB)
    return {"ok": True}

# ── PLACETEL ENDPOINTS ────────────────────────────────────────────────────
@app.get("/api/phone-status")
def phone_status():
    return {
        "configured": PLACETEL_CONFIGURED,
        "provider": "placetel",
        "wss": PLACETEL_WSS,
        "sip_domain": PLACETEL_SIP_DOMAIN,
    }

@app.get("/api/phone-credentials")
def phone_credentials(user: str = ""):
    if not PLACETEL_CONFIGURED:
        raise HTTPException(status_code=503, detail="Placetel nicht konfiguriert — PLACETEL_USER_* Env-Variablen setzen")
    cred = PLACETEL_USERS.get(user)
    if not cred or not cred["username"]:
        cred = next((v for v in PLACETEL_USERS.values() if v["username"]), None)
    if not cred:
        raise HTTPException(status_code=503, detail="Kein Placetel-Account für diesen Nutzer")
    return {
        "username": cred["username"],
        "password": cred["password"],
        "sip_domain": PLACETEL_SIP_DOMAIN,
        "wss": PLACETEL_WSS,
    }

# ── FRONTEND ──────────────────────────────────────────────────────────────
frontend_path = Path("frontend")
if frontend_path.exists():
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return HTMLResponse("<h1>MorioCRM — frontend/ Ordner fehlt</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
