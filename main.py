"""
ReviewCRM — Echtzeit Backend
FastAPI + WebSockets: alle Nutzer sehen Änderungen sofort

Start: uvicorn main:app --reload --port 8000
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Any
import uuid
import time

app = FastAPI(title="ReviewCRM", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DATENSPEICHER ─────────────────────────────────────────────────────────
DATA_FILE = Path("crm_data.json")

def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return get_demo_data()

def save_data(data: dict):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_demo_data() -> dict:
    return {
        "kunden": [
            {"id": "k1", "name": "Trattoria Bella Italia", "branche": "Restaurant", "kontakt": "Marco Rossi", "email": "marco@bella.de", "tel": "+49 89 123456", "status": "aktiv", "mrr": 299, "reviews": 127, "score": 4.8, "notizen": "Top-Kunde, will Yelp ausweiten", "seit": "2024-03-15"},
            {"id": "k2", "name": "Sanitär Müller GmbH", "branche": "Handwerk", "kontakt": "Hans Müller", "email": "mueller@sanitaer.de", "tel": "+49 711 654321", "status": "aktiv", "mrr": 199, "reviews": 43, "score": 4.6, "notizen": "Fokus Google Bewertungen", "seit": "2024-06-01"},
            {"id": "k3", "name": "Dr. med. Schmidt", "branche": "Medizin", "kontakt": "Dr. Petra Schmidt", "email": "praxis@schmidt.de", "tel": "+49 30 987654", "status": "trial", "mrr": 0, "reviews": 12, "score": 4.9, "notizen": "Trial bis Ende Monat", "seit": "2024-10-01"},
            {"id": "k4", "name": "Auto Ziegler AG", "branche": "Automotive", "kontakt": "Klaus Ziegler", "email": "ziegler@auto.de", "tel": "+49 221 111222", "status": "aktiv", "mrr": 499, "reviews": 89, "score": 4.3, "notizen": "3 Standorte, Großkunde", "seit": "2024-01-20"},
            {"id": "k5", "name": "Hotel Seehof", "branche": "Tourismus", "kontakt": "Anna Weber", "email": "weber@seehof.de", "tel": "+49 8151 333444", "status": "inaktiv", "mrr": 0, "reviews": 234, "score": 4.7, "notizen": "Vertrag abgelaufen", "seit": "2023-11-01"},
        ],
        "deals": [
            {"id": "d1", "company": "Zahnarzt Dr. Braun", "contact": "Dr. Braun", "value": 349, "phase": "demo", "prob": 70, "close": "2025-01-15", "notes": "Demo diese Woche"},
            {"id": "d2", "company": "Bäckerei Hoffmann", "contact": "Sandra Hoffmann", "value": 149, "phase": "lead", "prob": 30, "close": "2025-02-10", "notes": "Kaltakquise, interessiert"},
            {"id": "d3", "company": "Reifenservice Kern", "contact": "Dieter Kern", "value": 199, "phase": "angebot", "prob": 80, "close": "2025-01-20", "notes": "Angebot gesendet"},
            {"id": "d4", "company": "Beautystudio Lux", "contact": "Maria Lux", "value": 249, "phase": "kontakt", "prob": 50, "close": "2025-02-01", "notes": "Follow-up geplant"},
            {"id": "d5", "company": "Steuerbüro Fischer", "contact": "Michael Fischer", "value": 399, "phase": "gewonnen", "prob": 100, "close": "2024-11-30", "notes": "Abschluss! Onboarding läuft"},
        ],
        "kamps": [
            {"id": "kp1", "name": "Google Boost Q4", "kunde": "k1", "plattform": "Google", "status": "aktiv", "ziel": 60, "erreicht": 38, "methode": "E-Mail Sequenz", "start": "2024-10-01"},
            {"id": "kp2", "name": "Handwerker Stars", "kunde": "k2", "plattform": "Google", "status": "aktiv", "ziel": 30, "erreicht": 21, "methode": "SMS-Kampagne", "start": "2024-09-15"},
            {"id": "kp3", "name": "Jameda Aufbau", "kunde": "k3", "plattform": "Jameda", "status": "geplant", "ziel": 20, "erreicht": 0, "methode": "E-Mail Sequenz", "start": "2025-01-01"},
            {"id": "kp4", "name": "Multi-Platform Auto", "kunde": "k4", "plattform": "Mehrere", "status": "aktiv", "ziel": 100, "erreicht": 67, "methode": "Kombination", "start": "2024-08-01"},
            {"id": "kp5", "name": "Tripadvisor Comeback", "kunde": "k5", "plattform": "Tripadvisor", "status": "abgeschlossen", "ziel": 50, "erreicht": 50, "methode": "QR-Code", "start": "2024-06-01"},
        ],
        "tasks": [
            {"id": "t1", "title": "Demo vorbereiten: Dr. Braun", "prio": "hoch", "due": "2025-01-10", "type": "Bericht", "kunde": "", "done": False, "user": "Alex"},
            {"id": "t2", "title": "Follow-up: Bäckerei Hoffmann", "prio": "mittel", "due": "2025-01-08", "type": "E-Mail", "kunde": "", "done": False, "user": "Bianca"},
            {"id": "t3", "title": "Monatsbericht: Trattoria", "prio": "hoch", "due": "2025-01-01", "type": "Bericht", "kunde": "k1", "done": False, "user": "Chris"},
            {"id": "t4", "title": "Trial verlängern: Dr. Schmidt", "prio": "hoch", "due": "2025-01-05", "type": "Anruf", "kunde": "k3", "done": False, "user": "Alex"},
            {"id": "t5", "title": "Onboarding Hotel Seehof", "prio": "niedrig", "due": "2025-01-20", "type": "Meeting", "kunde": "k5", "done": True, "user": "Dana"},
            {"id": "t6", "title": "Kampagnenbericht Q3", "prio": "mittel", "due": "2024-11-30", "type": "Bericht", "kunde": "", "done": True, "user": "Bianca"},
        ],
        "activities": [
            {"ic": "🎯", "text": "<b>Steuerbüro Fischer</b> als Deal gewonnen!", "time": "vor 2 Std.", "user": "Emir", "bg": "rgba(45,122,79,.15)"},
            {"ic": "⭐", "text": "Kampagne <b>Google Boost Q4</b>: 38 neue Bewertungen", "time": "vor 4 Std.", "user": "Alex", "bg": "rgba(192,138,48,.12)"},
            {"ic": "🏢", "text": "<b>Dr. med. Schmidt</b> als Trial-Kunde hinzugefügt", "time": "gestern", "user": "Bianca", "bg": "rgba(192,57,43,.13)"},
            {"ic": "✓", "text": "Aufgabe <b>Onboarding Hotel Seehof</b> erledigt", "time": "gestern", "user": "Dana", "bg": "rgba(45,122,79,.12)"},
            {"ic": "📄", "text": "Angebot an <b>Reifenservice Kern</b> gesendet", "time": "vor 2 Tagen", "user": "Chris", "bg": "rgba(30,28,22,1)"},
        ]
    }

DB = load_data()


# ── WEBSOCKET MANAGER ─────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}  # user -> websocket

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
    print(f"[+] {user} verbunden ({len(mgr.connections)} online)")

    # Schicke aktuellen State + wer online ist
    await websocket.send_json({
        "type": "init",
        "data": DB,
        "online": mgr.online_users()
    })

    # Broadcast: neuer Nutzer online
    await mgr.broadcast({
        "type": "user_joined",
        "user": user,
        "online": mgr.online_users()
    }, exclude=user)

    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")

            if msg_type == "update":
                # Client schickt komplette Daten-Änderung
                action = msg.get("action", "update")
                collection = msg.get("collection")
                payload = msg.get("payload")
                actor = msg.get("user", user)

                if collection and payload is not None:
                    DB[collection] = payload
                    save_data(DB)

                # Activity eintragen wenn übergeben
                if msg.get("activity"):
                    act = msg["activity"]
                    act["time"] = "gerade eben"
                    DB["activities"].insert(0, act)
                    DB["activities"] = DB["activities"][:50]
                    save_data(DB)

                # Broadcast an alle anderen
                await mgr.broadcast({
                    "type": "update",
                    "collection": collection,
                    "data": DB,
                    "action": action,
                    "user": actor,
                    "online": mgr.online_users()
                }, exclude=user)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        mgr.disconnect(user)
        print(f"[-] {user} getrennt ({len(mgr.connections)} online)")
        await mgr.broadcast({
            "type": "user_left",
            "user": user,
            "online": mgr.online_users()
        })


# ── REST API (Fallback / Tools) ───────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "online": mgr.online_users(),
        "kunden": len(DB.get("kunden", [])),
        "deals": len(DB.get("deals", [])),
    }

@app.get("/api/data")
def get_all():
    return DB

@app.post("/api/reset")
def reset_data():
    global DB
    DB = get_demo_data()
    save_data(DB)
    return {"ok": True}


# ── FRONTEND ──────────────────────────────────────────────────────────────
frontend_path = Path("frontend")
if frontend_path.exists():
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return HTMLResponse("<h1>ReviewCRM — frontend/ Ordner fehlt</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
