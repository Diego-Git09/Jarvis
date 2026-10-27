#!/usr/bin/env bash
set -u
ROOT="${JARVIS_DIR:-$HOME/Jarvis}"
if ! command -v python3 >/dev/null 2>&1; then
    command -v notify-send >/dev/null 2>&1 && notify-send -a Jarvis 'Jarvis' 'No encontré Python 3 para abrir la interfaz.'
    exit 1
fi
exec python3 -B "$ROOT/herramientas/interfaz_grafica.py"
