"""Instala el inicio de sesión y acceso de escritorio sin servicios de administrador."""
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from entorno_jarvis import PROYECTO,REGISTROS,en_pruebas


def escribir(ruta,texto,ejecutable=False):
    ruta.parent.mkdir(parents=True,exist_ok=True)
    if ruta.is_symlink():raise ValueError('No se reemplaza un acceso que sea enlace simbólico.')
    if ruta.exists():
        copia=REGISTROS/'copias'/'instalacion_recordatorios';copia.mkdir(parents=True,exist_ok=True)
        (copia/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'-'+ruta.name)).write_bytes(ruta.read_bytes())
    fd,tmp=tempfile.mkstemp(prefix='.jarvis-',dir=ruta.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(texto);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o755 if ejecutable else 0o600);os.replace(tmp,ruta)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def instalar(config=None,escritorio=None):
    if en_pruebas() and config is None:raise ValueError('La instalación real está desactivada durante pruebas.')
    config=config or Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))
    if escritorio is None:
        try:escritorio=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True,timeout=3).strip())
        except (OSError,subprocess.SubprocessError):escritorio=Path.home()/'Desktop'
    script=str(PROYECTO/'herramientas'/'recordatorios_escritorio.py').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    base='[Desktop Entry]\nType=Application\nName=Jarvis Recordatorios\nComment=Recordatorios personales visibles y programados\nIcon=appointment-soon\nTerminal=false\n'
    auto=config/'autostart'/'jarvis-recordatorios.desktop'
    escribir(auto,base+f'Exec=/usr/bin/python3 -B "{script}" --iniciar\nX-GNOME-Autostart-enabled=true\n')
    launcher=escritorio/'Jarvis Recordatorios.desktop'
    escribir(launcher,base+f'Exec=/usr/bin/python3 -B "{script}" --gestionar\n',True)
    try:subprocess.run(['gio','set',str(launcher),'metadata::trusted','true'],capture_output=True,timeout=3)
    except (OSError,subprocess.SubprocessError):pass
    return auto,launcher


if __name__=='__main__':
    for ruta in instalar():print(ruta)
