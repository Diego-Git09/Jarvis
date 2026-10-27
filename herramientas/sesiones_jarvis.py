"""Sesiones explícitas. Nunca restaura permisos, propuestas ni referencias de recuerdos."""
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from entorno_jarvis import DATOS
from conversaciones_jarvis import _redactar, _privada

CARPETA=DATOS/'sesiones'
MAX_BYTES=600_000


def limpiar_mensaje(mensaje):
    if not isinstance(mensaje,dict) or mensaje.get('role') not in {'user','assistant','tool'} or not isinstance(mensaje.get('content',''),str):
        raise ValueError('Mensajes de sesión no válidos')
    limpio={'role':mensaje['role'],'content':_redactar(mensaje.get('content',''))}
    if mensaje['role']=='tool':
        nombre=mensaje.get('tool_name','')
        if not isinstance(nombre,str) or len(nombre)>100:raise ValueError('Nombre de herramienta de sesión no válido')
        limpio['tool_name']=nombre
    if mensaje['role']=='assistant' and mensaje.get('tool_calls'):
        llamadas=mensaje['tool_calls']
        if not isinstance(llamadas,list) or len(llamadas)>20:raise ValueError('Acciones de sesión no válidas')
        limpias=[]
        for llamada in llamadas:
            funcion=llamada.get('function') if isinstance(llamada,dict) else None
            if not isinstance(funcion,dict) or not isinstance(funcion.get('name'),str) or not isinstance(funcion.get('arguments',{}),(dict,str)):
                raise ValueError('Acción de sesión no válida')
            def redactar_argumentos(dato):
                if isinstance(dato,str):return _redactar(dato)
                if isinstance(dato,list):return [redactar_argumentos(x) for x in dato]
                if isinstance(dato,dict):return {k:('[REDACTADO]' if re.search(r'(?i)(?:password|contrase[nñ]a|token|secret|api.?key|authorization|cookie)',str(k)) else redactar_argumentos(v)) for k,v in dato.items()}
                return dato
            limpias.append({'function':{'name':funcion['name'],'arguments':redactar_argumentos(funcion.get('arguments',{}))}})
        limpio['tool_calls']=limpias
    return limpio


def ruta_sesion(nombre, carpeta=CARPETA):
    if not isinstance(nombre,str) or not re.fullmatch(r'[\w -]{1,60}',nombre,flags=re.UNICODE) or nombre.strip() in {'','.'}:
        raise ValueError('Usa un nombre de sesión de letras, números, espacios o guiones')
    ruta=carpeta/(nombre.strip()+'.json')
    if carpeta.is_symlink() or ruta.is_symlink():raise ValueError('La ruta de sesión no puede ser un enlace')
    return ruta


def guardar(nombre, historial, estado, carpeta=CARPETA):
    ruta=ruta_sesion(nombre,carpeta)
    mensajes=[]
    privado=False
    for m in historial:
        if not isinstance(m,dict) or m.get('role') not in {'user','assistant','tool'}:continue
        if m.get('role')=='user':privado=isinstance(m.get('content'),str) and _privada(m['content'])
        if privado:continue
        mensajes.append(limpiar_mensaje(m))
    datos={'version':1,'nombre':nombre.strip(),'guardado':datetime.now(timezone.utc).isoformat(),
           'mensajes':mensajes,'preferencias':{k:estado[k] for k in ('_proyecto_activo','_tamano_pagina') if k in estado}}
    import hilo_conversacion as H
    hilo=H.exportar(estado)
    if hilo is not None:datos['hilo']=hilo
    texto=json.dumps(datos,ensure_ascii=False,indent=2).encode('utf-8')
    if len(texto)>MAX_BYTES:raise ValueError('La sesión es demasiado grande; empieza una conversación nueva o guarda una conversación más corta')
    carpeta.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(carpeta,0o700)
    fd,tmp=tempfile.mkstemp(prefix='.sesion-',dir=carpeta)
    try:
        with os.fdopen(fd,'wb') as f:f.write(texto);f.flush();os.fsync(f.fileno())
        os.replace(tmp,ruta)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return {'nombre':nombre.strip(),'mensajes':len(mensajes),'ruta':str(ruta)}


def cargar(nombre, carpeta=CARPETA):
    ruta=ruta_sesion(nombre,carpeta)
    if ruta.stat().st_size>MAX_BYTES:raise ValueError('Sesión demasiado grande')
    dato=json.loads(ruta.read_text(encoding='utf-8'))
    if not isinstance(dato,dict) or dato.get('version')!=1 or not isinstance(dato.get('mensajes'),list):raise ValueError('Formato de sesión no reconocido')
    mensajes=[];privado=False
    for m in dato['mensajes']:
        limpio=limpiar_mensaje(m)
        if limpio['role']=='user':privado=_privada(limpio['content'])
        if not privado:mensajes.append(limpio)
    preferencias=dato.get('preferencias',{})
    if not isinstance(preferencias,dict):preferencias={}
    permitidas={}
    if isinstance(preferencias.get('_proyecto_activo'),str) and len(preferencias['_proyecto_activo'])<=100:
        permitidas['_proyecto_activo']=preferencias['_proyecto_activo']
    tam=preferencias.get('_tamano_pagina')
    if type(tam) is int and 1<=tam<=20:permitidas['_tamano_pagina']=tam
    if isinstance(dato.get('hilo'),dict):
        import hilo_conversacion as H
        hilo=H.validar_reapertura(dato['hilo'])
        permitidas['_hilo_conversacion']=hilo;permitidas['_id_hilo']=hilo['id']
        permitidas['_hilo_reanudado']=True;permitidas['_mensajes_hilo_reanudado']=len(mensajes)
        if hilo['tanda']:permitidas['_tanda_documentos']=hilo['tanda']
        if hilo['etapa_explicativa']=='android_inicio_mostrado':permitidas['_inicio_android_guiado']=True
    return mensajes,permitidas


def listar(carpeta=CARPETA):
    if not carpeta.exists():return []
    resultado=[]
    for p in sorted(carpeta.glob('*.json')):
        if p.is_symlink():continue
        try:
            if p.stat().st_size>MAX_BYTES:continue
            dato=json.loads(p.read_text(encoding='utf-8'))
            if isinstance(dato,dict) and dato.get('version')==1:
                resultado.append({'nombre':p.stem,'guardado':dato.get('guardado',''),'mensajes':len(dato.get('mensajes',[]))})
        except (OSError,ValueError,TypeError):continue
    return resultado


def markdown(nombre,carpeta=CARPETA):
    mensajes,_=cargar(nombre,carpeta)
    bloques=['# Conversación de Jarvis: '+nombre,'']
    for m in mensajes:
        titulo={'user':'Tú','assistant':'Jarvis','tool':'Resultado de herramienta'}[m['role']]
        contenido=m.get('content','')
        if not contenido:continue
        bloques.extend(['## '+titulo,'','\n'.join('> '+linea for linea in contenido.splitlines()),''])
    return '\n'.join(bloques)
