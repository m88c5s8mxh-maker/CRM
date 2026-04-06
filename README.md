# ReviewCRM — Echtzeit Multi-User

Bewertungs-KI CRM mit WebSocket-Echtzeitsync für 5 Nutzer.

## Start in Claude Code (3 Befehle)

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Dann im Browser: **http://localhost:8000**

## Wie es funktioniert

Jeder Nutzer öffnet http://localhost:8000 → wählt seinen Namen (Alex/Bianca/Chris/Dana/Emir) → ist sofort live verbunden.

Änderungen von einem Nutzer sehen alle anderen **sofort** ohne Neuladen:
- Neuer Kunde angelegt → alle sehen ihn
- Deal in Pipeline verschoben → Kanban aktualisiert sich bei allen
- Aufgabe erledigt → erscheint bei allen als erledigt
- Wer online ist wird oben rechts angezeigt

## Für Railway Deployment (alle 5 Nutzer im Internet)

1. Repo auf GitHub pushen
2. railway.app → New Project → GitHub Repo
3. Fertig — URL teilen mit allen 5 Nutzern

## Datenspeicherung

Alle Daten werden in `crm_data.json` gespeichert (automatisch).
Beim ersten Start werden Demo-Daten geladen.
