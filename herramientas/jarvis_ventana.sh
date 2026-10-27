#!/usr/bin/env bash
set -u
DIR="${JARVIS_DIR:-$HOME/Jarvis}/herramientas"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/jarvis.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "Jarvis ya está abierto en otra ventana."
    exit 0
fi
cd "$DIR" || exit 1
python3 -B jarvis_agente.py
codigo=$?
if [ "$codigo" -ne 0 ]; then
    echo
    echo "Jarvis terminó con un error (código $codigo)."
    read -r -p "Pulsa Enter para cerrar esta ventana. " _
fi
