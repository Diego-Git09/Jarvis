"""Lista local de tareas, independiente de las memorias y de Qwen."""
import json
import uuid
from datetime import datetime, timezone
from entorno_jarvis import DATOS
import os
import tempfile
import fcntl
import unicodedata

ARCHIVO=DATOS/'tareas.json'


def _leer(ruta):
    if not ruta.exists():return []
    if ruta.is_symlink() or ruta.stat().st_size>500000:raise ValueError('Archivo de tareas no válido')
    dato=json.loads(ruta.read_text(encoding='utf-8'))
    if not isinstance(dato,list) or any(not isinstance(t,dict) or not isinstance(t.get('id'),str) or not isinstance(t.get('texto'),str) or type(t.get('hecha')) is not bool for t in dato):
        raise ValueError('No pude leer las tareas; no sobrescribí el archivo')
    if len(dato)>500 or len({t['id'] for t in dato})!=len(dato) or any(not isinstance(t.get('prioridad','normal'),str) or t.get('prioridad','normal') not in {'alta','normal','baja'} for t in dato):
        raise ValueError('La lista de tareas tiene datos inválidos; no sobrescribí el archivo')
    return dato


def listar(ruta=ARCHIVO):return _leer(ruta)


def _actualizar(funcion,ruta=ARCHIVO):
    ruta.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with open(ruta.with_suffix('.lock'),'a') as bloqueo:
        os.chmod(bloqueo.name,0o600);fcntl.flock(bloqueo,fcntl.LOCK_EX)
        tareas=_leer(ruta);resultado=funcion(tareas)
        texto=json.dumps(tareas,ensure_ascii=False,indent=2)
        if len(texto.encode('utf-8'))>500000:raise ValueError('La lista ocupa demasiado espacio. No se guardó el cambio; usa textos más cortos.')
        fd,tmp=tempfile.mkstemp(prefix='.tareas-',dir=ruta.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                f.write(texto);f.flush();os.fsync(f.fileno())
            os.replace(tmp,ruta)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return resultado


def anotar(texto,ruta=ARCHIVO):
    if not isinstance(texto,str) or not texto.strip() or len(texto)>1000:raise ValueError('Escribe una tarea de entre 1 y 1000 caracteres')
    def aplicar(tareas):
        if len(tareas)>=500:raise ValueError('La lista llegó a 500 tareas; no añadí más')
        t={'id':uuid.uuid4().hex,'texto':texto.strip(),'hecha':False,'creada':datetime.now(timezone.utc).isoformat()}
        tareas.append(t);return t
    return _actualizar(aplicar,ruta)


def marcar(ident,hecha,ruta=ARCHIVO):
    if type(hecha) is not bool:raise ValueError('Estado de tarea inválido')
    def aplicar(tareas):
        t=next((t for t in tareas if t['id']==ident),None)
        if t is None:raise ValueError('Esa tarea ya no existe; actualiza /tareas')
        t['hecha']=hecha;return dict(t)
    return _actualizar(aplicar,ruta)


def marcar_varias(identificadores,hecha,ruta=ARCHIVO):
    if type(hecha) is not bool or not isinstance(identificadores,list) or not identificadores or len(set(identificadores))!=len(identificadores):raise ValueError('Selección de tareas inválida')
    def aplicar(tareas):
        mapa={t['id']:t for t in tareas}
        if any(ident not in mapa for ident in identificadores):raise ValueError('Alguna tarea ya no existe. Actualiza /tareas; no cambié ninguna.')
        for ident in identificadores:mapa[ident]['hecha']=hecha
        return [dict(mapa[ident]) for ident in identificadores]
    return _actualizar(aplicar,ruta)


def editar(ident,texto,ruta=ARCHIVO):
    if not isinstance(texto,str) or not texto.strip() or len(texto)>1000:raise ValueError('Escribe una tarea de entre 1 y 1000 caracteres')
    return _cambiar(ident,{'texto':texto.strip()},ruta)


def priorizar(ident,prioridad,ruta=ARCHIVO):
    if not isinstance(prioridad,str) or prioridad not in {'alta','normal','baja'}:raise ValueError('Elige prioridad alta, normal o baja')
    return _cambiar(ident,{'prioridad':prioridad},ruta)


def _cambiar(ident,cambios,ruta):
    def aplicar(tareas):
        t=next((t for t in tareas if t['id']==ident),None)
        if t is None:raise ValueError('Esa tarea ya no existe; actualiza /tareas')
        t.update(cambios);return dict(t)
    return _actualizar(aplicar,ruta)


def filtrar(texto,tareas):
    def normalizar(t):return ''.join(c for c in unicodedata.normalize('NFD',t.casefold()) if unicodedata.category(c)!='Mn')
    return [t for t in tareas if normalizar(texto) in normalizar(t['texto'])]


def markdown(tareas):
    return '# Tareas de Jarvis\n\n'+('\n'.join(f"- [{'x' if t['hecha'] else ' '}] {t['texto'].replace(chr(10),' ')} — prioridad {t.get('prioridad','normal')}" for t in tareas) if tareas else 'No hay tareas.')+'\n'
