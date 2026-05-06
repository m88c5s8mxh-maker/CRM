#!/bin/bash
# MorioCRM — Hetzner Deploy Script
# Einmal auf dem frischen Ubuntu-Server ausführen:
#   bash deploy.sh
set -e

REPO_URL="https://github.com/m88c5s8mxh-maker/CRM.git"
APP_DIR="/opt/morio-crm"

echo "==> Docker installieren..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "==> Repo klonen..."
if [ -d "$APP_DIR" ]; then
  git -C "$APP_DIR" pull
else
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

echo "==> .env erstellen (falls noch nicht vorhanden)..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "WICHTIG: Öffne jetzt /opt/morio-crm/.env und trage deine Werte ein."
  echo "         Dann: cd /opt/morio-crm && docker compose up -d"
  echo ""
else
  echo "==> .env existiert bereits, wird nicht überschrieben."
fi

echo ""
echo "==> Caddyfile prüfen — trage deine Domain ein:"
grep -n "meine-domain" Caddyfile && echo "  -> Datei: $APP_DIR/Caddyfile" || true

echo ""
echo "==> Starten..."
docker compose pull caddy 2>/dev/null || true
docker compose up -d --build

echo ""
echo "✓ Fertig! CRM läuft unter https://$(grep -oP '(?<=\{)[^}]+' Caddyfile | head -1 | xargs)"
echo "  Logs: docker compose -f $APP_DIR/docker-compose.yml logs -f"
