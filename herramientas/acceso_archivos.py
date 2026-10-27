"""Carpetas personales autorizadas: rutas adicionales sin cambiar las rutas relativas."""
import json
import os
import tempfile
from pathlib import Path
from entorno_jarvis import DATOS, TRABAJO

ARCHIVO=DATOS/'carpetas_autorizadas.json'


def protegida(ruta):
    hogar=Path.home().resolve()
    bruto=Path(os.path.abspath(Path(ruta).expanduser()))
    rutas={bruto,bruto.resolve()}
    secretos=[hogar/x for x in ('.ssh','.gnupg','.aws','.netrc','.git-credentials','.docker','.kube',
        '.config/gcloud','.config/gh','.config/google-chrome','.config/chromium','.mozilla','snap',
        '.bash_history','.local/share/keyrings','.local/share/opencode','.config/jarvis')]
    secretos += [hogar/'.codex'/'auth.json',DATOS/'perfiles_ia.json']
    secretos={p for s in secretos for p in (s,s.resolve())}
    return any(r==p or p in r.parents for r in rutas for p in secretos)


def listar():
    if not ARCHIVO.exists():return []
    if ARCHIVO.is_symlink() or ARCHIVO.stat().st_size>32000:raise ValueError('Configuración de carpetas inválida.')
    dato=json.loads(ARCHIVO.read_text(encoding='utf-8'))
    if not isinstance(dato,list) or any(not isinstance(p,str) or not Path(p).is_absolute() for p in dato):
        raise ValueError('Configuración de carpetas inválida; no se ampliaron los accesos.')
    return [Path(p).resolve() for p in dato]


def _guardar(raices):
    ARCHIVO.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,tmp=tempfile.mkstemp(prefix='.carpetas-',dir=ARCHIVO.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump([str(p) for p in raices],f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(tmp,ARCHIVO)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def validar_carpeta(ruta):
    p=Path(ruta).expanduser().resolve()
    if not p.is_dir():raise ValueError('Esa carpeta no existe.')
    if p==Path.home().resolve():raise ValueError('Elige una subcarpeta concreta; no se autoriza la carpeta personal completa.')
    if p==Path('/') or any(p==Path(x) or Path(x) in p.parents for x in ('/etc','/usr','/boot','/proc','/sys','/dev')):
        raise ValueError('Selecciona una carpeta de archivos personales, no una carpeta del sistema.')
    if protegida(p):raise ValueError('Esa carpeta contiene credenciales protegidas.')
    return p


def autorizar(ruta):
    p=validar_carpeta(ruta);raices=listar()
    if p not in raices:raices.append(p);_guardar(raices)
    return p


def revocar(ruta):
    p=Path(ruta).expanduser().resolve();raices=listar()
    if p not in raices:raise ValueError('Esa carpeta no está en la lista de accesos adicionales.')
    _guardar([x for x in raices if x!=p]);return p


def permitido(ruta,raiz=TRABAJO):
    p=Path(ruta).resolve();base=Path(raiz).resolve()
    if protegida(p):return False
    if p==base or base in p.parents:return True
    return any(p==r or r in p.parents for r in listar())
