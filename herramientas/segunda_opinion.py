"""Opinión textual de otro modelo; nunca delega herramientas o permisos."""
import json
import os
import re
import cliente_ollama as O
import internet_jarvis as WEB
import perfiles_ia as P
import politica_ia as POLITICA

SESION = {}
ENDPOINTS = {nombre:p['url'] for nombre,p in P.PRESETS.items() if p['url']}
GUIA = 'Responde en español a esta consulta independiente. No tienes acceso al equipo, historial, memorias ni herramientas de Jarvis. No afirmes haber ejecutado acciones. Distingue hechos de incertidumbres. No uses emojis salvo que se pidan. No inventes datos actuales como clima, precios o noticias: si falta una fuente actual, dilo.'


def configuracion(perfil=''):
    POLITICA.comprobar_externa()
    if perfil:
        perfil={'claude':'Anthropic','chatgpt':'OpenAI','openai':'OpenAI','anthropic':'Anthropic','deepseek':'DeepSeek'}.get(perfil.casefold(),perfil)
        if perfil not in P.PRESETS:raise ValueError('Proveedor no admitido. /modelos muestra los modelos locales.')
        return P.configuracion(perfil)
    if not SESION and P.opciones()['configurado']:return P.configuracion()
    return dict(proveedor=SESION.get('proveedor',os.environ.get('JARVIS_IA_PROVEEDOR','OpenAI')),
                url=SESION.get('url',os.environ.get('JARVIS_IA_URL','')),
                modelo=SESION.get('modelo',os.environ.get('JARVIS_IA_MODELO','')),
                clave=SESION.get('clave',os.environ.get('JARVIS_IA_API_KEY','')))


def configurar(proveedor,url,modelo,clave):
    POLITICA.comprobar_externa()
    if proveedor not in P.PRESETS:raise ValueError('Proveedor no admitido.')
    url=WEB.validar_url(url or ENDPOINTS.get(proveedor,''))
    if proveedor in ENDPOINTS and url!=ENDPOINTS[proveedor]:raise ValueError('Para otra dirección elige Compatible.')
    if not isinstance(modelo,str) or not modelo.strip() or len(modelo)>100:raise ValueError('Indica el modelo exacto de tu proveedor.')
    if not isinstance(clave,str) or not clave.strip() or len(clave)>4096 or re.search(r'[\x00-\x20\x7f]',clave):raise ValueError('Indica una clave API válida, sin espacios.')
    SESION.clear();SESION.update(proveedor=proveedor,url=url,modelo=modelo.strip(),clave=clave)


def limpiar_texto(texto):
    return re.sub(r'<think>.*?</think>','',texto,flags=re.S).strip()


def listar_modelos_ia():
    try:
        return {'ok':True,'modelos':[m for m in O.modelos() if not any(x in m.casefold() for x in ('embed','embedding'))]}
    except ConnectionError as e:return {'ok':False,'error':str(e)}


def preguntar_ia(pregunta,modelo):
    try:
        if not isinstance(pregunta,str) or not 1<=len(pregunta.strip())<=8000:raise ValueError('La pregunta debe tener entre 1 y 8000 caracteres.')
        if modelo not in O.modelos():raise ValueError('Ese modelo no está instalado; usa /modelos. No descargué modelos.')
        if any(x in modelo.casefold() for x in ('embed','embedding')):raise ValueError('Un modelo de embeddings no genera respuestas de chat.')
        cuerpo={'model':modelo,'messages':[{'role':'system','content':GUIA},{'role':'user','content':pregunta}],
                                  'stream':False,'think':False,'keep_alive':'5s',
                                  'options':{'num_ctx':8192,'num_predict':1400}}
        import protocolo_deepseek as PROTOCOLO_DS
        estructurado=PROTOCOLO_DS.aplica(modelo)
        if estructurado:cuerpo=PROTOCOLO_DS.preparar(cuerpo)
        import configuracion_jarvis as C
        import recursos_ollama
        ajustes=C.leer()[0]
        r=O.solicitar('/api/chat',cuerpo,timeout=recursos_ollama.plazo(ajustes,modelo,len(pregunta)))
        texto=limpiar_texto(PROTOCOLO_DS.interpretar(r,[])['content'] if estructurado else r.get('message',{}).get('content',''))
        import formato_respuestas
        texto=formato_respuestas.presentar(pregunta,texto)
        if not texto:raise ValueError('El modelo no devolvió texto visible.')
        return {'ok':True,'modelo':modelo,'origen':'Ollama local','respuesta':texto[:10000],
                'recortado':r.get('done_reason')=='length' or len(texto)>10000}
    except (OSError,ValueError,TypeError,AttributeError) as e:return {'ok':False,'error':str(e)[:250]}


def preguntar_externa(pregunta,confirmar,perfil='',automatico=False):
    try:
        POLITICA.comprobar_externa()
        if not isinstance(pregunta,str) or not 1<=len(pregunta.strip())<=8000:raise ValueError('La pregunta debe tener entre 1 y 8000 caracteres.')
        c=configuracion(perfil)
        if not c.get('modelo') or not c.get('clave'):raise ValueError('Configura proveedor, modelo y clave en «Configurar IA», o consulta /ayuda internet.')
        # Valida también la configuración de entorno, sin persistir credenciales.
        proveedor=c['proveedor'];url=WEB.validar_url(c['url'] or ENDPOINTS.get(proveedor,''))
        if proveedor not in P.PRESETS:raise ValueError('Proveedor no admitido.')
        if proveedor in ENDPOINTS and url!=ENDPOINTS[proveedor]:raise ValueError('La dirección no corresponde al proveedor elegido.')
        if re.search(r'[\x00-\x20\x7f]',c['clave']) or len(c['clave'])>4096:raise ValueError('Clave API no válida.')
        autorizado=automatico and P.opciones()['automatico']
        if not autorizado and not confirmar(f"Consultar {proveedor}, modelo {c['modelo']}, en {url}. La API puede consumir saldo.\nSolo se enviará esta pregunta, sin historial ni memorias automáticas:\n\n{pregunta}"):
            return {'ok':False,'error':'No autorizaste la consulta externa. No envié la pregunta.'}
        headers={'Content-Type':'application/json'}
        protocolo=c.get('protocolo',P.PRESETS[proveedor]['protocolo'])
        if protocolo=='Anthropic':
            headers.update({'x-api-key':c['clave'],'anthropic-version':'2023-06-01'})
            body={'model':c['modelo'],'max_tokens':1400,'system':GUIA,'messages':[{'role':'user','content':pregunta}]}
        else:
            headers['Authorization']='Bearer '+c['clave']
            body={'model':c['modelo'],'messages':[{'role':'system','content':GUIA},{'role':'user','content':pregunta}],
                  'stream':False,('max_completion_tokens' if protocolo=='OpenAI' else 'max_tokens'):2000}
            if proveedor=='DeepSeek':body['thinking']={'type':'disabled'}
        datos,_,_=WEB.solicitar_publico(url,json.dumps(body).encode(),headers,timeout=60 if automatico else 90)
        r=json.loads(datos)
        if protocolo=='Anthropic':
            texto='\n'.join(x['text'] for x in r.get('content',[]) if x.get('type')=='text');limite=r.get('stop_reason')=='max_tokens'
        else:
            eleccion=r['choices'][0];texto=eleccion['message'].get('content') or eleccion['message'].get('refusal','');limite=eleccion.get('finish_reason')=='length'
        texto=limpiar_texto(texto)
        if not texto:raise ValueError('La IA externa no devolvió texto visible.')
        if c.get('credencial'):
            try:P.registrar_resultado(proveedor,True)
            except (ValueError,OSError):pass
        return {'ok':True,'modelo':c['modelo'],'origen':proveedor,'respuesta':texto[:10000],'recortado':limite or len(texto)>10000}
    except (OSError,ValueError,TypeError,KeyError,IndexError,AttributeError,WEB.http.client.HTTPException) as e:
        # Nunca muestra cuerpo HTTP, credenciales ni excepciones del SDK.
        if isinstance(e,ConnectionError):error=mensaje_error_api(e)
        elif isinstance(e,ValueError) and not isinstance(e,json.JSONDecodeError):error=str(e)
        else:error='No pude completar la consulta externa. Comprueba conexión, modelo, saldo y clave.'
        if 'c' in locals() and c.get('credencial'):
            try:P.registrar_resultado(c['proveedor'],False,error)
            except (ValueError,OSError):pass
        return {'ok':False,'error':error[:700],'diagnostico':dict(getattr(e,'diagnostico',{}))}


def listar_modelos_remotos(proveedor,url,clave):
    try:
        POLITICA.comprobar_externa()
        configurar_datos(proveedor,url,clave)
        url=url or ENDPOINTS.get(proveedor,'')
        if proveedor=='Anthropic':endpoint='https://api.anthropic.com/v1/models';headers={'x-api-key':clave,'anthropic-version':'2023-06-01'}
        else:endpoint=url.rsplit('/chat/completions',1)[0]+'/models';headers={'Authorization':'Bearer '+clave}
        b,_,_=WEB.solicitar_publico(endpoint,headers=headers);d=json.loads(b)
        modelos=[m['id'] for m in d.get('data',[]) if isinstance(m,dict) and isinstance(m.get('id'),str)]
        modelos=[m for m in modelos if not any(x in m.casefold() for x in ('embedding','whisper','tts','realtime','image','dall-e','moderation','sora','veo'))]
        if not modelos:raise ValueError('La API no devolvió modelos de conversación. Puedes indicar el ID exacto de su catálogo.')
        return {'ok':True,'modelos':sorted(set(modelos))}
    except (OSError,ValueError,TypeError,KeyError,WEB.http.client.HTTPException) as e:
        return {'ok':False,'error':mensaje_error_api(e)+' Puedes escribir el ID exacto del catálogo si el listado no está disponible.'}


def configurar_datos(proveedor,url,clave):
    if proveedor not in P.PRESETS:raise ValueError('Proveedor no admitido.')
    url=WEB.validar_url(url or ENDPOINTS.get(proveedor,''))
    if proveedor in ENDPOINTS and url!=ENDPOINTS[proveedor]:raise ValueError('Endpoint incorrecto.')
    if not clave or len(clave)>4096 or re.search(r'[\x00-\x20\x7f]',clave):raise ValueError('Clave API no válida.')


def modelo_sugerido(proveedor,modelos):
    preferencias={'OpenAI':('gpt-4.1-mini','gpt-4o-mini'),'DeepSeek':('deepseek-flash',)}
    for m in preferencias.get(proveedor,()):
        if m in modelos:return m
    candidatos=[m for m in modelos if ('haiku' in m if proveedor=='Anthropic' else 'mini' in m if proveedor=='OpenAI' else True) and 'preview' not in m and 'exp' not in m]
    return sorted(candidatos)[-1] if candidatos else modelos[0] if modelos else ''


def mensaje_error_api(error):
    texto=str(error)
    d=getattr(error,'diagnostico',{})
    motivo=d.get('motivo','');causa=d.get('causa','')
    if causa=='clave_bloqueada':return 'El proveedor bloqueó la clave por detectarla expuesta. Crea otra en su panel y reemplázala en Jarvis; no la pegues en el chat.'
    if causa=='clave_caducada':return 'El proveedor indica que la clave caducó. Renueva la clave en su panel y reemplázala en «Configurar IA».'
    if causa=='clave_invalida' or motivo=='API_KEY_INVALID':return 'El proveedor indica que la clave no es válida. Comprueba el servicio y reemplázala en «Configurar IA».'
    if causa=='restricciones_clave' or motivo in {'API_KEY_SERVICE_BLOCKED','API_KEY_HTTP_REFERRER_BLOCKED','API_KEY_IP_ADDRESS_BLOCKED'}:
        return 'La clave tiene restricciones que bloquean esta llamada. Revisa permisos y restricciones de aplicación/IP en el panel del proveedor. Una clave limitada a un navegador no sirve para este cliente de escritorio.'
    if causa=='servicio_deshabilitado' or motivo=='SERVICE_DISABLED':return 'El proveedor indica que la API está deshabilitada. Revisa el servicio asociado a la clave en su panel.'
    if d.get('cuota_cero'):return 'El proveedor devuelve cuota 0 para esta operación/modelo. Esperar o repetir no habilita una cuota de cero. Revisa los límites del proyecto en el panel del proveedor; Jarvis no activa facturación.'
    if 'HTTP 401' in texto:return 'La API rechazó la clave (HTTP 401). Revisa que pertenezca al servicio elegido y cópiala completa.'
    if 'HTTP 403' in texto:return 'La API no permite esta operación (HTTP 403). Revisa permisos de la clave, API habilitada, región y acceso al modelo. No confirma que necesites pagar; cargar modelos tampoco confirma permiso para generar respuestas.'
    if 'HTTP 429' in texto:
        extra=(' Límite diario: revisa cuándo se restablece en el panel.' if d.get('periodo')=='diario' else f" Espera al menos {d['espera_segundos']} segundos antes de probar otra vez." if d.get('espera_segundos') else '')
        return 'La API alcanzó una cuota o límite de uso (HTTP 429).'+extra+' Revisa los límites activos del proyecto y modelo en el panel del proveedor. No repetí la consulta ni activé facturación. La lectura de archivos, web y clima siguen disponibles sin esa API.'
    if 'HTTP 404' in texto:return 'La API no encontró el endpoint o modelo (HTTP 404). Carga los modelos y revisa la dirección.'
    if 'HTTP 400' in texto:return 'La API rechazó los parámetros o el modelo (HTTP 400). Selecciona otro modelo de chat disponible.'
    if isinstance(error,TimeoutError):return 'La API no respondió dentro del tiempo disponible. No repetí la consulta automáticamente.'
    return 'No pude conectar con la API. Revisa Internet, clave, modelo y disponibilidad del proveedor.'


def presentar(r):
    if not r.get('ok'):return 'No pude pedir una segunda opinión: '+r.get('error','sin respuesta')
    return f"Segunda opinión · {r['origen']} · {r['modelo']}\n\n{r['respuesta']}"+ ('\n[Aviso: respuesta recortada.]' if r.get('recortado') else '')
