"""Auditoría local sin red: solo metadatos, nunca devuelve la credencial."""
import ast
import os
from pathlib import Path
import stat
from datetime import datetime
from zoneinfo import ZoneInfo


def auditar(ruta=None, fuentes=None):
    ruta=Path(ruta) if ruta else Path.home()/'.config/jarvis/zen.key'
    fuentes=Path(fuentes) if fuentes else Path(__file__).parent
    r={'ruta':str(ruta),'existe':False,'servicio_consultado':False,'modificado':False,
       'entorno_detectado':[k for k in ('OPENCODE_ZEN_API_KEY','OPENCODE_API_KEY','ZEN_API_KEY') if os.environ.get(k)],
       'autor':'No atribuible a una persona o proceso solo con metadatos del archivo.'}
    try:
        s=ruta.lstat();r['existe']=True
        r.update(permisos=oct(stat.S_IMODE(s.st_mode)),uid_propietario=s.st_uid,
                 fecha_modificacion=datetime.fromtimestamp(s.st_mtime,ZoneInfo('America/Santiago')).isoformat(),
                 fecha_cambio_metadatos=datetime.fromtimestamp(s.st_ctime,ZoneInfo('America/Santiago')).isoformat())
        if not stat.S_ISREG(s.st_mode) or ruta.is_symlink() or any(p.is_symlink() for p in ruta.parents):
            r['clasificacion']='ruta no regular o enlazada; no se leyó';return r
        if s.st_mode&0o077 or s.st_uid!=os.getuid() or s.st_size>2048:
            r['clasificacion']='permisos o tamaño no admitidos por el cliente; no se leyó';return r
        secreto=ruta.read_text().strip()
        coincidencias=[]
        # Comparar sin devolver valores ni huellas de un secreto de poca entropía.
        for p in fuentes.glob('prueba_*.py'):
            if p.is_symlink() or p.stat().st_size>100000:continue
            try:arbol=ast.parse(p.read_text())
            except (OSError,SyntaxError,UnicodeError):continue
            for nodo in ast.walk(arbol):
                if isinstance(nodo,ast.Constant) and isinstance(nodo.value,str) and len(nodo.value)>=12 and nodo.value==secreto:
                    coincidencias.append({'archivo':p.name,'linea':nodo.lineno})
        r['coincidencias_con_literal_de_prueba']=coincidencias
        r['clasificacion']='valor ficticio coincidente con pruebas locales' if coincidencias else 'autenticidad desconocida: no se validó con el proveedor'
        r['clave_aceptable_para_cliente']=bool(secreto)
        if r['entorno_detectado']:r['nota']='Una variable de entorno tiene prioridad; no se afirma que su valor coincida con el archivo.'
        return r
    except FileNotFoundError:
        r['clasificacion']='archivo ausente';return r
    except (OSError,UnicodeError):
        r['clasificacion']='no se pudo leer de forma segura';return r
