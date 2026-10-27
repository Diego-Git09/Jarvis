"""Configuración, sesiones y diagnóstico: acciones del usuario sin pasar por Qwen."""
import shutil
import re
import shlex
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from lenguaje_jarvis import normalizar, limpiar, NUMEROS, seleccion, definir_expresion, sin_literales, no_es_peticion
import configuracion_jarvis as C
import sesiones_jarvis as S
import cliente_ollama as O
import tareas_jarvis as T
from contexto_jarvis import estado_contexto
import calculos_jarvis as CALC
import sincronizacion_jarvis as SYNC
from entorno_jarvis import PROYECTO, TRABAJO
import mejoras_jarvis as MEJORAS
import estructura_jarvis as ESTRUCTURA
import internet_jarvis as WEB
import segunda_opinion as IA
import clima_jarvis as CLIMA
import acceso_archivos as ACCESO
import interfaz_recordatorios as RECORDATORIOS
import proyectos_codigo as CODIGO
import seguimiento_conversacion as SEGUIMIENTO
import tandas_documentales as TANDAS
import vocabulario_pendientes as VOCAB_PENDIENTES


def comando_local(pregunta,historial,estado,confirmar,ajustes,aplicar_config,cerebro,estadisticas=None,ejecutar=None,avisar=None):
    anterior=estado.get('_ultima_decision_modelo')
    resultado=_comando_local(pregunta,historial,estado,confirmar,ajustes,aplicar_config,cerebro,estadisticas,ejecutar,avisar)
    generativo=pregunta.strip().casefold().startswith(('/mensaje_completo ','/resumir tanda generado','/preguntar_ia '))
    if resultado[0] and generativo and estado.get('_ultima_decision_modelo') is anterior:
        estado['_ultima_decision_modelo']={'modelo':ajustes['modelo'],'preferido':ajustes['modelo'],'regla':'comando_generativo','motivo':'consulta generativa local pedida explícitamente; revisar el resultado por si se detuvo antes de inferir'}
    elif resultado[0] and estado.get('_ultima_decision_modelo') is anterior and ajustes.get('seleccion_modelo')=='automatico' and not pregunta.strip().casefold().startswith(('/modelo','/escalar')):
        from enrutador_modelos import clasificar_peticion
        estado['_ultima_decision_modelo']=dict(clasificar_peticion(pregunta),sin_inferencia=True)
    return resultado


def _comando_local(pregunta,historial,estado,confirmar,ajustes,aplicar_config,cerebro,estadisticas=None,ejecutar=None,avisar=None):
    import administracion_local
    if administracion_local.es_entrada(pregunta,estado):
        hecho,texto=administracion_local.comando(pregunta,estado,confirmar)
        if hecho:return True,texto
    acceso_ollama=pregunta.strip().casefold()
    if acceso_ollama in {'/ollama','/ollama estado','/ollama reintentar'}:
        if acceso_ollama=='/ollama reintentar':
            try:
                O.activar_servicio()
                O.asegurar_servicio(timeout=10)
            except ConnectionError as e:return True,str(e)+' Puedes seguir usando archivos, tareas y recuerdos con los accesos directos.'
        dato=O.estado_servicio()
        gestion=dato['gestion']
        texto=('Ollama disponible, versión '+dato['version']+'.' if dato['ok'] else dato.get('error','Ollama no está disponible.'))
        texto+='\nInicio automático: '+('activado.' if ajustes.get('autoinicio_ollama',True) else 'desactivado en la configuración.')
        if gestion=='iniciado_por_jarvis':texto+='\nEste servidor lo inició Jarvis. Se detendrá cuando cierre la última sesión de Jarvis que lo usa.'
        elif gestion=='preexistente':texto+='\nOllama ya estaba encendido. Cerrar Jarvis lo dejará funcionando.'
        else:texto+='\nNo hay un servidor propio confirmado en esta sesión; no se detendrán procesos ajenos.'
        return True,texto
    import externo_zen
    hecho,texto=externo_zen.comando(pregunta.strip(),confirmar)
    if hecho:return True,texto
    import vocabulario_privado
    hecho,texto=vocabulario_privado.comando(pregunta.strip(),confirmar)
    if hecho:return True,texto
    import mensajes_largos
    import resumen_mensaje
    if resumen_mensaje.solicitado(pregunta,estado,historial):
        return True,resumen_mensaje.resumir(estado,ajustes,O.solicitar,avisar=avisar)
    manejado,tramo=mensajes_largos.comando(pregunta,estado)
    if manejado:return True,tramo
    import consultas_equipo,fiabilidad_tecnica
    medido=consultas_equipo.modelos_memoria(pregunta,O)
    if medido is not None:return True,medido
    guia=fiabilidad_tecnica.guia_directa(pregunta,historial)
    if guia is not None:return True,guia
    import memoria_explicita
    manejado,respuesta=memoria_explicita.comando(pregunta,cerebro,confirmar,estado)
    if manejado:return True,respuesta
    import lenguaje_tareas
    tarea_explicita=lenguaje_tareas.interpretar(pregunta,estado) if not estado.get('_entrenamiento_pendiente') else None
    if tarea_explicita and tarea_explicita.nombre=='aclarar':return True,tarea_explicita.respuesta
    acceso_tarea=lenguaje_tareas.acceso(tarea_explicita)
    if acceso_tarea:pregunta=acceso_tarea
    from lenguaje_jarvis import acceso_vocabulario
    entrada_original=pregunta
    traducido=acceso_vocabulario(pregunta,estado)
    if traducido and not ('ollama' in normalizar(entrada_original) and traducido=='/diagnostico'):pregunta=traducido
    if not estado.get('_entrenamiento_pendiente'):
        hecho,texto=_comando_tareas(pregunta.strip(),estado)
        if hecho:return True,texto
    if pregunta.strip().casefold().startswith('/resumir tanda generado'):
        import resumen_documental as RESUMEN
        try:
            partes=shlex.split(pregunta)
            if partes[:3]!=['/resumir','tanda','generado'] or len(partes)>4:
                return True,'Usa /resumir tanda generado [cantidad de trozos, entre 1 y 12].'
            ident=estado.get('_tanda_documentos')
            if not ident:return True,'Primero adjunta e indexa una tanda con /adjuntar y /indexar.'
            cantidad=int(partes[3]) if len(partes)==4 else 12
            if not 1<=cantidad<=12:raise ValueError('La cantidad de trozos debe estar entre 1 y 12.')
            r=RESUMEN.resumir(ident,modelo=ajustes['modelo'],max_trozos=cantidad,progreso=avisar)
            estado['_ultimo_resumen_documental']={k:r[k] for k in ('tipo','cobertura','generacion_completa','cache','fallos','segundos')}
            if not r['ok']:estado['_estado_respuesta']='fallida'
            return True,r['texto']
        except (OSError,ValueError,ConnectionError) as e:return True,'No pude resumir la tanda: '+str(e)
    try:
        manejado,respuesta=TANDAS.comando(pregunta,estado,confirmar,avisar=avisar)
        if manejado:return True,respuesta
    except (OSError,ValueError,ConnectionError) as e:return True,str(e)
    p=pregunta.strip();q=p.casefold(); clave=normalizar(p)
    if clave=='/guia' or clave.startswith('/guia '):
        from guias_contexto_r3 import guia
        return True,guia(p.partition(' ')[2])
    if clave in {'/revisar_fallos','/novedades'}:
        import revision_fallos
        try:return True,revision_fallos.revisar(cerebro) if clave=='/revisar_fallos' else revision_fallos.novedades(cerebro,estado,confirmar)
        except (OSError,ValueError,ConnectionError):return True,'No pude leer esas conversaciones. Comprueba /diagnostico y vuelve a intentarlo.'
    if clave.startswith('/estilo'):
        partes=clave.split()
        if len(partes)!=2 or partes[1] not in {'simple','tecnico'}:return True,'Uso: /estilo simple o /estilo tecnico.'
        if not confirmar('Guardar el estilo '+partes[1]+' para las próximas aperturas?'):return True,'Estilo sin cambios.'
        nuevos=C.guardar(dict(ajustes,modo=partes[1]));ajustes.clear();ajustes.update(nuevos);aplicar_config()
        return True,'Estilo '+partes[1]+' guardado.'
    if clave=='/dudosos':
        import conversaciones_jarvis as CONV
        try:
            filas=[__import__('json').loads(x.read_text()) for x in CONV.COLA.glob('*.json') if not x.is_symlink()]
            dudas=[x for x in filas if x.get('categoria')=='dudosa']
            return True,'Intercambios dudosos conservados solo localmente:\n'+'\n'.join(f'{i}. {x["pregunta"][:180]} · {x["motivo_duda"]}' for i,x in enumerate(dudas,1)) if dudas else 'No hay intercambios dudosos.'
        except (OSError,ValueError) as e:return True,str(e)
    if clave.startswith('/estado_ia'):
        import estado_ia as ESTADO_IA
        try:
            if clave=='/estado_ia local':
                if not confirmar('Regenerar los documentos compactos locales de estado de Jarvis, sin publicar en Segundo Cerebro?'):return True,'Estado local sin cambios.'
                texto=ESTADO_IA.generar()
                return True,'Estado compacto local actualizado: '+str(ESTADO_IA.RESUMEN)+' ('+str(len(texto))+' caracteres). No se publicó.'
            if clave=='/estado_ia ver':return True,ESTADO_IA.RESUMEN.read_text() if ESTADO_IA.RESUMEN.exists() else 'Usa /estado_ia para generar y publicar el resumen.'
            if clave=='/estado_ia iniciar':
                if confirmar('Abrir sesión de mejoras y autorizar que al cerrarla se regenere y publique el resumen fijo de estado de Jarvis?'):
                    estado['_sesion_mejoras']=True;return True,'Sesión abierta. /estado_ia cerrar publica el estado al finalizar; cerrar esta ventana también lo intentará.'
                return True,'Sesión automática sin activar.'
            autorizado=estado.get('_sesion_mejoras') and clave=='/estado_ia cerrar'
            if not autorizado and not confirmar('Regenerar y publicar el resumen fijo de estado en Jarvis, con contenido esperado y lectura posterior?'):
                return True,'Estado sin publicar.'
            r=ESTADO_IA.publicar(cerebro);estado.pop('_sesion_mejoras',None)
            return True,f'{len(r)} documentos publicados y recuperados para verificar. Resumen fijo ID {r[0]["id"]}. No se limpiaron recuerdos.'
        except (OSError,ValueError,ConnectionError) as e:
            cola=' Hay una publicación pendiente en la cola local.' if ESTADO_IA.PENDIENTE.exists() else ' No pude preparar una publicación pendiente.'
            return True,'No pude confirmar la publicación: '+str(e)+'.'+cola+' Reintenta con /estado_ia después de revisar el motivo.'
    if clave=='/limpieza' or clave.startswith('/limpieza '):
        import limpieza_cerebro as LIMPIEZA
        try:
            if clave.startswith('/limpieza aplicar '):
                ids=[int(x) for x in clave[len('/limpieza aplicar '):].split(',')]
                return True,LIMPIEZA.aplicar(ids,cerebro,confirmar)
            return True,LIMPIEZA.presentar(LIMPIEZA.generar(cerebro))
        except (OSError,ValueError,ConnectionError) as e:return True,'No pude completar la propuesta de limpieza: '+str(e)
    if clave=='/vocabulario pendientes':
        try:return True,VOCAB_PENDIENTES.presentar()
        except (OSError,ValueError) as e:return True,str(e)
    if clave=='/perfil':return True,'Perfiles: rapido (1.5B/8192), equilibrado (8B/8192), maximo (8B/16384). /perfil NOMBRE. '+ajustes.get('perfil','equilibrado')+' activo.'
    if clave.startswith('/perfil '):
        nombre=clave.split(maxsplit=1)[1]
        if nombre not in C.PERFILES:return True,'Elige rapido, equilibrado o maximo.'
        try:
            datos=dict(ajustes,**C.PERFILES[nombre],perfil=nombre,seleccion_modelo='manual')
            if datos['modelo'] not in O.modelos():return True,'El modelo de ese perfil no está instalado; no descargué nada.'
            nuevos=C.validar(datos);C.guardar(nuevos);ajustes.clear();ajustes.update(nuevos);aplicar_config()
            return True,f'Perfil {nombre} guardado. Rápido prioriza velocidad; no garantiza la precisión de 8B. /config muestra los límites.'
        except (OSError,ValueError,ConnectionError) as e:return True,str(e)
    if clave.startswith('/ollama_url '):
        url=p.split(maxsplit=1)[1]
        try:
            url=C.validar_url(url)
            import politica_ia
            politica_ia.comprobar_destino_local(ajustes['modelo'],url)
            if not confirmar('Guardar destino de Ollama '+url+' para las próximas aperturas? Los documentos enviados al modelo se procesarán allí.'):
                return True,'Destino sin cambios.'
            nuevos=C.validar(dict(ajustes,ollama_url=url));C.guardar(nuevos);ajustes.clear();ajustes.update(nuevos);O.cambiar_url(url);aplicar_config()
            r=O.diagnostico()
            return True,'Destino guardado. '+('Conexión comprobada.' if r['ok'] else 'No respondió; puedes volver al equipo local con /ollama_url http://127.0.0.1:11434.')
        except (OSError,ValueError,ConnectionError) as e:return True,str(e)
    natural=limpiar(p);n=normalizar(natural)
    visible=normalizar(sin_literales(natural))
    from salud_ollama import queja_conexion
    queja_ollama=queja_conexion(visible)
    conceptual=bool(re.search(r'\b(?:como funciona|que (?:es|significa)|para que (?:sirve|se usa)|guia conceptual|explicame|explica)\b',visible))
    diagnostico_ollama=(not p.startswith('/') and not estado.get('_entrenamiento_pendiente') and (not no_es_peticion(entrada_original) or queja_ollama) and not conceptual and
        (queja_ollama or traducido=='/diagnostico' or ('ollama' in visible and bool(re.search(r'\b(?:funciona|funcionas|funcionando|conectado|conectada|conexion|usas|usando|utilizas|uso|responde|respondiendo|disponible|apagado|detenido|encendido)\b',visible))) or
         bool(re.fullmatch(r'(?:que|cual) (?:es el )?(?:modelo|ia)(?: (?:que )?(?:usas|eres|estas usando|tienes activo|me esta contestando))?',visible.strip(' ¿?¡!.'))) or
         bool(re.search(r'\b(?:usas|usando|funcionando|respondiendo)\b',visible) and re.search(r'\b(?:deepseek|qwen)\b',visible))))
    if diagnostico_ollama:
        fecha=datetime.now(ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M:%S (Chile)')
        d=O.diagnostico()
        from urllib.parse import urlsplit
        local_ollama=urlsplit(O.BASE).hostname in {'127.0.0.1','localhost','::1'}
        texto=(f"Jarvis usa Ollama local, modelo configurado {ajustes['modelo']}. La conexión local no requiere Internet. " if local_ollama else
               f"Jarvis usa el servidor Ollama configurado, modelo {ajustes['modelo']}. La conexión depende del servidor elegido. ")
        texto+=f'Comprobado ahora: {fecha}. '
        if ajustes.get('seleccion_modelo')=='automatico':
            texto+='Selección automática: Qwen para consultas cotidianas y DeepSeek para análisis. '
        else:texto+='La selección está fijada al modelo configurado. '
        if estadisticas and estadisticas.get('modelo'):
            texto+='Última respuesta del motor en esta apertura: '+str(estadisticas['modelo'])+'. '
        if d['ok']:
            texto+='Ollama disponible, versión '+d['version']+'. '
            texto+=('El modelo está instalado.' if ajustes['modelo'] in d['modelos'] else 'El modelo configurado no aparece instalado; usa /modelos.')
        else:texto+='En esta comprobación no pude conectarme. '+d.get('error','Usa /diagnostico.')
        if re.search(r'\bdiferencia\b',visible) and 'qwen' in visible and 'deepseek' in visible:
            texto=('1. En Jarvis, Qwen3:8b atiende consultas breves y DeepSeek R1 8B los análisis y el código. Es una regla del enrutador, no una garantía de calidad. Un modelo ya cargado puede reutilizarse si alcanza para la tarea.\n\n2. Modelo y conexión comprobados:\n'+texto)
        return True,texto+' Esta comprobación no prueba que una respuesta anterior haya terminado bien.'
    if not estado.get('_entrenamiento_pendiente'):
        hecho,texto=RECORDATORIOS.comando(p,estado,confirmar,historial)
        if hecho:return True,texto
    if not p.startswith('/') and not estado.get('_entrenamiento_pendiente') and not diagnostico_ollama and SEGUIMIENTO.es_guia(p):return False,''
    try:
        hecho,texto=CODIGO.comando(p,estado,confirmar)
        if hecho:return True,texto
    except (OSError,ValueError,KeyError,TypeError):return True,'No pude consultar el seguimiento del código. No cambié los archivos del proyecto.'
    if not estado.get('_entrenamiento_pendiente'):
        if q=='/carpetas':
            return True,'Carpeta de trabajo: '+str(TRABAJO)+'\nCarpetas personales autorizadas:\n'+('\n'.join('• '+str(x) for x in ACCESO.listar()) or 'Ninguna adicional.')+'\nUsa rutas completas o ~/Documentos. /autorizar_carpeta RUTA añade una carpeta; /revocar_carpeta RUTA retira el acceso adicional.'
        if q.startswith(('/autorizar_carpeta ','/revocar_carpeta ')):
            try:
                partes=shlex.split(p)
                if len(partes)!=2:raise ValueError('Escribe una sola ruta; usa comillas si contiene espacios.')
                if q.startswith('/autorizar_carpeta '):
                    destino=ACCESO.validar_carpeta(partes[1])
                    if not confirmar(f'Permitir a Jarvis leer y preparar modificaciones en {destino}. Cada escritura seguirá mostrando su propuesta y pidiendo autorización.'):
                        return True,'No añadí ese acceso.'
                    ACCESO.autorizar(destino);return True,f'Carpeta autorizada permanentemente: {destino}. Las rutas relativas siguen apuntando a {TRABAJO}.'
                destino=ACCESO.revocar(partes[1]);return True,f'Retiré el acceso adicional a {destino}. /carpetas muestra los demás accesos; una carpeta padre autorizada puede seguir incluyendo esa ruta.'
            except (ValueError,OSError) as e:return True,str(e)
        clima=CLIMA.interpretar_clima(p)
        if q.startswith('/clima '):clima={'lugar':p[len('/clima '):].strip()}
        if clima:return True,CLIMA.presentar(CLIMA.consultar_clima(**clima))
        if q=='/clima':return True,'Usa /clima Santiago, o «¿Puedes verificar el clima en Santiago mañana?».'
        if q=='/ias':
            modelos=IA.listar_modelos_ia()
            return True,IA.POLITICA.MENSAJE+'\nModelos locales:\n'+('\n'.join('• '+m for m in modelos.get('modelos',[])) if modelos.get('ok') else modelos.get('error','No pude consultar Ollama.'))
        web_natural=WEB.interpretar_busqueda(p)
        if q.startswith('/internet ') or web_natural:
            consulta=p[len('/internet '):].strip() if q.startswith('/internet ') else web_natural
            return True,WEB.presentar(WEB.buscar_web(consulta))
        if q.startswith('/web '):return True,WEB.presentar(WEB.leer_web(p[len('/web '):].strip()))
        if q.startswith('/preguntar_ia '):
            partes=p[len('/preguntar_ia '):].split('|',1)
            if len(partes)!=2:return True,'Uso: /preguntar_ia MODELO | PREGUNTA. /modelos muestra los modelos instalados.'
            r=IA.preguntar_ia(partes[1].strip(),partes[0].strip())
            if r.get('ok'):estado['_ultima_decision_modelo']={'modelo':r['modelo'],'preferido':r['modelo'],'regla':'opinion_local','motivo':'consulta explícita independiente a este modelo local'}
            return True,IA.presentar(r)
        if q=='/ia_externa' or q.startswith('/ia_externa '):
            if not IA.POLITICA.permite_externa():return True,IA.POLITICA.MENSAJE
            texto=p[len('/ia_externa '):].strip();partes=texto.split('|',1)
            return True,IA.presentar(IA.preguntar_externa(partes[-1].strip(),confirmar,perfil=partes[0].strip() if len(partes)==2 else ''))
        if re.fullmatch(r'(?:(?:puedes|podrias|podrías)\s+)?(?:preg[uú]ntale|consulta|consultar)\s+(?:a\s+)?gemini\s+.+',natural,re.I|re.S):
            return True,'Ese proveedor fue retirado. Puedes consultar DeepSeek local o usar /modelos para elegir otro modelo instalado.'
        externa=re.fullmatch(r'(?:(?:puedes|podrias|podrías)\s+)?(?:preg[uú]ntale|preguntarle|pregunta|consulta|consultar|cons[uú]ltale|p[ií]dele)\s+(?:a\s+)?(claude|chatgpt|deepseek(?:\s+local)?|openai|anthropic)\s*[,;:]?\s+(.+)',natural,re.I|re.S)
        if externa:
            if externa[1].casefold().startswith('deepseek'):
                r=IA.preguntar_ia(externa[2],C.MODELO_PREDETERMINADO)
                if r.get('ok'):estado['_ultima_decision_modelo']={'modelo':r['modelo'],'preferido':r['modelo'],'regla':'opinion_local','motivo':'consulta explícita independiente a DeepSeek local'}
                return True,IA.presentar(r)
            if not IA.POLITICA.permite_externa():return True,IA.POLITICA.MENSAJE
            return True,IA.presentar(IA.preguntar_externa(externa[2],confirmar,perfil=externa[1]))
        if q in {'/internet','/web','/preguntar_ia'}:
            return True,'Usa /internet BÚSQUEDA, /web https://URL o /preguntar_ia MODELO | PREGUNTA. /ayuda internet muestra ejemplos locales.'
    definicion=definir_expresion(p)
    if definicion and not estado.get('_entrenamiento_pendiente'):
        return True,definicion
    pide_capacidad=bool(re.fullmatch(r'(?:(?:puedes|podrias|tu puedes|eres capaz de)\s+)?(?:ver|consultar|acceder a|leer|revisar|usar)\s+(?:(?:mi|el|tu|nuestro)\s+)?(?:segundo cerebro|segundocerebro)(?: directamente)?',n))
    pide_capacidad=pide_capacidad or bool(re.fullmatch(r'(?:tienes acceso a|te puedes conectar a|puedes conectarte a)\s+(?:(?:mi|el|tu)\s+)?(?:segundo cerebro|segundocerebro)',n))
    if pide_capacidad and not estado.get('_entrenamiento_pendiente'):
        try:
            actual=cerebro.llamar('consultar_estado_cerebro',{})
            if not actual.get('ok',False):raise ConnectionError(actual.get('error','No respondió el servidor.'))
            return True,('Sí. Puedo consultar tus proyectos, recuerdos y conversaciones mediante las herramientas de Segundo Cerebro. '
                         'También puedo moverlos o corregirlos cuando me lo pidas, mostrando el cambio antes de aplicarlo.\n'
                         f"Conexión comprobada: {ESTRUCTURA._fecha_local(actual.get('consultado',''))}. Usa /proyectos para ver los proyectos o /ultimo_recuerdo para leer el último recuerdo.")
        except ConnectionError:
            return True,'Tengo herramientas para consultar Segundo Cerebro, pero ahora no pude confirmar la conexión. Revisa http://127.0.0.1:8767 o usa /diagnostico.'
    ideas=bool(re.search(r'\b(?:ideas|sugerencias|propuestas|recomendaciones)\b',n) and re.search(r'\b(?:mejorarte|mejorar(?:te)?|reforzar(?:te)?|perfeccionar(?:te)?)\b',n))
    if re.search(r'\bno(?: me)? (?:quiero|des|muestres|pidas) (?:ideas|sugerencias|propuestas|recomendaciones)\b',n):ideas=False
    if clave in {'/entrenamiento estado','como va mi entrenamiento','que hemos entrenado'}:
        try:return True,MEJORAS.informe()
        except ValueError as error:return True,str(error)
    tema_practica=None
    if clave.startswith('/entrenamiento '):
        resto=p.split(' ',1)[1].strip()
        tema_practica='general' if normalizar(resto)=='general' else MEJORAS.tema(resto)
        if not tema_practica:return True,'Elige /entrenamiento python, sql, java, android, ubuntu o general. /entrenamiento estado muestra tus prácticas.'
    elif re.fullmatch(r'(?:entrenemos|entrename|entrenamiento|practiquemos)(?: (?:con|en|sobre))? .+',n):
        tema_practica=MEJORAS.tema(n) or None
    if estado.get('_entrenamiento_pendiente'):
        if q in {'/cancelar','cancelar entrenamiento','cancela entrenamiento'} or re.search(r'\b(?:no (?:quiero )?(?:guardar|guardes|registrar|registres)|prefiero no guardar)\b',n):
            return True,MEJORAS.cancelar(estado)
        if clave in {'/entrenamiento','entrenamiento','entrename','entrenemos','iniciar entrenamiento',
                     'hagamos una sesion de entrenamiento','hagamos un entrenamiento'} or tema_practica:
            return True,'Ya hay una práctica abierta. Respóndeme con el comportamiento que prefieres o escribe /cancelar.'
        if q.startswith('/'):
            return False,''
        item=MEJORAS.proponer(estado,p)
        if item:
            pedido=('Guardar esta preferencia de entrenamiento local para futuras respuestas de Jarvis?\n\n'
                    f"Situación: {item['situacion']}\n\nPreferencia que indicaste:\n{item['preferencia']}\n\n"
                    'Se conserva en un archivo local privado. No cambia los pesos del modelo.')
            if confirmar(pedido):
                try:numero=MEJORAS.registrar(item)
                except (ValueError,OSError) as error:return True,str(error)+' La práctica sigue abierta; puedes cancelar.'
                MEJORAS.cancelar(estado)
                return True,f'Preferencia guardada para futuras respuestas. Entrenamientos registrados: {numero}. Puedes empezar otra práctica con /entrenamiento.'
            MEJORAS.cancelar(estado)
            return True,'No guardé la preferencia. Puedes volver a practicar con /entrenamiento.'
    if ideas or clave in {'/mejoras','mejoras','que puedo mejorar de ti','que cosas puedo mejorar de ti',
             'en que puedes mejorar','como puedes mejorar','dime que necesitas reforzar',
             'que necesitas reforzar','que deberia entrenar'}:
        return True,MEJORAS.sugerir(p,ajustes.get('modelo','')) if ideas else MEJORAS.listar(ajustes.get('modelo',''))
    if clave.startswith('/mejoras '):
        area=p[len('/mejoras '):].strip()
        if MEJORAS.tema(area):return True,MEJORAS.sugerir(area,ajustes.get('modelo',''))
        coincidencias=[x for x in MEJORAS.AREAS if area.casefold() in x[0].casefold()]
        if not coincidencias:
            return True,'No encontré esa área. /mejoras muestra las áreas que puedo revisar.'
        return True,'\n\n'.join(f'{nombre}\nLímite actual: {brecha}\nForma concreta de reforzarla: {como}' for nombre,brecha,como in coincidencias)
    if clave in {'/entrenamiento','entrenamiento','entrename','entrenemos','iniciar entrenamiento',
             'hagamos una sesion de entrenamiento','hagamos un entrenamiento'} or tema_practica:
        try:return True,MEJORAS.iniciar(estado,tema_practica or 'general')
        except ValueError as error:return True,str(error)
    estructura_natural=(
        bool(re.search(r'\b(?:muestrame|mostrar|lista|listar|ensename|dime|quiero ver)\b',clave))
        and bool(re.search(r'\bproyectos?\b',clave))
        and bool(re.search(r'\b(?:estructura|arbol|agrupad|guardad|recuerdos?|conversaciones?|memorias?)\b',clave))
        and not re.search(r'\b(?:ultimo|ultima|mas reciente)\b',clave)
    )
    if clave == '/estructura' or clave.startswith('/estructura ') or estructura_natural or clave in {
            'estructura de proyectos','estructura del segundo cerebro','que cosas tienen guardadas los proyectos',
            'muestrame todo lo guardado en los proyectos','lista lo guardado por proyecto'}:
        filtro=p[len('/estructura'):].strip() if clave.startswith('/estructura ') else ''
        try:
            return True,ESTRUCTURA.texto(ESTRUCTURA.consultar(cerebro,filtro))
        except (ConnectionError,ValueError,TypeError) as e:
            return True,f'No pude consultar la estructura de Segundo Cerebro. Revisa http://127.0.0.1:8767. {e}'
    if q=='/tamano' or q.startswith('/tamano '):
        valor=p[len('/tamano'):].strip()
        if not valor:return True,f"Tamaño de página: {estado.get('_tamano_pagina',ajustes['tamano_pagina'])}. Usa /tamano N, entre 1 y 20."
        try:
            nuevo=C.validar(dict(ajustes,tamano_pagina=int(valor)))
            C.guardar(nuevo);ajustes.clear();ajustes.update(nuevo)
            estado['_tamano_pagina']=nuevo['tamano_pagina']
            for clave in ('_pagina_memorias','_listado_completo','_ultima_pagina_visible','_lista_memorias','_memorias','_origen_listado'):
                estado.pop(clave,None)
            return True,f"Mostraré {nuevo['tamano_pagina']} recuerdos por página también en las próximas aperturas. Abre un listado nuevo."
        except (OSError,ValueError) as e:return True,str(e)
    if q.startswith('/contexto '):
        try:
            partes=q.split()
            if len(partes)!=2:raise ValueError('Usa /contexto N (4096–32768 tokens).')
            nuevos=C.guardar(dict(ajustes,num_ctx=int(partes[1])));ajustes.clear();ajustes.update(nuevos);aplicar_config()
            return True,'Contexto guardado: '+str(ajustes['num_ctx'])+' tokens. La carga debe superar la comprobación de RAM/VRAM; ampliar la ventana no garantiza leer todos los adjuntos.'
        except (OSError,ValueError,IndexError) as e:return True,str(e)
    if q.startswith('/mensaje_completo '):
        import analisis_completo
        return True,analisis_completo.analizar(estado.get('_mensaje_largo',{}),p.split(maxsplit=1)[1],ajustes,O.solicitar)
    if q=='/mensaje_completo':return True,'Usa /mensaje_completo PREGUNTA después de pegar un texto largo. Lo enviará entero, sin herramientas, si cabe en la ventana configurada; no amplía ni recorta automáticamente.'
    if q=='/contexto':
        r=estado_contexto(historial)
        texto=(f"Conversación: {r['turnos_conversacion']} turno(s). El modelo recibe los {r['turnos_modelo']} más recientes que caben.\n"
               f"Turnos anteriores fuera del contexto: {r['turnos_fuera_contexto']}. Siguen en esta conversación para /guardar.\n"
               'Las sesiones guardadas se recuperan explícitamente con /continuar; /nuevo empieza de cero.')
        presupuesto=estado.get('_presupuesto_contexto') or (estadisticas or {}).get('presupuesto_contexto')
        if presupuesto:
            import presupuesto_contexto as P
            texto+='\n\n'+P.presentar(presupuesto)
        texto+='\nVentana configurada: '+str(ajustes['num_ctx'])+' tokens. Procesamiento: '+ajustes.get('modo_gpu','auto')+(' '+str(ajustes.get('capas_gpu',12))+' capas GPU; resto CPU/RAM' if ajustes.get('modo_gpu')=='mixto' else '')+'.'
        return True,texto+ ('\n'+r['aviso'] if r['aviso'] else '')
    natural=limpiar(p);n=normalizar(natural)
    if q=='/hora' or n in {'que hora es','que dia es hoy','que fecha es hoy','fecha y hora','dime la hora'}:
        fecha=datetime.now(ZoneInfo('America/Santiago'))
        return True,f'{fecha:%d/%m/%Y %H:%M:%S} (Chile)'
    calculo=re.fullmatch(r'(?:calcula|calcular|cuanto es|cuanto da)\s+(.+)',natural,re.I)
    if q.startswith('/calcular ') or calculo:
        expresion=p[len('/calcular '):] if q.startswith('/calcular ') else calculo[1]
        if calculo and re.search(r'\b(?:y (?:crea|guarda|escribe|mueve)|despu[eé]s|luego)\b',expresion,re.I):return False,''
        if calculo:
            letras=re.sub(r'\b(?:de|del|raiz|sqrt|abs|redondear)\b','',normalizar(expresion))
            if re.search(r'[a-df-z]',letras):return False,''
        try:return True,CALC.presentar(CALC.calcular(expresion))
        except ValueError as e:return True,str(e)
    aliases_naturales={'revisa las conexiones':'/diagnostico','revisa si funciona jarvis':'/diagnostico','diagnostica jarvis':'/diagnostico',
                      'muestra la configuracion':'/config','como estas configurado':'/config','muestra los modelos':'/modelos',
                      'que modelos tengo':'/modelos','muestra las sesiones':'/sesiones','mis sesiones':'/sesiones',
                      'responde mas breve':'/modo breve','responde mas corto':'/modo breve','responde con mas detalle':'/modo detallado',
                      'responde normal':'/modo normal','cuanto contexto tienes':'/contexto',
                      'sincroniza':'/sincronizar','sincroniza ahora':'/sincronizar','sincroniza los recuerdos':'/sincronizar',
                      'sincroniza mis recuerdos':'/sincronizar','sincroniza el segundo cerebro':'/sincronizar',
                      'sincroniza segundo cerebro':'/sincronizar','sincroniza la memoria':'/sincronizar',
                      'como va la sincronizacion':'/sincronizar estado','estado de la sincronizacion':'/sincronizar estado',
                      'termino la sincronizacion':'/sincronizar estado','ya termino la sincronizacion':'/sincronizar estado'}
    if n in aliases_naturales:
        return comando_local(aliases_naturales[n],historial,estado,confirmar,ajustes,aplicar_config,cerebro,estadisticas,ejecutar)
    if q.split()[:1]==['/sincronizar']:
        partes=q.split()
        if partes[1:]==['estado']:
            r=SYNC.consultar()
            return True,r['texto'] if r['ok'] else r['error']
        if len(partes)>1:return True,'Uso: /sincronizar (inicia una sincronización) o /sincronizar estado.'
        try:
            r=SYNC.sincronizar(confirmar,avisar=lambda texto:print('  '+texto,flush=True))
        except KeyboardInterrupt:
            texto='Dejé de seguir la sincronización. Si ya se solicitó, el ciclo continúa por su cuenta: /sincronizar estado muestra cómo va.'
            comprobante(estado,texto,False)
            return True,texto
        texto=r.get('texto') or r.get('error','No pude sincronizar.')
        comprobante(estado,texto,bool(r.get('ok')))
        return True,texto
    completar=re.fullmatch(r'(?:completa|termina|marca como (?:hecha|hechas|lista|listas|completada|completadas))\s+(?:las?\s+)?tareas?\s+(.+)',natural,re.I)
    reabrir=re.fullmatch(r'(?:reabre|reabrir|vuelve a abrir)\s+(?:las?\s+)?tareas?\s+(.+)',natural,re.I)
    prioridad=re.fullmatch(r'(?:pon|marca|asigna)\s+(?:la\s+)?tarea\s+(\d+|uno|dos|tres|cuatro|cinco)\s+(?:como|con prioridad|en prioridad)\s+(alta|normal|baja|urgente|importante)',n)
    if completar or reabrir:
        p=('/hecho ' if completar else '/reabrir ')+(completar[1] if completar else reabrir[1]);q=p.casefold()
    if prioridad:
        valor={'urgente':'alta','importante':'alta'}.get(prioridad[2],prioridad[2])
        numero=prioridad[1] if prioridad[1].isdigit() else NUMEROS[prioridad[1]]
        p=f'/prioridad {numero} {valor}';q=p.casefold()
    if q.startswith('/exportar_tareas') or q.startswith('/exportar_sesion'):
        try:
            partes=shlex.split(p)
            if partes[0]=='/exportar_tareas' and len(partes)==2:
                texto=T.markdown(T.listar());destino=partes[1]
            elif partes[0]=='/exportar_sesion' and len(partes)==3:
                texto=S.markdown(partes[1]);destino=partes[2]
            else:return True,'Uso: /exportar_tareas RUTA o /exportar_sesion "NOMBRE" RUTA (dentro de la carpeta de trabajo).'
            if ejecutar is None:return True,'No están disponibles las herramientas de escritura para exportar.'
            r=ejecutar('crear_archivo',{'ruta':destino,'contenido':texto})
            return True,f'Exportación guardada y comprobada en {destino}.' if r.get('ok') and r.get('verificado') else r.get('error','No pude comprobar la exportación.')
        except (OSError,ValueError,TypeError) as e:return True,'No pude exportar: '+str(e)
    if n in {'muestra mis tareas','muestrame mis tareas','lista mis tareas','que tareas tengo pendientes','mis pendientes'}:
        q='/tareas'
    tarea=re.fullmatch(r'(?:anota|a[nñ]ade|agrega|crea)\s+(?:una\s+)?tarea\s*:?\s+(.+)',natural,re.I)
    if tarea:
        p='/anotar '+tarea[1];q=p.casefold()
    hecho,texto=_comando_tareas(p,estado)
    if hecho:return True,texto
    if q=='/rendimiento':
        if not estadisticas:return True,'Todavía no hubo una respuesta del modelo en esta apertura.'
        return True,'Última respuesta del modelo:\n'+'\n'.join(f'• {k}: {v}' for k,v in estadisticas.items() if v is not None)
    if q=='/escalar':
        import respaldo_local
        usuarios=[i for i,m in enumerate(historial) if m.get('role')=='user' and not m.get('content','').lstrip().startswith('/')]
        if not usuarios:return True,'Primero haz una pregunta. /escalar pide una segunda respuesta local sin repetir acciones.'
        indice=usuarios[-1]
        if respaldo_local.hubo_herramientas(historial,indice):
            return True,'Ese turno incluyó herramientas. No las repetiré al escalar; formula una pregunta sobre el resultado ya comprobado o usa /preguntar_ia MODELO | PREGUNTA.'
        try:
            actual=estado.get('_ultima_decision_modelo',{}).get('modelo') or (estadisticas or {}).get('modelo') or ajustes['modelo']
            otro=respaldo_local.elegir(actual,O.modelos(),O.BASE)
            pedido=historial[indice].get('content','')
            inicio_escalado=time.monotonic()
            r=IA.preguntar_ia(pedido,otro)
            if r.get('ok'):
                estado['_ultima_decision_modelo']={'modelo':otro,'preferido':otro,'motivo':'escalado explícito del usuario; sin herramientas ni repetición de acciones','regla':'escalado','clase':'compleja'}
                import metricas_modelos
                if not re.search(r'\b(?:no guardes|no guardar|es privado)\b',normalizar(pedido)):
                    metricas_modelos.registrar(estado,estado['_ultima_decision_modelo'],time.monotonic()-inicio_escalado)
            return True,'Segunda respuesta local, sin ejecutar herramientas:\n'+IA.presentar(r)
        except (OSError,ValueError) as e:return True,'No pude escalar la respuesta: '+str(e)
    if q=='/gpu':
        return True,'Uso de GPU guardado: '+ajustes.get('modo_gpu','auto')+(' '+str(ajustes.get('capas_gpu',12))+' capas GPU' if ajustes.get('modo_gpu')=='mixto' else '')+'. /gpu mixto N reparte capas entre GPU y RAM. /gpu cpu procesa próximos turnos con CPU (más lento); /gpu auto permite aceleración. /liberar descarga los modelos que ya estén cargados.'
    if q.startswith('/gpu '):
        try:
            partes=q.split();valor=partes[1]
            if valor=='mixto':
                if len(partes)!=3:raise ValueError('Usa /gpu mixto N (capas GPU); /gpu auto o /gpu cpu.')
                capas=int(partes[2])
                info=O.solicitar('/api/show',{'model':ajustes['modelo']})
                meta=info.get('model_info',{});bloques=meta.get(meta.get('general.architecture','')+'.block_count')
                if type(bloques) is not int or not 1<=capas<=bloques+1:raise ValueError('Cantidad de capas no válida para el modelo instalado.')
            else:
                if len(partes)!=2:raise ValueError('Usa /gpu auto, /gpu cpu o /gpu mixto N.')
                capas=ajustes.get('capas_gpu',12)
            nuevos=C.guardar(dict(ajustes,modo_gpu=valor,capas_gpu=capas));ajustes.clear();ajustes.update(nuevos);aplicar_config()
            return True,'Modo '+valor+(' '+str(capas)+' capas GPU, resto CPU/RAM' if valor=='mixto' else '')+' guardado para las próximas inferencias. '+('Los modelos usan CPU y RAM; pueden responder más lento. Antes de jugar usa /liberar para descargar cualquier copia GPU anterior.' if valor=='cpu' else 'Ollama puede volver a usar GPU; /diagnostico comprueba la carga real.')
        except (OSError,ValueError) as e:return True,str(e)
    if q=='/liberar':
        import recursos_ollama
        try:return True,recursos_ollama.liberar(O,ajustes,confirmar)
        except (OSError,ValueError) as e:return True,'No pude comprobar la descarga de memoria: '+str(e)
    if q=='/reposo':
        return True,'Reposo actual: '+ajustes['keep_alive']+'. /reposo 0|1m|5m|10m|30m|60m guarda el plazo tras cada respuesta. 0 descarga al terminar; /liberar actúa ahora.'
    if q.startswith('/reposo '):
        try:
            nuevos=C.guardar(dict(ajustes,keep_alive=p.split(maxsplit=1)[1].strip()))
            ajustes.clear();ajustes.update(nuevos);aplicar_config()
            return True,'Reposo guardado: '+ajustes['keep_alive']+'. Se aplicará desde la próxima inferencia; /liberar descarga los modelos cargados ahora.'
        except (OSError,ValueError) as e:return True,str(e)
    if q=='/timeout auto':
        try:
            nuevos=C.guardar(dict(ajustes,timeout_auto=True));ajustes.clear();ajustes.update(nuevos);aplicar_config()
            return True,'Espera automática guardada: se amplía para DeepSeek, textos largos y código, hasta 600 segundos. /timeout SEGUNDOS fija un límite manual.'
        except (OSError,ValueError) as e:return True,str(e)
    if q=='/config':
        return True, '\n'.join(['Configuración actual:']+[f'• {k}: {v}' for k,v in ajustes.items()])+ '\n/modo breve|normal|detallado · /modelo automatico|NOMBRE · /timeout SEGUNDOS'
    if q=='/modelo':
        texto='Selección: '+C.etiqueta_modelo(ajustes)+'. Modelo configurado: '+ajustes['modelo']+'.'
        import externo_zen
        zen=externo_zen.estado()
        texto+=' Niveles: rápido qwen3:8b; razonamiento jarvis-deepseek:8b; Zen '+('encendido' if zen['encendido'] else 'apagado')+' (solo genérico y modelos permitidos).'
        if zen.get('ultimo_error'):texto+=' Último intento Zen: '+zen['ultimo_error'][:400]
        if estadisticas and estadisticas.get('modelo'):texto+=' Última inferencia: '+str(estadisticas['modelo'])+'.'
        from enrutador_modelos import presentar_decision
        return True,texto+' /modelo NOMBRE guarda una selección; /modelo automatico permite alternar por tarea.\n'+presentar_decision(estado.get('_ultima_decision_modelo'))
    if q=='/modelos':
        try:
            nombres=O.modelos()
            return True,'Modelos instalados:\n'+'\n'.join('• '+n for n in nombres)
        except ConnectionError as e:return True,str(e)
    if q in {'/modelo auto','/modelo automatico','/modelo automático'}:
        try:
            instalados=O.modelos()
            if not {C.MODELO_PREDETERMINADO,C.MODELO_COTIDIANO}.intersection(instalados):
                return True,'No están instalados los modelos del modo automático. Usa /modelos. No descargué nada.'
            nuevos=C.guardar(dict(ajustes,seleccion_modelo='automatico'))
            ajustes.clear();ajustes.update(nuevos);aplicar_config()
            from enrutador_modelos import presentar_decision
            return True,'Selección automática guardada: Qwen para saludos/consultas simples; DeepSeek para análisis, código y adjuntos. Si falta uno, uso el otro instalado. /modelo NOMBRE vuelve a manual.\n'+presentar_decision(estado.get('_ultima_decision_modelo'))
        except (ValueError,OSError,ConnectionError) as e:return True,str(e)
    for acceso,clave in [('/modo','modo'),('/modelo','modelo'),('/timeout','timeout_modelo')]:
        if q.startswith(acceso+' '):
            valor=p[len(acceso):].strip()
            try:
                if clave=='timeout_modelo':valor=int(valor)
                if clave=='modelo' and valor not in O.modelos():return True,'Ese modelo no está instalado. /modelos muestra los disponibles. No descargué nada.'
                cambios={clave:valor}
                if clave=='modelo':cambios['seleccion_modelo']='manual'
                if clave=='timeout_modelo':cambios['timeout_auto']=False
                nuevos=C.validar(dict(ajustes,**cambios))
                C.guardar(nuevos);ajustes.clear();ajustes.update(nuevos);aplicar_config()
                texto=f'{clave}: {valor}. Ajuste guardado para las próximas aperturas.'
                comprobante(estado,texto,True)
                return True,texto
            except (ValueError,OSError,ConnectionError) as e:return True,str(e)
    if q=='/sesiones':
        try:
            sesiones=S.listar()
            return True,'Sesiones guardadas:\n'+'\n'.join(f"• {s['nombre']} ({s['mensajes']} mensajes)" for s in sesiones) if sesiones else 'Todavía no hay sesiones guardadas. /guardar NOMBRE guarda esta conversación.'
        except OSError:return True,'No pude leer la carpeta de sesiones.'
    if q.startswith('/guardar '):
        nombre=p[len('/guardar '):].strip()
        try:
            ruta=S.ruta_sesion(nombre)
            pedido=f'Guardar esta conversación como «{nombre}». Incluye los mensajes y resultados consultados en un archivo local privado.'
            if ruta.exists():pedido+=' Se reemplazará la sesión anterior con ese nombre.'
            if not confirmar(pedido):
                comprobante(estado,'No guardé la sesión: no autorizaste la escritura.',False)
                return True,'No guardé la sesión.'
            r=S.guardar(nombre,historial,estado)
            texto=f"Sesión «{nombre}» guardada: {r['mensajes']} mensajes. Usa /continuar {nombre} para retomarla."
            comprobante(estado,texto,True)
            return True,texto
        except (OSError,ValueError,TypeError) as e:return True,'No pude guardar la sesión: '+str(e)
    if q=='/continuar':
        import hilo_conversacion as H
        try:
            nuevo={};H.recuperar(nuevo)
            if historial[1:] and not confirmar('Retomar el último hilo local y cerrar la vista actual. No se recuperarán permisos ni propuestas ejecutables. ¿Cambiar de conversación?'):
                return True,'Seguí en la conversación actual.'
            sistema=historial[0].get('content','') if historial else ''
            historial[:]=[{'role':'system','content':sistema}]
            estado.clear();estado.update(nuevo)
            return True,'Hilo local recuperado. Conservé el objetivo, las decisiones y la referencia de los adjuntos; los permisos y consultas de archivos o recuerdos deben comprobarse otra vez.'
        except (OSError,ValueError,TypeError) as e:return True,'No pude recuperar el hilo local: '+str(e)
    if q.startswith('/continuar '):
        nombre=p[len('/continuar '):].strip()
        try:
            mensajes,prefs=S.cargar(nombre)
            if historial[1:] and not confirmar(f'Cambiar a la sesión «{nombre}». La conversación actual se cerrará; guárdala primero si la necesitas.'):
                return True,'Seguí en la conversación actual.'
            historial[:]=[{'role':'system','content':historial[0]['content']}]+mensajes
            estado.clear();estado.update(prefs)
            return True,f'Sesión «{nombre}» recuperada. Las referencias a recuerdos y cambios deben consultarse de nuevo antes de modificarlas.'
        except (OSError,ValueError,TypeError) as e:return True,'No pude recuperar la sesión: '+str(e)
    if q=='/diagnostico':
        datos=O.diagnostico()
        fecha=datetime.now(ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M:%S (Chile)')
        lineas=['Comprobación de Jarvis: '+fecha, 'Lecturas realizadas ahora: conexión. Los sensores pueden reutilizar lecturas de hasta 4 segundos.']
        lineas.append('• Ollama: '+('disponible, versión '+datos['version'] if datos['ok'] else 'sin conexión. Los accesos directos siguen disponibles.'))
        if not datos['ok'] and datos.get('error'):lineas.append('• Motivo de la comprobación: '+datos['error'])
        if datos['ok']:lineas.append('• Modelo configurado: '+('instalado' if ajustes['modelo'] in datos['modelos'] else 'no está instalado; usa /modelos'))
        try:
            if cerebro is None:raise ConnectionError('Sin cliente de memoria en este contexto.')
            r=cerebro.llamar('consultar_estado_cerebro',{})
            lineas.append('• Segundo Cerebro: '+('disponible' if r.get('ok') else 'no se pudo consultar; revisa http://127.0.0.1:8767'))
        except ConnectionError:lineas.append('• Segundo Cerebro: sin conexión; revisa http://127.0.0.1:8767')
        lineas.append('• Carpeta de trabajo: '+str(TRABAJO))
        try:lineas.append(f'• Espacio libre: {shutil.disk_usage(PROYECTO).free//(1024**3)} GB')
        except OSError:lineas.append('• Espacio libre: no disponible')
        lineas.append('• Configuración: '+C.leer()[1] if C.leer()[1] else '• Configuración: válida')
        import recursos_ollama
        lineas.extend(recursos_ollama.lineas_diagnostico(O,ajustes))
        import control_recursos
        lineas.extend(control_recursos.diagnostico_termico())
        return True,'\n'.join(lineas)
    if q in {'/guardar','/continuar','/modo','/modelo','/timeout','/anotar','/editar_tarea','/prioridad','/buscar_tareas','/hecho','/reabrir','/calcular'}:
        return True,'Añade un valor después del acceso. /ayuda muestra ejemplos.'
    return False,''


def _comando_tareas(p,estado):
    """Despacha accesos de tareas sin interpretar su contenido como otra orden."""
    q=p.casefold()
    if q in {'/tareas','/pendientes','/tareas todas'} or q.startswith('/buscar_tareas '):
        try:
            tareas=T.listar()
            visibles=T.filtrar(p[len('/buscar_tareas '):].strip(),tareas) if q.startswith('/buscar_tareas ') else tareas if q=='/tareas todas' else [t for t in tareas if not t['hecha']]
            visibles=sorted(visibles,key=lambda t:{'alta':0,'normal':1,'baja':2}[t.get('prioridad','normal')])
            estado['_tareas_visibles']={n:t['id'] for n,t in enumerate(visibles,1)}
            estado['_tipo_ultimo_listado']='tareas'
            return True,'\n'.join(f"{n}. {'✓' if t['hecha'] else '○'} {t['texto']} · {t.get('prioridad','normal')}" for n,t in enumerate(visibles,1)) if visibles else 'No encontré tareas con ese texto.' if q.startswith('/buscar_tareas ') else 'No hay tareas pendientes.'
        except (OSError,ValueError) as e:return True,str(e)
    if q.startswith('/anotar '):
        try:
            import hilo_conversacion as HILO
            HILO.marcar_accion(estado,'anotar_tarea')
            t=T.anotar(p[len('/anotar '):])
            estado.pop('_tareas_visibles',None)
            texto='Tarea añadida: '+t['texto']+'. /tareas muestra la lista.'
            comprobante(estado,texto,True)
            return True,texto
        except (OSError,ValueError) as e:return True,'No pude añadir la tarea: '+str(e)
    for acceso,hecha in [('/hecho',True),('/reabrir',False)]:
        if q.startswith(acceso+' '):
            try:
                mapa=estado.get('_tareas_visibles',{})
                numeros=seleccion(p[len(acceso):].strip(),{'_lista_memorias':mapa})
                if not numeros or any(numero not in mapa for numero in numeros):return True,'Primero usa /tareas (o /tareas todas) y elige los números mostrados.'
                import hilo_conversacion as HILO
                HILO.marcar_accion(estado,'cambiar_estado_tarea')
                tareas=[T.marcar(mapa[numeros[0]],hecha)] if len(numeros)==1 else T.marcar_varias([mapa[numero] for numero in numeros],hecha)
                texto=('Tarea completada: ' if hecha else 'Tarea reabierta: ')+', '.join(t['texto'] for t in tareas)
                comprobante(estado,texto,True)
                return True,texto
            except (OSError,ValueError) as e:return True,'No pude cambiar la tarea: '+str(e)
    for acceso in ('/editar_tarea','/prioridad'):
        if q.startswith(acceso+' '):
            try:
                partes=p[len(acceso):].strip().split(maxsplit=1)
                if len(partes)!=2:return True,f'Uso: {acceso} N '+('TEXTO' if acceso=='/editar_tarea' else 'alta|normal|baja')
                numero=int(partes[0]);ident=estado.get('_tareas_visibles',{}).get(numero)
                if ident is None:return True,'Primero usa /tareas y elige un número mostrado.'
                import hilo_conversacion as HILO
                HILO.marcar_accion(estado,'editar_tarea')
                t=T.editar(ident,partes[1]) if acceso=='/editar_tarea' else T.priorizar(ident,normalizar(partes[1]))
                texto='Tarea actualizada: '+t['texto']+' · prioridad '+t.get('prioridad','normal')
                comprobante(estado,texto,True)
                return True,texto
            except (OSError,ValueError) as e:return True,'No pude cambiar la tarea: '+str(e)
    return False,''


def comprobante(estado,texto,ok):
    estado['_ultima_accion']={'fecha':datetime.now(ZoneInfo('America/Santiago')).strftime('%d/%m/%Y %H:%M:%S (Chile)'),
                              'detalle':texto,'ok':ok}
