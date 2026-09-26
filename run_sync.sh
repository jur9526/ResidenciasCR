#!/bin/bash
# Sync diario desde esta Mac (Cloudflare bloquea las IPs de GitHub Actions).
# Lo ejecuta launchd: com.residenciascostarica.sync.plist
set -uo pipefail

APP_DIR="/Users/jurgenarleyelizondo/ResidenciasCostaRica"
cd "$APP_DIR" || exit 1
echo "── $(date '+%Y-%m-%d %H:%M:%S') ──"

# Al despertar de la suspensión la red tarda en volver
for i in $(seq 1 30); do
  curl -s -o /dev/null --max-time 5 https://github.com && break
  sleep 10
done

git pull --rebase --autostash -q origin main || { echo "✗ git pull falló"; exit 1; }

.venv/bin/python sync_encuentra24.py || { echo "✗ sync falló"; exit 1; }

git add properties-data.js assets/
if git diff --cached --quiet; then
  echo "Sin cambios"
else
  git commit -q -m "Auto-sync: actualizar propiedades desde Encuentra24 [$(date +'%Y-%m-%d')]"
  git push -q origin main && echo "✓ Push completado"
fi
