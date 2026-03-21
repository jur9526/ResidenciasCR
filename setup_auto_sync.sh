#!/bin/bash
# ================================================================
# ResidenciasCostaRica — setup_auto_sync.sh
# Instala y configura sincronización automática cada 24h
# ================================================================

set -e

APP_DIR="/Users/jurgenarleyelizondo/ResidenciasCostaRica"
PLIST="$APP_DIR/com.residenciascostarica.sync.plist"
LOGS_DIR="$APP_DIR/logs"
LABEL="com.residenciascostarica.sync"

echo "🔧 Configurando sincronización automática de Encuentra24..."
echo ""

# Crear carpeta de logs
mkdir -p "$LOGS_DIR"
echo "✓ Carpeta de logs: $LOGS_DIR"

# Hacer el script Python ejecutable
chmod +x "$APP_DIR/sync_encuentra24.py"
echo "✓ sync_encuentra24.py marcado como ejecutable"

# Instalar el LaunchAgent
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"

cp "$PLIST" "$LAUNCH_AGENTS_DIR/"
echo "✓ Plist copiado a $LAUNCH_AGENTS_DIR"

# Cargar el agent
launchctl load "$LAUNCH_AGENTS_DIR/$(basename $PLIST)"
echo "✓ LaunchAgent activado"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ CONFIGURACIÓN COMPLETADA"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📋 Información:"
echo "  • Se ejecutará diariamente a las 6:00 AM"
echo "  • Logs: $LOGS_DIR/sync.log"
echo "  • Errores: $LOGS_DIR/sync-error.log"
echo ""
echo "📝 Comandos útiles:"
echo "  Ver logs:           tail -f $LOGS_DIR/sync.log"
echo "  Desactivar:         launchctl unload ~/Library/LaunchAgents/$LABEL.plist"
echo "  Activar:            launchctl load ~/Library/LaunchAgents/$LABEL.plist"
echo "  Prueba manual:      python3 $APP_DIR/sync_encuentra24.py"
echo ""
