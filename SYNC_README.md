# 🏠 Sincronización Automática de Encuentra24

## Descripción
Las propiedades de tu perfil en Encuentra24 se actualizan automáticamente **cada 24 horas** en tu sitio web. El daemon descarga:
- Información de cada propiedad (título, precio, ubicación)
- Imágenes principales
- IDs para linkedar de vuelta a Encuentra24

## ⚙️ Configuración Actual
- **Ejecución**: Automática cada día a las **6:00 AM** (macOS LaunchAgent)
- **Archivo actualizado**: `properties-data.js`
- **Logs**: 
  - Éxito: `logs/sync.log`
  - Errores: `logs/sync-error.log`

## 📋 Comandos de Utilidad

### Ver logs en tiempo real
```bash
tail -f logs/sync.log
```

### Ejecutar sincronización manual ya
```bash
python3 sync_encuentra24.py
```

### Activar/desactivar daemon
```bash
# Desactivar (para de sincronizar)
launchctl unload ~/Library/LaunchAgents/com.residenciascostarica.sync.plist

# Activar (reanuda sincronización)
launchctl load ~/Library/LaunchAgents/com.residenciascostarica.sync.plist
```

### Ver estado del daemon
```bash
launchctl list | grep residenciascostarica
```

## 🔧 Editar horario de ejecución
1. Abre: `com.residenciascostarica.sync.plist`
2. Cambia `<integer>6</integer>` (hour) a tu hora preferida (0-23)
3. Recarga:
```bash
launchctl unload ~/Library/LaunchAgents/com.residenciascostarica.sync.plist
launchctl load ~/Library/LaunchAgents/com.residenciascostarica.sync.plist
```

## 📝 Agregar nuevas propiedades
Edita `sync_encuentra24.py` y agrega los IDs en `KNOWN_PROPERTY_IDS`:

```python
KNOWN_PROPERTY_IDS = [
    "31892295",   # Propiedad existente
    "31076847",   # Nueva propiedad
    # ... etc
]
```

Luego ejecuta:
```bash
python3 sync_encuentra24.py
```

## ✅ Detalles Técnicos
- **Herramientas**: Playwright (web scraping), requests (descargas)
- **Fuente**: Perfil Encuentra24 ID **13021117**
- **Destino**: `properties-data.js`
- **Cada sincronización**:
  1. Conecta a cada propiedad en Encuentra24
  2. Extrae datos JSON-LD (schema.org)
  3. Descarga la imagen principal
  4. Actualiza `properties-data.js` automáticamente

## 🚨 Si hay problemas
1. Revisa logs: `tail -f logs/sync.log`
2. Intenta manual: `python3 sync_encuentra24.py`
3. Verifica que Playwright esté instalado:
   ```bash
   python3 -c "import playwright; print('OK')"
   ```
4. Si necesitas reinstalar:
   ```bash
   bash setup_auto_sync.sh
   ```

---
**Creado**: 21 de marzo de 2026 | **Sitio**: Residencias Costa Rica
