#!/usr/bin/env bash
# Abre Jarvis aunque Ollama esté desconectado: los accesos directos siguen funcionando.
set -u
DIR="${JARVIS_DIR:-$HOME/Jarvis}/herramientas"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/jarvis.lock"
aviso() { notify-send -a Jarvis "Jarvis" "$1" 2>/dev/null || echo "$1"; }
if ! command -v python3 >/dev/null; then
    aviso "No encontré Python 3 para abrir Jarvis."
    exit 1
fi
if ! ( exec 9>"$LOCK"; flock -n 9 ); then
    aviso "Jarvis ya está abierto: busca la ventana llamada «Jarvis»."
    exit 0
fi
export JARVIS_HERRAMIENTAS="$DIR"
if python3 -B -c "import sys,os; sys.path.insert(0,os.environ['JARVIS_HERRAMIENTAS']); import cliente_ollama as O; O.solicitar('/api/version',timeout=2)" >/dev/null 2>&1; then
    ( cd "$DIR" && nohup python3 -B -c "
import configuracion_jarvis as C, cliente_ollama as O
config,_=C.leer()
try:
 O.solicitar('/api/generate',{'model':config['modelo'],'keep_alive':'30m','stream':False,'options':{'num_ctx':config['num_ctx']}},timeout=180)
except ConnectionError:
 pass
" >/dev/null 2>&1 & )
else
    aviso "Ollama no responde. Jarvis abrirá igual; /diagnostico permite revisar la conexión."
fi
if command -v ptyxis >/dev/null; then
    exec ptyxis --new-window -T Jarvis -d "${JARVIS_DIR:-$HOME/Jarvis}" -- bash "$DIR/jarvis_ventana.sh"
elif command -v gnome-terminal >/dev/null; then
    exec gnome-terminal --title=Jarvis -- bash "$DIR/jarvis_ventana.sh"
else
    aviso "No encontré Ptyxis ni GNOME Terminal. Abre Jarvis con python3 $DIR/jarvis_agente.py"
    exit 1
fi
