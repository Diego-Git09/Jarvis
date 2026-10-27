"""Excepción Zen acotada. Solo pregunta actual genérica, nunca herramientas."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime,timezone
from entorno_jarvis import DATOS
from seguridad_texto import privacidad_externa

ENDPOINT='https://opencode.ai/inference/openai/v1/chat/completions'
CATALOGO='https://opencode.ai/inference/v1/models'
CLAVE=Path.home()/'.config/jarvis/zen.key'
ARCHIVO=DATOS/'externo_zen.json'
REGISTRO=Path(__file__).with_name('registro_externos.json')
AUDITORIA=DATOS/'envios_zen.jsonl'
LOCK=threading.RLock()
_ACTIVOS=set()

def estado():
    inicial={'encendido':False,'modelos':{},'ultimo_error':'','revision':0}
    try:
        if ARCHIVO.is_symlink() or ARCHIVO.stat().st_size>500000:raise ValueError('Configuración inválida')
        d=json.loads(ARCHIVO.read_text())
        if not isinstance(d,dict) or type(d.get('encendido')) is not bool:raise ValueError('Configuración inválida')
        return dict(inicial,**d)
    except (OSError,ValueError):return inicial

def guardar(d):
    from conversaciones_jarvis import _atomic
    _atomic(ARCHIVO,d)

def modelos():
    try:
        if REGISTRO.is_symlink() or REGISTRO.stat().st_size>100000:raise ValueError('Registro inválido')
        r=json.loads(REGISTRO.read_text())
        if not isinstance(r,list):return []
        e=estado();estados=e['modelos'];resultado=[]
        for x in r:
            if not isinstance(x,dict) or not isinstance(x.get('id'),str) or not isinstance(x.get('estado'),str) or not isinstance(x.get('capacidades',{}),dict) or not isinstance(x.get('metricas',{}),dict):continue
            cats=x.get('metricas',{}).get('categorias',{})
            if not isinstance(cats,dict) or any(not isinstance(v,dict) for v in cats.values()):continue
            status=estados.get(x['id'],x['estado'])
            if e.get('no_disponible_hasta',{}).get(x['id'],0)>time.time():status='no disponible'
            resultado.append(dict(x,estado=status))
        return resultado
    except (OSError,ValueError,KeyError):return []

def clave():
    for k in ('OPENCODE_ZEN_API_KEY','OPENCODE_API_KEY','ZEN_API_KEY'):
        v=os.environ.get(k)
        if v:return v.strip()
    try:
        fd=os.open(CLAVE,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd) as f:
            s=os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_mode&0o077 or s.st_uid!=os.getuid() or s.st_size>2048:return ''
            return f.read().strip()
    except OSError:return ''

def guardar_clave(valor):
    if not isinstance(valor,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{12,1024}',valor):raise ValueError('Formato de clave no válido; no se guardó.')
    if CLAVE.is_symlink() or any(p.is_symlink() for p in CLAVE.parents):raise ValueError('La ruta de credenciales no admite enlaces.')
    CLAVE.parent.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(CLAVE.parent,0o700)
    import tempfile
    fd,p=tempfile.mkstemp(prefix='.zen-',dir=CLAVE.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(valor);f.flush();os.fsync(f.fileno())
        os.replace(p,CLAVE);os.chmod(CLAVE,0o600)
    finally:
        if os.path.exists(p):os.unlink(p)

class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kw):raise ValueError('Zen devolvió una redirección; no se reenviaron credenciales.')

def _mensaje_http(error):
    """Describe solo un bloqueo conocido; nunca muestra el cuerpo remoto ni secretos."""
    mensaje='Zen respondió HTTP '+str(error.code)+'.'
    if error.code!=403:return mensaje
    try:
        raw=error.read(32769)
        if len(raw)>32768:return mensaje
        dato=json.loads(raw)
        error_dato=dato.get('error',dato) if isinstance(dato,dict) else None
        if isinstance(error_dato,dict) and error_dato.get('type')=='FreeTierError':
            return mensaje+' El servidor restringió el acceso al nivel gratuito (FreeTierError). Consultar el catálogo no acredita generación ni que la clave sea inválida.'
        tipo=dato.get('type') if isinstance(dato,dict) else None
        if tipo=='https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/':
            return mensaje+' Cloudflare bloqueó la identificación del cliente (error 1010). Esto no confirma que la clave sea inválida ni que falte saldo. Actualiza o reinicia Jarvis; si persiste, consulta al soporte de OpenCode.'
    except (OSError,ValueError,TypeError):pass
    return mensaje

def transporte(url,cuerpo=None,token='',cancelado=None):
    if url not in {ENDPOINT,CATALOGO}:raise ValueError('Destino de IA no permitido.')
    if url==ENDPOINT and estado().get('transporte')=='cliente_oficial':
        import cliente_opencode
        def registrar(handle):
            with LOCK:
                if not estado()['encendido']:
                    handle.close();raise ConnectionError('Externo apagado; consulta cancelada.')
                _ACTIVOS.add(handle)
        def retirar(handle):
            with LOCK:_ACTIVOS.discard(handle)
        return cliente_opencode.consultar(cuerpo,token,cancelado,registrar,retirar)
    headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'Jarvis/1.0'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(url,json.dumps(cuerpo).encode() if cuerpo is not None else None,headers)
    op=urllib.request.build_opener(urllib.request.ProxyHandler({}),SinRedireccion())
    try:
        with op.open(req,timeout=35) as r:
            with LOCK:
                if cancelado and cancelado.is_set():raise ConnectionError('Envío cancelado')
                _ACTIVOS.add(r)
            try:
                datos=r.read(2_000_001)
                if len(datos)>2_000_000:raise ConnectionError('Zen excedió el límite de respuesta')
                return json.loads(datos)
            finally:
                with LOCK:_ACTIVOS.discard(r)
    except urllib.error.HTTPError as e:
        try:mensaje=_mensaje_http(e)
        finally:e.close()
        raise ConnectionError(mensaje) from None
    except (OSError,ValueError) as e:raise ConnectionError('Zen: '+type(e).__name__+'. Sin causa adicional confirmada.') from None

def apagar():
    with LOCK:
        d=estado();d['encendido']=False;d['revision']+=1;guardar(d)
        for r in tuple(_ACTIVOS):
            try:r.close()
            except OSError:pass
    return 'Externo apagado. No se iniciarán nuevos envíos; las respuestas en curso se descartan. Los datos ya enviados no pueden retirarse.'

def anotar_envio(pregunta,modelo,motivo):
    AUDITORIA.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if any(p.is_symlink() for p in AUDITORIA.parents):raise ValueError('Ruta de auditoría no segura')
    r={'hora':datetime.now(timezone.utc).isoformat(),'modelo':modelo,'motivo':motivo,'bytes':len(pregunta.encode()),'sha256':hashlib.sha256(pregunta.encode()).hexdigest()}
    with LOCK:
        fd=os.open(AUDITORIA,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600);os.fchmod(fd,0o600)
        with os.fdopen(fd,'a') as f:f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())

def actualizar_catalogo(confirmar,solicitar=None):
    if not clave():return 'No hay clave Zen. Configúrala con /externo clave por entrada oculta.'
    if not confirmar('Consultar el catálogo de modelos de Zen y guardar solo sus IDs y metadatos, sin conversaciones?'):return 'Catálogo sin cambios.'
    d=(solicitar or transporte)(CATALOGO,token=clave())
    ids=[x['id'] for x in d.get('data',[]) if isinstance(x,dict) and isinstance(x.get('id'),str)]
    if not ids or len(ids)>1000:raise ValueError('Catálogo Zen inválido')
    with LOCK:
        e=estado();e.update(catalogo=ids,catalogo_fecha=time.time());e.pop('catalogo_reintentar_despues',None);guardar(e)
    return 'Catálogo consultado con la clave y guardado: '+str(len(ids))+' IDs. Esto no prueba generación ni acceso a cada modelo.'

def respuesta_capacidades(pregunta,automatico=None):
    """Estado local verificable para consultas de conexión; no inicia una llamada."""
    from normalizacion_entrada import vista
    if not isinstance(pregunta,str) or '\n' in pregunta or '`' in pregunta:return None
    n=vista(pregunta).strip(' ¿?¡!.,')
    if len(n)>260 or '\n' in n or '`' in n:return None
    if not re.search(r'\b(?:open ?ai|chat ?gpt|deep ?seek|open ?code|opencode|zen|otra ia|ias externas|la nube)\b',n):return None
    if not re.match(r'(?:(?:hola|oye)[, ]+)?(?:jarvis[, ]+)?(?:puedes|podrias|te puedes|eres capaz de|estas|tienes|que modelos|a que modelos|con que modelos)\b',n):return None
    if not re.search(r'\b(?:conectar|conectarte|conectado|conexion|acceder|usar|consultar|hablar|modelos)\b',n):return None
    if re.search(r'\b(?:para|borra|elimina|mueve|escribe|genera|crea|analiza|explica|responde|adjunto|archivo|token|clave)\b',n):return None
    e=estado();hay_clave=bool(clave())
    if e['encendido'] and hay_clave and 'FreeTierError' in e.get('ultimo_error',''):
        texto='La integración con DeepSeek por OpenCode está activada, pero el servicio está rechazando las respuestas gratuitas (HTTP 403, FreeTierError). Mientras ocurra, respondo con los modelos locales.'
    elif e['encendido'] and hay_clave:
        texto='Sí. Tengo activado OpenCode Zen para consultar DeepSeek con preguntas genéricas.'
    elif e['encendido']:
        texto='Tengo la integración con DeepSeek por OpenCode Zen activada, pero falta una clave legible; todavía no puedo enviar consultas.'
    else:
        texto='Tengo integración con DeepSeek mediante OpenCode Zen, pero está apagada. Puedes activarla desde OpenCode API o con /externo encender.'
    if automatico is None:
        from configuracion_jarvis import leer
        automatico=leer()[0]['seleccion_modelo']=='automatico'
    texto+='\n'+('La selección automática está activa: Qwen local para consultas sencillas, DeepSeek local para análisis y código, y DeepSeek por OpenCode como respaldo cuando hace falta y la pregunta admite envío externo.' if automatico else 'La selección está en modo manual; /modelo automatico permite alternar según la tarea.')
    if re.search(r'\b(?:open ?ai|chat ?gpt)\b',n):texto+='\nLa conexión directa a OpenAI no está habilitada.'
    texto+='\nLos archivos, adjuntos y recuerdos permanecen locales. /modelo muestra la última elección y su motivo.'
    return texto

def preferencia(pregunta,estado_turno):
    from texto_visible_usuario import visible
    from normalizacion_entrada import plegar
    n=plegar(visible(pregunta))
    if re.search(r'\b(?:solo local|sin internet|sin (?:la )?nube|no uses internet|no uses (?:el )?externo|no uses (?:la )?nube)\b',n):estado_turno['_preferencia_externa']='local'
    elif re.search(r'\b(?:usa|usar) (?:(?:el )?(?:externo|gratis|de internet|deepseek flash|online|opencode|zen)|la nube)\b',n):estado_turno['_preferencia_externa']='externo'
    return estado_turno.get('_preferencia_externa')

def elegir(pregunta,clase,estado_turno,*,fallo=False,recursos=False,contexto=False,descargado=False,renovar=False):
    preferencia(pregunta,estado_turno)
    n=pregunta.casefold()
    ok,motivo=privacidad_externa(pregunta,adjuntos=bool(estado_turno.get('_adjuntos_turno') or estado_turno.get('_fuentes_turno')),memoria=bool(estado_turno.get('_uso_memoria_turno')),herramientas=bool(estado_turno.get('_hubo_herramientas_turno')))
    if not ok:return None,motivo
    if estado_turno.get('_preferencia_externa')=='local':return None,'preferencia de esta conversación: solo local'
    e=estado()
    if not e['encendido']:return None,'externo apagado'
    if clase!='compleja':return None,'las consultas simples y comandos se mantienen locales'
    if not (fallo or recursos or contexto or descargado or estado_turno.get('_preferencia_externa')=='externo'):return None,'la respuesta local no requiere escalado'
    if not clave():return None,'falta clave Zen'
    if time.time()-e.get('catalogo_fecha',0)>86400:
        if not renovar:return None,'catálogo autenticado pendiente o vencido; usa /externo modelos actualizar'
        if e.get('catalogo_reintentar_despues',0)>time.time():return None,'la renovación del catálogo falló recientemente; se mantiene local'
        # El permiso persistente de Zen cubre renovar solo IDs, después del
        # filtro privado y de comprobar que este turno necesita respaldo.
        try:
            actualizar_catalogo(lambda _:True)
            e=estado()
        except (OSError,ValueError,ConnectionError) as error:
            mensaje=str(error) if isinstance(error,ConnectionError) else 'No se pudo verificar el catálogo de Zen.'
            with LOCK:
                d=estado();d.update(ultimo_error=mensaje,catalogo_reintentar_despues=time.time()+60);guardar(d)
            return None,'no se pudo renovar el catálogo: '+mensaje
        if not e['encendido']:return None,'externo apagado durante la consulta del catálogo'
        if time.time()-e.get('catalogo_fecha',0)>86400:return None,'no se confirmó un catálogo reciente; se mantiene local'
    candidatos=[m for m in modelos() if m['estado']=='permitido' and m['id'] in e.get('catalogo',[]) and m.get('privacidad')!='desconocida' and m.get('capacidades',{}).get('texto') is True and m.get('endpoint')==ENDPOINT and not m.get('solo_evaluacion') and '-vl-' not in m['id']]
    # Solo métricas acreditadas; el modelo inicial permitido conserva prioridad.
    categoria='codigo' if re.search(r'\b(?:codigo|python|sql|java|kotlin|funcion|programa)\b',n) else 'razonamiento'
    def medida(m):
        d=m.get('metricas',{}).get('categorias',{}).get(categoria,{})
        utilidad=d.get('utilidad',0);latencia=d.get('mediana_segundos',100000)
        return (-utilidad if type(utilidad) in {int,float} and 0<=utilidad<=1 else 0,latencia if type(latencia) in {int,float} and 0<=latencia<100000 else 100000,m['id']!='deepseek-v4.1-flash-free')
    candidatos=[m for m in candidatos if m['id']=='deepseek-v4.1-flash-free' or m.get('metricas',{}).get('categorias',{}).get(categoria,{}).get('ventaja_verificada') is True]
    candidatos.sort(key=medida)
    if not candidatos:
        if 'FreeTierError' in e.get('ultimo_error',''):return None,'OpenCode rechazó el nivel gratuito (HTTP 403, FreeTierError); se mantiene local'
        return None,'no hay modelo permitido disponible con privacidad documentada'
    return candidatos[0],('fallo local' if fallo else 'recursos locales' if recursos else 'contexto extenso' if contexto else 'preferencia explícita' if estado_turno.get('_preferencia_externa')=='externo' else 'carga local lenta')

def evaluar_modelo(ident,confirmar,solicitar=None):
    """Banco fijo sintético. No acepta preguntas ni conversaciones del usuario."""
    m=next((x for x in modelos() if x['id']==ident),None)
    if not m:return 'ID no encontrado.'
    if m.get('endpoint')!=ENDPOINT or '-vl-' in ident:return 'Ese protocolo o modelo de visión no se utiliza en este banco de texto.'
    if not clave():return 'No probado con el servicio real: falta la clave Zen.'
    e=estado()
    if ident not in e.get('catalogo',[]) or time.time()-e.get('catalogo_fecha',0)>86400:return 'Actualiza primero el catálogo autenticado con /externo modelos actualizar.'
    if not confirmar('Evaluar '+ident+' exclusivamente con las 40 preguntas sintéticas congeladas y tres contratos de código de ejemplo; guardar sus respuestas en datos privados para revisión. Los filtros pueden bloquear algunos casos. No se promueve ningún modelo automáticamente.'):return 'Evaluación cancelada.'
    from medir_seleccion_20261020 import CASOS
    from conversaciones_jarvis import _atomic
    preguntas=[x[0] for x in CASOS]+['Escribe una función Python que sume dos enteros. Solo texto.','Escribe una consulta SQL que seleccione una constante entera. Solo texto.','Escribe una función Kotlin de identidad de Int. Solo texto.']
    resultados=[]
    for i,p in enumerate(preguntas,1):
        ok,causa=privacidad_externa(p)
        if not ok:resultados.append({'id':i,'estado':'bloqueado por privacidad','motivo':causa});continue
        inicio=time.monotonic()
        try:
            if estado()['revision']!=e['revision']:break
            cuerpo={'model':ident,'messages':[{'role':'system','content':'Responde en español. Solo texto; sin herramientas ni acciones.'},{'role':'user','content':p}],'stream':False,'max_tokens':1400}
            anotar_envio(p,ident,'banco sintético autorizado')
            r=(solicitar or transporte)(ENDPOINT,cuerpo,token=clave());mensaje=r['choices'][0]['message']
            if estado()['revision']!=e['revision']:
                resultados.append({'id':i,'estado':'respuesta descartada por cancelación'});break
            if mensaje.get('tool_calls') or not isinstance(mensaje.get('content'),str):raise ValueError('Respuesta no textual')
            from conversaciones_jarvis import _redactar
            token_usado=clave()
            protegido=mensaje['content'].replace(token_usado,'[TOKEN ZEN REDACTADO]') if len(token_usado)>=12 else mensaje['content']
            limpio=_redactar(protegido)
            resultados.append({'id':i,'pregunta_sintetica':p,'respuesta_original':limpio,'secretos_redactados':limpio!=mensaje['content'],'segundos':round(time.monotonic()-inicio,3),'estado':'pendiente de revisión cualitativa'})
        except (ConnectionError,ValueError,KeyError,IndexError,TypeError) as error:
            resultados.append({'id':i,'estado':'fallo','tipo':type(error).__name__,'error':str(error) if isinstance(error,(ValueError,ConnectionError)) else 'formato inválido'})
            if isinstance(error,ConnectionError):break
    destino=DATOS/'evaluaciones_zen'/('banco_'+ident+'_'+str(time.time_ns())+'.json')
    _atomic(destino,{'modelo':ident,'solo_sintetico':True,'resultados':resultados,'promocion':False,'calidad':'pendiente de revisión; este banco no ejecuta código externo'})
    return 'Banco guardado en '+str(destino)+'. Casos registrados: '+str(len(resultados))+'. No se promovió el modelo. Revisa calidad, política y comparación antes de permitirlo.'

def preguntar(pregunta,modelo,motivo,solicitar=None):
    ok,causa=privacidad_externa(pregunta)
    if not ok:raise ValueError('Consulta externa bloqueada: '+causa)
    with LOCK:
        e=estado()
        if not e['encendido']:raise ValueError('Externo apagado')
        revision=e['revision']
    # Valida nuevamente el ID y estado aunque el llamador ya haya elegido.
    permitidos={m['id'] for m in modelos() if m['estado']=='permitido' and m.get('privacidad')!='desconocida' and m.get('endpoint')==ENDPOINT and '-vl-' not in m['id'] and m.get('capacidades',{}).get('texto') is True and not m.get('solo_evaluacion')}
    if modelo['id'] not in permitidos or modelo['id'] not in e.get('catalogo',[]):raise ValueError('Modelo no permitido o no disponible')
    token=clave()
    if not token:raise ValueError('Falta la clave Zen; no se intentó una conexión externa')
    cuerpo={'model':modelo['id'],'messages':[{'role':'system','content':'Responde en español con pasos simples. Solo devuelve texto. No tienes herramientas ni acceso a archivos ni memorias. No afirmes haber realizado acciones.'},{'role':'user','content':pregunta}],'stream':False,'max_tokens':2048}
    from conversaciones_jarvis import _atomic
    # El registro es requisito previo: si falla, no hay envío. Sin texto ni clave.
    anotar_envio(pregunta,modelo['id'],motivo)
    try:
        respuesta=(solicitar or transporte)(ENDPOINT,cuerpo,token=token)
        m=respuesta['choices'][0]['message'];texto=m.get('content')
        if m.get('tool_calls') or not isinstance(texto,str) or not texto.strip():raise ValueError('Zen no devolvió solo texto')
        token_usado=clave()
        if len(token_usado)>=12:texto=texto.replace(token_usado,'[TOKEN ZEN REDACTADO]')
        from calidad_respuesta import filtraciones
        if filtraciones(texto):raise ValueError('Respuesta externa no válida para presentar')
        with LOCK:
            actual=estado()
            if not actual['encendido'] or actual['revision']!=revision:raise ValueError('Respuesta descartada por cambio de autorización')
            actual.update(ultimo_error='',ultima_respuesta_verificada={'hora':datetime.now(timezone.utc).isoformat(),'modelo':modelo['id']});guardar(actual)
        return 'Respondió: externo, '+modelo['id']+' (texto sin acciones verificadas).\n\n'+texto
    except (ConnectionError,ValueError,KeyError,IndexError,TypeError) as exc:
        mensaje=str(exc) if isinstance(exc,(ConnectionError,ValueError)) else 'Respuesta Zen con formato inválido'
        with LOCK:
            d=estado();d['ultimo_error']=mensaje
            if 'FreeTierError' in mensaje:d.setdefault('no_disponible_hasta',{})[modelo['id']]=time.time()+600
            elif re.search(r'HTTP (?:404|410)',mensaje):d['modelos'][modelo['id']]='no disponible'
            elif re.search(r'HTTP (?:429|5\d\d)',mensaje):d.setdefault('no_disponible_hasta',{})[modelo['id']]=time.time()+60
            guardar(d)
        raise ConnectionError(mensaje) from None

def comando(p,confirmar):
    if not p.startswith('/externo'):return False,''
    try:
        if p=='/externo clave':
            import sys
            if not sys.stdin.isatty():return True,'Abre /externo clave en la interfaz gráfica o en una terminal interactiva. No pegues la clave en el chat.'
            if not confirmar('Guardar la clave Zen fuera del proyecto, en archivo privado con permisos 600?'):return True,'Clave sin cambios.'
            guardar_clave(getpass.getpass('Clave Zen (oculta): '));return True,'Clave guardada fuera del proyecto. El externo conserva su estado anterior.'
        if p=='/externo apagar':return True,apagar()
        if p=='/externo encender':
            if not clave():return True,'Primero configura /externo clave. No pegues la clave en el chat.'
            if not confirmar('Activar Zen solo para preguntas genéricas y con filtro de privacidad, sin archivos, adjuntos, memoria ni herramientas?'):return True,'Externo sin activar.'
            with LOCK:
                d=estado();d['encendido']=True;d['revision']+=1;guardar(d)
            return True,'Externo encendido. Siempre se intenta local primero. Falta catálogo autenticado si no lo actualizaste: /externo modelos actualizar.'
        if p=='/externo modelos actualizar':return True,actualizar_catalogo(confirmar)
        if p.startswith('/externo evaluar '):return True,evaluar_modelo(p.split(maxsplit=2)[2],confirmar)
        if p=='/externo modelos':return True,'Modelos externos (ninguno puede recibir imágenes):\n'+'\n'.join(m['id']+' · '+m['estado']+' · privacidad: '+m.get('privacidad','desconocida') for m in modelos())
        m=re.fullmatch(r'/externo (permitir|bloquear) ([\w.-]+)',p)
        if m:
            listado=modelos();modelo=next((x for x in listado if x['id']==m[2]),None)
            if not modelo:return True,'ID no encontrado en el registro.'
            if m[1]=='permitir':
                if modelo.get('privacidad')=='desconocida':return True,'No se permite promover un modelo con privacidad desconocida.'
                if not modelo.get('metricas',{}).get('ventaja_verificada') and m[2]!='deepseek-v4.1-flash-free':return True,'Falta una ventaja medida y revisada para promover ese modelo.'
                if sum(x['estado']=='permitido' for x in listado)>=3 and modelo['estado']!='permitido':return True,'Máximo tres externos permitidos.'
            if not confirmar(m[1].capitalize()+' '+m[2]+' en el registro externo?'):return True,'Registro sin cambios.'
            with LOCK:
                d=estado();d['modelos'][m[2]]='permitido' if m[1]=='permitir' else 'bloqueado';guardar(d)
            return True,'Registro actualizado y comprobado.'
        if p in {'/externo','/externo estado'}:
            d=estado();ultimos=[]
            if AUDITORIA.is_file() and not AUDITORIA.is_symlink():
                with AUDITORIA.open('rb') as f:f.seek(max(0,AUDITORIA.stat().st_size-8192));ultimos=f.read().decode(errors='replace').splitlines()[-3:]
            requisitos=[]
            if not d['encendido']:requisitos.append('está apagado: no envía preguntas')
            if not clave():requisitos.append('falta una clave válida: no intenta conectarse')
            if not d.get('catalogo_fecha'):requisitos.append('catálogo autenticado sin comprobar')
            return True,'Zen '+('encendido' if d['encendido'] else 'apagado')+' · clave '+('detectada localmente; autenticidad y origen sin verificar' if clave() else 'ausente')+' · último error: '+(d['ultimo_error'] or 'ninguno registrado')+'\n'+('; '.join(requisitos) or 'Requisitos presentes; esto no acredita una respuesta del servicio real.')+'\nModelos y permisos: /externo modelos. Últimos envíos (sin texto):\n'+('\n'.join(ultimos) or 'ninguno registrado')
        return True,'Usa /externo estado|clave|encender|apagar|modelos o /externo permitir|bloquear ID.'
    except (OSError,ValueError,ConnectionError) as e:return True,'Externo: '+str(e)
