#!/bin/bash
set -e

REPO_URL="https://github.com/m88c5s8mxh-maker/CRM.git"
APP_DIR="/opt/morio-crm"

echo "==> Docker installieren..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl git

curl -fsSL https://get.docker.com | sh

echo "==> Repo klonen / aktualisieren..."
if [ -d "$APP_DIR" ]; then
  git -C "$APP_DIR" pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

echo "==> .env erstellen..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  WICHTIG: Trage jetzt deine Placetel SIP-Zugangsdaten ein:"
  echo "    nano $APP_DIR/.env"
  echo ""
fi

echo "==> Container starten..."
docker compose up -d --build

echo ""
echo "✅ MorioCRM läuft unter https://intra.moriosolutions.de"
echo "📋 Logs: docker compose -f $APP_DIR/docker-compose.yml logs -f"
echo ""
echo "📞 Placetel einrichten: nano $APP_DIR/.env"
