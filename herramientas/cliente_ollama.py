"""Operaciones locales de Ollama, con límites de respuesta y sin proxies."""
import json
import urllib.request
import urllib.error
import threading
import time
import socket
import http.client
from copy import deepcopy
from contextlib import nullcontext,contextmanager
import cola_inferencia
from configuracion_jarvis import leer,validar_url

BASE = validar_url(leer()[0]['ollama_url'])
class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ErrorOllama('Ollama intentó redirigir la consulta. La detuve antes de enviar datos a otro destino.',tipo='politica')

ABRIR = urllib.request.build_opener(urllib.request.ProxyHandler({}),SinRedireccion()).open
MAX_BYTES = 2_000_000
_TURNO=threading.RLock()
_META_LOCK=threading.RLock()
_CATALOGOS={}
_METADATOS={}
TTL_METADATOS=4
_SERVICIO=None
_SERVICIO_LOCK=threading.RLock()
_SERVICIO_GENERACION=0
_CIERRE_SOLICITADO=False

def activar_servicio(avisar=None,*,nueva_sesion=False):
    """Solo abrir una interfaz nueva puede revocar el cierre del ciclo anterior."""
    global _SERVICIO,_SERVICIO_GENERACION,_CIERRE_SOLICITADO
    with _SERVICIO_LOCK:
        if nueva_sesion:_CIERRE_SOLICITADO=False
        comprobar_sesion_abierta()
    from entorno_jarvis import en_pruebas
    if en_pruebas():return None
    ajustes,aviso=leer()
    if aviso or not ajustes.get('autoinicio_ollama',True):return None
    with _SERVICIO_LOCK:
        # Cerrar pudo ocurrir mientras se leía la configuración. Un reintento
        # o cambio de URL tardío no crea otro servidor después de ese cierre.
        comprobar_sesion_abierta()
        if _SERVICIO is None or _SERVICIO.estado().get('sesion_cerrada'):
            from servicio_ollama import SesionOllama
            try:_SERVICIO=SesionOllama(BASE,avisar=avisar)
            except (OSError,ValueError):
                if avisar:avisar('No pude habilitar el inicio automático para el destino configurado; /diagnostico permite revisarlo.')
                return None
            _SERVICIO_GENERACION=0
        elif avisar is not None:_SERVICIO.avisar=avisar
        return _SERVICIO

def cerrar_servicio():
    global _CIERRE_SOLICITADO
    with _SERVICIO_LOCK:
        _CIERRE_SOLICITADO=True
        servicio=_SERVICIO
    if servicio is not None:servicio.cerrar()

def sesion_cerrada():
    with _SERVICIO_LOCK:return _CIERRE_SOLICITADO

def comprobar_sesion_abierta():
    if sesion_cerrada():
        raise ErrorOllama('Jarvis se está cerrando; la consulta quedó interrumpida y no inicié otra.',tipo='cancelada')

def asegurar_servicio(timeout=10):
    global _SERVICIO_GENERACION
    with _SERVICIO_LOCK:
        servicio=_SERVICIO;cerrando=_CIERRE_SOLICITADO
    if cerrando:comprobar_sesion_abierta()
    if servicio is None:return None
    r=servicio.asegurar(timeout=timeout)
    comprobar_sesion_abierta()
    if not r['ok']:
        raise ErrorOllama(r.get('error','Ollama no está disponible.'),tipo='servidor',servicio=True)
    if servicio.generacion!=_SERVICIO_GENERACION:
        invalidar_metadatos();_SERVICIO_GENERACION=servicio.generacion
    return r

def estado_servicio():
    from salud_ollama import comprobar
    with _SERVICIO_LOCK:servicio=_SERVICIO
    r=comprobar(BASE,timeout=1)
    r['gestion']=servicio.estado().get('gestion','sin_comprobar') if servicio else 'sin_gestion'
    return r

def invalidar_metadatos():
    with _META_LOCK:_CATALOGOS.clear();_METADATOS.clear()

def _observar_catalogo(resultado):
    modelos=resultado.get('models')
    if not isinstance(modelos,list):return
    clave=(BASE,ABRIR)
    digests={m['name']:m['digest'] for m in modelos if isinstance(m,dict) and isinstance(m.get('name'),str) and isinstance(m.get('digest'),str) and m['digest']}
    with _META_LOCK:
        _CATALOGOS[clave]=(time.monotonic(),digests)
        for k in list(_METADATOS):
            if k[:2]==clave and digests.get(k[2])!=_METADATOS[k]['digest']:_METADATOS.pop(k,None)


@contextmanager
def reservar(timeout):
    try:
        with cola_inferencia.reservar(timeout):yield
    except cola_inferencia.ColaOcupada as e:raise ErrorOllama(str(e),tipo='cola') from e


class ErrorOllama(ConnectionError):
    """Un fallo de transporte no es evidencia de una acción ejecutada."""
    def __init__(self, mensaje, *, tipo='transporte', reintentable=False, intentos=1,servicio=False):
        super().__init__(mensaje)
        self.tipo=tipo;self.reintentable=reintentable;self.intentos=intentos
        self.servicio=servicio


def _error(exc,plazo=None):
    from conversaciones_jarvis import _redactar
    if isinstance(exc, ErrorOllama):return exc
    if isinstance(exc, urllib.error.HTTPError):
        try:
            from lectura_http import leer_acotado
            fin=min(time.monotonic()+1,plazo) if plazo is not None else time.monotonic()+1
            detalle=json.loads(leer_acotado(exc.fp,4096,fin)).get('error','')
        except (OSError,ValueError,AttributeError):detalle=''
        finally:exc.close()
        detalle=_redactar(str(detalle))[:200]
        contexto=any(x in detalle.casefold() for x in ('context length','context window','too many tokens','prompt is longer'))
        memoria=any(x in detalle.casefold() for x in ('out of memory','insufficient memory','not enough memory','cuda error','cuda malloc'))
        consejo=(' Ollama no encontró el modelo o el acceso solicitado; /modelos comprueba su nombre. No descargué nada.' if exc.code==404 else
                 ' El servidor informó un problema de memoria/GPU. /diagnostico muestra recursos y /liberar permite descargar modelos.' if memoria else
                 ' El servidor está ocupado o temporalmente no disponible. /diagnostico permite comprobarlo antes de reintentar.' if exc.code in {429,503} else
                 ' La respuesta no se completó; /diagnostico comprueba el servidor.')
        return ErrorOllama(f'Ollama devolvió HTTP {exc.code}'+(': '+detalle if detalle else '.')+
            consejo,tipo='contexto' if contexto else 'memoria' if memoria else 'http',reintentable=not memoria and 500<=exc.code<=599)
    motivo=getattr(exc,'reason',exc)
    if isinstance(motivo,(TimeoutError,socket.timeout)):
        return ErrorOllama('Ollama agotó el tiempo de respuesta. Conservé la conversación; /timeout permite revisar el límite local y /diagnostico la conexión.',tipo='timeout',reintentable=False)
    if isinstance(exc,ValueError):
        return ErrorOllama('Ollama devolvió datos incompletos o JSON no válido. Conservé la pregunta; puedes reintentar.',tipo='respuesta',reintentable=False)
    if isinstance(motivo,ConnectionRefusedError):
        return ErrorOllama('El servidor Ollama rechazó la conexión; puede estar detenido o usar otro puerto. /ollama y /diagnostico permiten comprobarlo. No demuestra un problema del modelo.',tipo='conexion',reintentable=True,servicio=True)
    conexion=isinstance(exc,(urllib.error.URLError,ConnectionError)) or isinstance(motivo,(ConnectionError,socket.gaierror))
    return ErrorOllama('No pude completar la solicitud a Ollama. /diagnostico comprueba la conexión. Los accesos de archivos y memoria siguen disponibles.',tipo='conexion' if conexion else 'transporte',reintentable=conexion,servicio=conexion)

def cambiar_url(url):
    global BASE,_SERVICIO,_SERVICIO_GENERACION
    nueva=validar_url(url)
    with _SERVICIO_LOCK:
        anterior=_SERVICIO
        if anterior is not None and nueva!=BASE:
            anterior.cerrar();_SERVICIO=None;_SERVICIO_GENERACION=0
        BASE=nueva
    invalidar_metadatos()
    if anterior is not None and nueva!=anterior.url:activar_servicio(avisar=anterior.avisar)
    return BASE


def acreditar_pesos_locales(nombre,timeout=5):
    import politica_ia
    try:politica_ia.comprobar_destino_local(nombre,BASE)
    except ValueError as error:raise ErrorOllama(str(error),tipo='politica') from None
    plazo=time.monotonic()+timeout
    k=(BASE,ABRIR,nombre)
    with _META_LOCK:
        registro=_CATALOGOS.get(k[:2]);existe=k in _METADATOS
    if existe and (not registro or time.monotonic()-registro[0]>=TTL_METADATOS):
        solicitar('/api/tags',timeout=max(.01,plazo-time.monotonic()))
    with _META_LOCK:
        registro=_CATALOGOS.get(k[:2]);cache=_METADATOS.get(k)
        if registro and cache and time.monotonic()-registro[0]<TTL_METADATOS and registro[1].get(nombre)==cache['digest']:
            return deepcopy(cache['info'])
    info=solicitar('/api/show',{'model':nombre},timeout=max(.01,plazo-time.monotonic()))
    if info.get('remote_model') or info.get('remote_host') or not isinstance(info.get('model_info'),dict) or not info['model_info']:
        raise ErrorOllama('No pude acreditar pesos locales para este modelo. No envié la pregunta; los alias de modelos cloud también están bloqueados.',tipo='politica')
    with _META_LOCK:
        registro=_CATALOGOS.get(k[:2]);digest=registro[1].get(nombre) if registro else None
        if digest and time.monotonic()-registro[0]<TTL_METADATOS:_METADATOS[k]={'digest':digest,'info':deepcopy(info)}
    return info


def preparar_cuerpo(ruta,cuerpo,plazo):
    """Política y recursos compartidos por respuestas completas y streaming."""
    import politica_ia
    try:politica_ia.comprobar_destino_local('',BASE)
    except ValueError as error:raise ErrorOllama(str(error),tipo='politica') from None
    if ruta in {'/api/chat','/api/generate','/api/embed','/api/embeddings'} and isinstance(cuerpo,dict) and cuerpo.get('model'):
        import politica_ia
        try:politica_ia.comprobar_destino_local(cuerpo['model'],BASE)
        except ValueError as error:raise ErrorOllama(str(error),tipo='politica') from None
        ajustes,aviso=leer()
        if aviso:raise ErrorOllama('No pude leer la configuración guardada. No inicié inferencia para no ignorar tu modo CPU o reposo. Revisa /diagnostico y restaura la configuración antes de reintentar.',tipo='configuracion')
        from entorno_jarvis import en_pruebas
        info=None
        if not en_pruebas():
            # La consulta solo contiene el nombre. Se verifica antes de enviar
            # prompts: un alias sin «cloud» también puede apuntar a un remoto.
            info=acreditar_pesos_locales(cuerpo['model'],timeout=min(5,max(.01,plazo-time.monotonic())))
        import recursos_ollama
        cuerpo=dict(cuerpo,keep_alive=recursos_ollama.limitar_reposo(cuerpo.get('keep_alive'),ajustes['keep_alive']))
        # La opción CPU se aplica también a auxiliares, resúmenes, código y
        # embeddings que usan este transporte. Copia el payload del llamador.
        if not (ruta=='/api/generate' and cuerpo.get('keep_alive') in (0,'0') and not cuerpo.get('prompt')):
            opciones=dict(cuerpo.get('options',{}))
            if ruta in {'/api/chat','/api/generate'}:opciones.setdefault('num_ctx',ajustes['num_ctx'])
            if ajustes.get('hilos'):opciones.setdefault('num_thread',ajustes['hilos'])
            if ajustes.get('modo_gpu')=='cpu':opciones['num_gpu']=0
            elif ajustes.get('modo_gpu')=='mixto':
                opciones['num_gpu']=ajustes['capas_gpu']
                if ruta in {'/api/embed','/api/embeddings'} and info:
                    meta=info.get('model_info',{});bloques=meta.get(meta.get('general.architecture','')+'.block_count')
                    if type(bloques) is int and bloques>0:opciones['num_gpu']=min(opciones['num_gpu'],bloques+1)
            cuerpo=dict(cuerpo,options=opciones)
    return cuerpo


def solicitar(ruta, cuerpo=None, timeout=5):
    plazo=time.monotonic()+max(.01,float(timeout))
    asegurar_servicio(timeout=min(10,max(.01,plazo-time.monotonic())))
    cuerpo=preparar_cuerpo(ruta,cuerpo,plazo)
    req=urllib.request.Request(BASE+ruta,data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
                              headers={'Content-Type':'application/json'})
    # Solo se repite una inferencia. Las herramientas del controlador no pasan
    # por aquí y nunca se vuelven a ejecutar por un fallo de red.
    max_intentos=2 if ruta in {'/api/chat','/api/embed','/api/embeddings'} else 1
    generativa=ruta in {'/api/chat','/api/generate','/api/embed','/api/embeddings'}
    if generativa and not _TURNO.acquire(timeout=max(0,plazo-time.monotonic())):
        raise ErrorOllama('Ollama sigue atendiendo otra petición. Se agotó la espera en la cola; reintenta cuando termine.',tipo='cola')
    primero=None
    try:
        with reservar(max(0,plazo-time.monotonic())) if generativa else nullcontext():
            import control_recursos
            comprobar_sesion_abierta()
            if generativa:control_recursos.comprobar(__import__(__name__),cuerpo,plazo_fin=plazo)
            for intento in range(1,max_intentos+1):
                comprobar_sesion_abierta()
                restante=plazo-time.monotonic()
                if restante<=0:break
                try:
                    # Una conexión fallida/5xx puede tener un segundo intento
                    # de hasta dos segundos, dentro del plazo total original.
                    espera=restante if intento==1 else min(2,restante)
                    fin_intento=min(plazo,time.monotonic()+espera)
                    with ABRIR(req,timeout=max(.01,espera)) as r:
                        from lectura_http import leer_acotado
                        datos=leer_acotado(r,MAX_BYTES+1,fin_intento)
                        if len(datos)>MAX_BYTES:raise ErrorOllama('Respuesta demasiado grande; no la procesé.',tipo='tamano')
                        result=json.loads(datos)
                    if not isinstance(result,dict):raise ErrorOllama('Ollama devolvió una respuesta no válida.',tipo='respuesta',reintentable=True)
                    comprobar_sesion_abierta()
                    if result.get('error'):
                        from conversaciones_jarvis import _redactar
                        raise ErrorOllama('Ollama rechazó la solicitud: '+_redactar(str(result['error']))[:200],tipo='respuesta')
                    if ruta=='/api/chat' and (not isinstance(result.get('message'),dict) or
                        not (result['message'].get('content') or result['message'].get('tool_calls'))):
                        raise ErrorOllama('Ollama respondió sin texto ni acciones. Puedes reintentar la pregunta.',tipo='vacia',reintentable=True)
                    if generativa:control_recursos.registrar(__import__(__name__),cuerpo)
                    if ruta=='/api/tags':_observar_catalogo(result)
                    return result
                except (OSError,ValueError,urllib.error.URLError,ConnectionError,http.client.HTTPException) as exc:
                    if sesion_cerrada():
                        if isinstance(exc,urllib.error.HTTPError):exc.close()
                        comprobar_sesion_abierta()
                    fallo=_error(exc,plazo=plazo);fallo.intentos=intento
                    if fallo.servicio and _SERVICIO is not None:_SERVICIO.invalidar()
                    if primero is None:primero=fallo
                    if not fallo.reintentable or fallo.tipo not in {'conexion','http'} or intento==max_intentos:raise fallo from exc
                    pausa=min(.25,max(0,(plazo-time.monotonic())*.2))
                    if pausa:time.sleep(pausa)
        fallo=primero or ErrorOllama('Se agotó el plazo local antes de recibir la respuesta.',tipo='timeout')
        fallo.intentos=max_intentos
        raise fallo
    finally:
        if generativa:
            import cache_recursos
            cache_recursos.invalidar()
            _TURNO.release()


@contextmanager
def abrir_flujo_chat(cuerpo,timeout=240):
    """Streaming acotado, con la misma reserva, CPU, reposo y política local."""
    plazo=time.monotonic()+max(.01,float(timeout))
    asegurar_servicio(timeout=min(10,max(.01,plazo-time.monotonic())))
    cuerpo=preparar_cuerpo('/api/chat',dict(cuerpo,stream=True),plazo)
    if not _TURNO.acquire(timeout=max(0,plazo-time.monotonic())):
        raise ErrorOllama('Otra petición sigue usando el modelo. Reintenta la medición cuando termine.',tipo='cola')
    try:
        with reservar(max(0,plazo-time.monotonic())):
            import control_recursos
            comprobar_sesion_abierta()
            control_recursos.comprobar(__import__(__name__),cuerpo,plazo_fin=plazo)
            restante=plazo-time.monotonic()
            if restante<=0:raise ErrorOllama('Se agotó la espera antes de iniciar la medición.',tipo='timeout')
            req=urllib.request.Request(BASE+'/api/chat',data=json.dumps(cuerpo).encode(),headers={'Content-Type':'application/json'})
            try:
                comprobar_sesion_abierta()
                with ABRIR(req,timeout=restante) as respuesta:
                    from lectura_http import lineas_acotadas,LimiteHTTP
                    def lineas():
                        comprobar_sesion_abierta()
                        try:
                            for linea in lineas_acotadas(respuesta,MAX_BYTES,plazo):
                                comprobar_sesion_abierta()
                                yield linea
                                comprobar_sesion_abierta()
                        except LimiteHTTP as e:raise ErrorOllama('El flujo supera el límite de respuesta; detuve la medición.',tipo='tamano') from e
                    yield lineas()
                    comprobar_sesion_abierta()
                    control_recursos.registrar(__import__(__name__),cuerpo)
            except (OSError,ValueError,urllib.error.URLError,ConnectionError,http.client.HTTPException) as exc:
                if sesion_cerrada():
                    if isinstance(exc,urllib.error.HTTPError):exc.close()
                    comprobar_sesion_abierta()
                raise _error(exc,plazo=plazo) from exc
    finally:
        import cache_recursos
        cache_recursos.invalidar();_TURNO.release()


def modelos():
    r=solicitar('/api/tags')
    lista=r.get('models',[])
    if not isinstance(lista,list):raise ErrorOllama('Ollama devolvió una lista de modelos no válida. /diagnostico permite revisar la conexión.',tipo='catalogo',servicio=True)
    import politica_ia
    nombres=[];vistos=set()
    for m in lista:
        if not isinstance(m,dict):continue
        nombre=m.get('name')
        if not isinstance(nombre,str) or not nombre.strip() or nombre!=nombre.strip() or len(nombre)>120 or any(ord(c)<32 for c in nombre):continue
        if m.get('remote_host') or m.get('remote_model') or politica_ia.modelo_cloud(nombre):continue
        if 'capabilities' in m:
            capacidades=m['capabilities']
            if not isinstance(capacidades,list) or not all(isinstance(x,str) for x in capacidades) or 'completion' not in capacidades:continue
        if nombre not in vistos:nombres.append(nombre);vistos.add(nombre)
    return nombres


def diagnostico():
    try:
        r=solicitar('/api/version',timeout=3)
        return {'ok':True,'version':str(r.get('version','?')),'modelos':modelos()}
    except ConnectionError as e:
        return {'ok':False,'error':str(e)}
