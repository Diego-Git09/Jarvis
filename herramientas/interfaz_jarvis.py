"""Accesos directos de terminal con respuestas basadas en resultados reales."""

import re
import unicodedata
from lenguaje_jarvis import interpretar
from interfaz_archivos import comando_archivos
from ayuda_jarvis import GENERAL as AYUDA, ayuda
from accesos_jarvis import normalizar_acceso, sugerir




def renderizar(nombre, r):
    if nombre == 'clasificar_recuerdos':
        lineas = [f"{m['numero']}. {m.get('titulo', '')}: {'movido' if m['estado']=='clasificado' else 'ya pertenecía'} al proyecto {r.get('proyecto', '')}." for m in r.get('resultados', [])]
        if not r.get('ok'):
            lineas.append(r.get('error', 'No pude completar la selección.'))
        elif r.get('nota'):
            lineas.append(r['nota'])
        return '\n'.join(lineas)
    if not r.get('ok'):
        from errores_usuario import presentar
        return presentar(r.get('error', 'No pude completar la consulta.'))
    if nombre == 'ver_recuerdo':
        m = r['recuerdo']
        fuente = f"\nIA de origen: {m['fuente']}" if m.get('fuente') else ''
        contenido = m.get('contenido', '').split('\n\nOrigen automático:', 1)[0]
        return f"{m['numero_lista']}. {m.get('titulo', 'Sin título')}\nProyecto: {m.get('proyecto', '')}\nFecha de guardado: {m.get('creado', 'no disponible')}{fuente}\nContenido completo:\n{contenido}"
    if nombre in {'consultar_ultimo_recuerdo', 'consultar_ultima_conversacion'}:
        m = r.get('registro', {})
        encabezado = 'Última conversación guardada' if nombre == 'consultar_ultima_conversacion' else 'Último recuerdo guardado'
        lineas = [f"{encabezado}: {m.get('titulo', 'Sin título')}",
                  f"Proyecto: {m.get('proyecto', 'sin_clasificar')}",
                  f"Fecha de guardado: {m.get('creado', 'no disponible')}"]
        if m.get('tipo'):
            lineas.append(f"Tipo de registro: {'transcripción' if m['tipo'] == 'conversacion' else 'recuerdo'}.")
        if m.get('fuente'):
            lineas.append(f"IA de origen: {m['fuente']}.")
        cuerpo = m.get('contenido', '').split('\n\nOrigen automático:', 1)[0].strip()
        if cuerpo:
            lineas.extend(['Contenido:', cuerpo])
        if r.get('registro', {}).get('recortado'):
            lineas.append('El contenido es extenso. Usa /ver 1 para consultarlo completo; el registro quedó seleccionado para poder moverlo.')
        elif m.get('tipo') == 'conversacion':
            lineas.append('La conversación quedó seleccionada; puedes pedirme que la mueva explícitamente a otro proyecto.')
        else:
            lineas.append('El recuerdo quedó seleccionado; puedes pedirme que lo mueva o corrija.')
        return '\n'.join(lineas)
    if nombre == 'crear_proyecto':
        return f"Proyecto «{r.get('proyecto', '')}»: {'creado' if r.get('estado') == 'creado' else 'ya existía'}."
    if nombre == 'listar_proyectos':
        items = r.get('proyectos', [])
        return 'Proyectos:\n' + '\n'.join(
            f"• {p['proyecto']}: {p.get('recuerdos', p.get('total','sin dato'))} recuerdo(s) · {p.get('conversaciones', 0)} conversación(es)"
            for p in items) if items else 'No hay proyectos registrados.'
    if nombre in {'listar_memorias','buscar_memoria','buscar_memoria_semantica'}:
        items = r.get('memorias', [])
        if not items:
            return 'No hay recuerdos en esta página.'
        texto = []
        for m in items:
            contenido = m.get('contenido', '').split('\n\nOrigen automático:', 1)[0].strip()
            origen = f"\n   Tipo: {'transcripción' if m.get('tipo') == 'conversacion' else 'recuerdo'}" if m.get('tipo') else ''
            if m.get('fuente'):
                origen += f" · IA: {m['fuente']}"
            fragmento = f"\n   Fragmento coincidente: {m['fragmento']}" if m.get('fragmento') else ''
            texto.append(f"{m['numero_lista']}. {m.get('titulo', 'Sin título')}\n   Proyecto: {m.get('proyecto', '')}\n   Fecha de guardado: {m.get('creado', 'no disponible')}{origen}\n   {contenido}{fragmento}")
        if r.get('recortado') and any(len(m.get('contenido', '')) >= 1600 for m in items):
            texto.append('Contenido abreviado. Usa /ver N para consultar el recuerdo completo.')
        if r.get('total_disponibles') is not None:
            tamano = r.get('tamano_pagina', 5)
            total_paginas = max(1, (r['total_disponibles']+tamano-1)//tamano)
            texto.append(f"Página {r.get('desplazamiento', 0)//tamano+1} de {total_paginas} · {r['total_disponibles']} recuerdo(s) en este listado.")
        final = ('Escribe /mas para ver los siguientes.' if r.get('siguiente_desplazamiento') is not None else 'Fin del listado.')
        encabezado = f"Recuerdos del proyecto {r['proyecto_filtro']}:\n\n" if r.get('proyecto_filtro') else ''
        if r.get('consulta_busqueda'):
            encabezado += f"Resultados para «{r['consulta_busqueda']}»:\n\n"
        elif nombre == 'listar_memorias':
            encabezado += "Orden: " + ("del más antiguo al más nuevo" if r.get('orden') == 'antiguos' else "del más nuevo al más antiguo") + "\n\n"
        return encabezado + '\n\n'.join(texto) + '\n\n' + final
    if nombre == 'consultar_estado_cerebro':
        lineas = [f"Consultado: {r.get('consultado', 'fecha no disponible')}", f"Recuerdos guardados: {r.get('memorias', '?')}"]
        for f in r.get('fuentes', []):
            reciente = 'lectura reciente' if f.get('lectura_reciente') else 'lectura sin confirmar como reciente'
            lineas.append(f"• {f['fuente']}: {f.get('estado', '?')}, {f.get('pendientes', '?')} pendiente(s), {reciente}.")
            if f.get('error'):
                lineas.append(f"  Error: {f['error']}")
        lineas.append(f"Panel: {r.get('panel', 'http://127.0.0.1:8767')}")
        return '\n'.join(lineas)
    return ''


def comando(pregunta, historial, estado, ejecutar, sistema, local=None, confirmar_plan=None):
    """Un despacho compartido por GUI y terminal, con hilo antes del modelo.

    Las traducciones y órdenes compuestas reutilizan el despacho interno; no
    aceptan una propuesta varias veces ni otorgan permisos a partir del hilo.
    """
    estado.pop('_solo_lectura_fuentes',None)
    if not estado.get('_profundidad_hilo'):
        estado.pop('_estado_respuesta',None)
    import administracion_local
    if administracion_local.es_entrada(pregunta,estado) and local is not None:
        estado.pop('_metricas_ultimo',None)
        manejado,texto=local(pregunta,historial,estado)
        if manejado:return True,texto
    else:
        estado.pop('_revision_respuestas',None);estado.pop('_confirmacion_vocabulario',None)
    import metricas_modelos
    metricas_modelos.entrada(pregunta,estado)
    import hilo_conversacion as H
    from normalizacion_entrada import analizar,aclaracion
    entrada=analizar(pregunta)
    from comprension_peticion import solo_datos_pegados
    import resumen_mensaje
    if local is not None and resumen_mensaje.solicitado(pregunta,estado,historial):
        manejado,texto=local(pregunta,historial,estado)
        if manejado:
            historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
            return True,texto
    import referencias_adjuntas
    adjunta=referencias_adjuntas.atender(pregunta,estado)
    if adjunta is not None:
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':adjunta}])
        return True,adjunta
    import peticiones_controladas
    controlada=peticiones_controladas.atender(pregunta,estado,ejecutar)
    if controlada is not None:
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':controlada}])
        return True,controlada
    if solo_datos_pegados(pregunta):return False,''
    incompleta=re.fullmatch(r'(?:(?:puedes|podrias|quiero|necesito)(?: que)?\s+)?(borra|borrar|elimina|eliminar|copia|copiar|mueve|mover|renombra|renombrar|edita|editar|modifica|modificar|guarda|guardar|olvida|olvidar)',entrada.vista.strip(' ¿?¡!.'))
    if incompleta:
        texto='Entendí que quieres '+incompleta[1]+', pero falta el objeto exacto. ¿Es así?\n1. Un archivo: indica su ruta y destino si corresponde.\n2. Un recuerdo o conversación: indica cuál del listado.\nEscribe la petición completa con el objeto elegido; todavía no preparé cambios.'
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}]);return True,texto
    if not pregunta.lstrip().startswith('/') and entrada.dudas:
        texto=aclaracion(entrada)
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
        return True,texto
    if confirmar_plan is not None:
        import ordenes_compuestas as ORDENES
        import planes_archivos as PLANES
        # Un recuerdo etiquetado puede contener separadores como datos.
        import memoria_explicita
        try:partes=[] if memoria_explicita.INICIO.match(pregunta) or pregunta.lstrip().casefold().startswith('/nuevo ') else ORDENES.separar(pregunta)
        except ValueError as e:return True,str(e)
        if partes and all(re.match(r'(?i)^\s*(?:explica|expl[ií]came|compara|resume|recomienda|dime|qu[eé]|c[oó]mo|cu[aá]nto)\b',p) for p in partes):
            estado['_consultas_compuestas']=partes
            return False,''
        if not memoria_explicita.INICIO.match(pregunta) and (partes or pregunta.strip().casefold()=='/deshacer_plan'):
            texto=PLANES.ejecutar(partes,ejecutar,confirmar_plan,estado) if partes else PLANES.deshacer(ejecutar,confirmar_plan,estado)
            historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
            H.terminar_turno(estado,pregunta,texto,hubo_acciones=bool(estado.get('_ultimo_plan_archivos',{}).get('cambios')))
            return True,texto
    profundidad=estado.get('_profundidad_hilo',0)
    if profundidad:return _comando(pregunta,historial,estado,ejecutar,sistema,local)
    nuevo=re.match(r'(?is)^\s*/nuevo\s+(\S.*)$',pregunta)
    if nuevo:
        restante=nuevo[1].strip()
        _comando('/nuevo',historial,estado,ejecutar,sistema,local)
        manejado,texto=comando(restante,historial,estado,ejecutar,sistema,local,confirmar_plan=confirmar_plan)
        if not manejado:
            estado['_entrada_tras_nuevo']={'original':pregunta,'pedido':restante}
        return manejado,texto
    if pregunta.strip().casefold() in {'/nuevo','/continuar'} or pregunta.strip().casefold().startswith('/continuar '):
        # No actualizar ultimo.json antes de leer el hilo que se quiere retomar.
        return _comando(pregunta,historial,estado,ejecutar,sistema,local)
    if len(pregunta)>12000:
        from decision_contexto import mensaje_largo
        candidato,_=mensaje_largo(pregunta,historial,estado)
        if candidato:return False,''
        import mensajes_largos
        texto=mensajes_largos.preparar(pregunta,estado)
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
        return True,texto
    import formato_literales
    literal=formato_literales.respuesta_condicional(pregunta,estado)
    if literal is not None:
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':literal}])
        estado['_respuesta_sin_modelo']='contrato_literal_explicito'
        return True,literal
    resolucion=H.iniciar_turno(estado,pregunta,historial)
    estado['_resolucion_hilo']=resolucion
    propuesta=estado.get('_hilo_conversacion',{}).get('propuesta')
    intencion=interpretar(pregunta,estado)
    import lenguaje_recordatorios as RECORDATORIOS_NLP
    import lenguaje_tareas as TAREAS_NLP
    import memoria_explicita
    paginas={'/mas','/anterior','/pagina'}
    local_explicita=bool((intencion and intencion.nombre not in paginas) or RECORDATORIOS_NLP.interpretar(pregunta) or (not estado.get('_entrenamiento_pendiente') and TAREAS_NLP.interpretar(pregunta,estado)) or memoria_explicita.INICIO.match(pregunta))
    # Mantiene las referencias del listado visible. Una propuesta de trabajo
    # vigente tiene prioridad sobre un listado viejo que haya quedado en caché.
    listado=bool(not propuesta and estado.get('_lista_memorias') and intencion and
                 (intencion.nombre in {'ver_recuerdo','clasificar_recuerdos','/mas','/anterior','/pagina'}))
    from lenguaje_jarvis import normalizar,limpiar
    documental=bool(estado.get('_documento_tramo') and normalizar(limpiar(pregunta)).strip(' ¿?¡!.') in {
        'continua leyendo','sigue leyendo','lee la siguiente pagina','muestra la siguiente pagina','siguiente parte del documento'})
    if resolucion['aclaracion'] and not listado and not documental and not local_explicita:
        from vocabulario_pendientes import aclarar
        texto=aclarar(pregunta,resolucion['aclaracion'],explicita=True)
        historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
        H.terminar_turno(estado,pregunta,texto);estado.pop('_resolucion_hilo',None)
        return True,texto
    if not pregunta.lstrip().startswith('/') and not listado and not documental and not local_explicita and (resolucion['continuacion'] or resolucion['reintento']):
        return False,''
    nombres=[]
    def controlado(nombre,args):
        nombres.append(nombre)
        return ejecutar(nombre,args)
    estado['_profundidad_hilo']=1
    try:
        manejado,texto=_comando(pregunta,historial,estado,controlado,sistema,local)
        if manejado:
            if pregunta.strip().casefold()!='/nuevo' and not pregunta.strip().casefold().startswith('/continuar'):
                if (intencion is not None and intencion.nombre=='aclarar') or re.match(r'¿(?:Qué (?:hora|día|fecha|título|texto|números?|prioridad|recordatorio)|A qué)',texto):
                    from vocabulario_pendientes import aclarar
                    texto=aclarar(pregunta,texto,explicita=True)
                H.terminar_turno(estado,pregunta,texto,fallido=texto.startswith(('No pude','Consulta interrumpida')),
                    hubo_acciones=bool(nombres))
            estado.pop('_resolucion_hilo',None)
        return manejado,texto
    except BaseException:
        H.terminar_turno(estado,pregunta,'Se interrumpió el despacho; comprueba las acciones antes de repetir.',fallido=True,hubo_acciones=True)
        estado.pop('_resolucion_hilo',None)
        raise
    finally:estado.pop('_profundidad_hilo',None)


def _comando(pregunta, historial, estado, ejecutar, sistema, local=None):
    """(manejado, respuesta). Las selecciones explícitas pasan por la autorización normal."""
    import memoria_explicita
    if local is not None and memoria_explicita.INICIO.match(pregunta):
        # El contenido etiquetado puede contener «y luego», rutas o accesos:
        # son texto del recuerdo, nunca otra orden encadenada.
        manejado,texto=local(pregunta,historial,estado)
        if manejado:
            historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
            return True,texto
    import ordenes_compuestas as ORDENES
    try:partes=ORDENES.separar(pregunta)
    except ValueError as e:return True,str(e)
    if partes:
        anterior=None
        def paso(texto):
            nonlocal anterior
            try:texto=ORDENES.referencia_archivo(texto,anterior)
            except ValueError as e:return True,str(e),False
            resultados=[];comprobante=estado.get('_ultima_accion')
            def registrar(nombre,args):
                r=ejecutar(nombre,args);resultados.append((nombre,args,r));return r
            hecho,respuesta=comando(texto,historial,estado,registrar,sistema,local)
            comprobado=None
            if resultados:
                escrituras={'copiar_archivo','mover_archivo','crear_archivo','crear_carpeta','aplicar_edicion','reemplazar_texto','revertir_cambio'}
                comprobado=all(r.get('ok') and (nombre not in escrituras or r.get('verificado')) and nombre!='proponer_edicion' for nombre,args,r in resultados)
                ultimo_nombre,ultimo_args,_=resultados[-1]
                anterior=ultimo_args['destino'] if comprobado and ultimo_nombre in {'copiar_archivo','mover_archivo'} else None
            elif estado.get('_ultima_accion') is not comprobante and isinstance(estado.get('_ultima_accion'),dict):
                comprobado=bool(estado['_ultima_accion'].get('ok'));anterior=None
            else:anterior=None
            return hecho,respuesta,comprobado
        return True,ORDENES.ejecutar(partes,paso)
    pregunta=normalizar_acceso(pregunta)
    import interfaz_documentos as DOCUMENTOS
    manejado,texto=DOCUMENTOS.comando(pregunta,historial,estado,ejecutar)
    if manejado:return True,texto
    if pregunta.strip().casefold()=='/codigo continuar':return False,''
    if local is not None:
        manejado,texto = local(pregunta,historial,estado)
        if manejado:
            if pregunta.strip().casefold()!='/continuar' and not pregunta.strip().casefold().startswith('/continuar '):
                historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
            return True,texto
    manejado,texto = comando_archivos(pregunta,historial,estado,ejecutar)
    if manejado:
        return True,texto
    intencion = interpretar(pregunta, estado)
    if intencion is not None:
        if intencion.nombre == 'aclarar':
            texto = intencion.respuesta
            historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
            return True, texto
        if intencion.nombre == '/salir':
            return True, 'Escribe /salir para cerrar Jarvis.'
        if intencion.nombre.startswith('/'):
            acceso = intencion.nombre + (" " + intencion.argumentos["proyecto"] if intencion.nombre == '/proyecto' else " " + str(intencion.argumentos["pagina"]) if intencion.nombre == '/pagina' else " " + str(intencion.argumentos["tamano"]) if intencion.nombre == '/tamano' else "")
            return comando(acceso, historial, estado, ejecutar, sistema, local=local)
        resultado = ejecutar(intencion.nombre, intencion.argumentos)
        texto = renderizar(intencion.nombre, resultado)
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    q = pregunta.strip().casefold()
    aliases = {'ayuda':'/ayuda', 'proyectos':'/proyectos', 'recuerdos':'/recuerdos',
               'más':'/mas', '/más':'/mas', 'estado':'/estado'}
    q = aliases.get(q, q)
    normal = ''.join(c for c in unicodedata.normalize('NFD', q) if unicodedata.category(c) != 'Mn').strip(' ¿?¡!.')
    filtro = None
    orden = None
    pedido_orden = re.fullmatch(r'(?:muestrame |lista )?(?:los |mis )?recuerdos(?: (sin clasificar))? ordenados del mas (antiguo al mas nuevo|nuevo al mas antiguo)(?: \(por fecha\))?', normal)
    if pedido_orden:
        q = '/recuerdos'
        filtro = 'sin_clasificar' if pedido_orden.group(1) else None
        orden = 'antiguos' if pedido_orden.group(2).startswith('antiguo') else 'recientes'
    fechas = normal in {'me los puedes listar con la fecha y hora', 'me los puedes mostrar con la fecha y hora',
                        'muestralos con fecha y hora', 'muestrame los recuerdos con fecha y hora',
                        'muestrame los recuerdos con la fecha y hora', 'con fecha y hora', 'con la fecha y hora'}
    if fechas or normal in {'no me mostraste los recuerdos', 'no mostraste los recuerdos'}:
        pagina = estado.get('_ultima_pagina_visible')
        if pagina is None:
            return True, 'Primero abre un listado con /recuerdos o /sin_clasificar.'
        estado['_lista_memorias'] = {m['numero_lista']: m['id'] for m in pagina.get('memorias', [])}
        texto = renderizar('listar_memorias', pagina)
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    if normal in {'muestrame los sin clasificar', 'muestrame los recuerdos sin clasificar',
                  'lista los sin clasificar', 'lista los recuerdos sin clasificar', '/sin_clasificar'}:
        q, filtro = '/recuerdos', 'sin_clasificar'
    elif re.fullmatch(r'(?:muestrame|mostrame|lista|listar) (?:todos )?(?:los|mis) recuerdos(?: para .+)?', normal):
        q = '/recuerdos'
    elif normal in {'muestrame los proyectos', 'muestrame todos los proyectos', 'que proyectos tengo'}:
        q = '/proyectos'
    if q == '/tamano' or q.startswith('/tamano '):
        valor = q[len('/tamano'):].strip()
        if not valor:
            return True, f"Tamaño de página: {estado.get('_tamano_pagina', 5)}. Usa /tamano N, entre 1 y 20."
        if not valor.isdigit() or not 1 <= int(valor) <= 20:
            return True, 'Elige un tamaño entre 1 y 20.'
        estado['_tamano_pagina'] = int(valor)
        for clave in ('_pagina_memorias','_listado_completo','_ultima_pagina_visible','_lista_memorias','_memorias','_origen_listado'):
            estado.pop(clave, None)
        return True, f"Mostraré {int(valor)} recuerdos por página. Abre /recuerdos o realiza una búsqueda nueva."
    for acceso,nombre in [('/buscar','buscar_memoria'),('/similares','buscar_memoria_semantica')]:
        if q == acceso or q.startswith(acceso+' '):
            consulta = pregunta.strip()[len(acceso):].strip()
            if not consulta:
                return True, f'Escribe {acceso} seguido del texto que quieres encontrar.'
            args = {'consulta':consulta}
            if estado.get('_proyecto_activo'):
                args['proyecto'] = estado['_proyecto_activo']
            if nombre == 'buscar_memoria_semantica':
                args.update(limite=5,incluir_personal=False)
            r = ejecutar(nombre,args)
            texto = renderizar(nombre,r)
            historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
            return True,texto
    if q == '/ultima_accion':
        ultima = estado.get('_ultima_accion')
        if ultima is None:
            return True, 'Todavía no hay intentos de cambio en esta conversación.'
        return True, f"Última acción intentada: {ultima['fecha']}\n{ultima['detalle']}"
    if q == '/ver' or q.startswith('/ver '):
        valor = q[len('/ver'):].strip()
        if not valor.isdigit():
            return True, 'Usa /ver N con un número de la página visible.'
        r = ejecutar('ver_recuerdo', {'numero_recuerdo':int(valor)})
        texto = renderizar('ver_recuerdo', r)
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    if q in {'/ultimo_recuerdo', '/ultima_conversacion'}:
        nombre = 'consultar_ultimo_recuerdo' if q == '/ultimo_recuerdo' else 'consultar_ultima_conversacion'
        resultado = ejecutar(nombre, {})
        texto = renderizar(nombre, resultado)
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    if q == '/pagina' or q.startswith('/pagina '):
        valor = q[len('/pagina'):].strip()
        pagina = estado.get('_pagina_memorias')
        snapshot = estado.get('_listado_completo')
        if pagina is None or snapshot is None:
            return True, 'Primero abre un listado con /recuerdos.'
        tamano = pagina.get('tamano', 5)
        total = max(1, (len(snapshot)+tamano-1)//tamano)
        if not valor.isdigit() or not 1 <= int(valor) <= total:
            return True, f'Elige una página entre 1 y {total}.'
        args = {'desplazamiento':(int(valor)-1)*tamano}
        if pagina.get('proyecto'):
            args['proyecto'] = pagina['proyecto']
        if pagina.get('orden'):
            args['orden'] = pagina['orden']
        estado['_reutilizar_listado'] = True
        r = ejecutar('listar_memorias', args)
        texto = renderizar('listar_memorias', r)
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    if q == '/proyecto' or q.startswith('/proyecto '):
        nombre_pedido = pregunta.strip()[len('/proyecto'):].strip()
        if not nombre_pedido:
            return True, f"Proyecto activo: {estado.get('_proyecto_activo', 'ninguno')}. Usa /proyecto NOMBRE para elegir uno."
        r = ejecutar('listar_proyectos', {})
        if not r.get('ok'):
            return True, renderizar('listar_proyectos', r)
        proyectos = [p['proyecto'] for p in r.get('proyectos', [])]
        candidatos = [n for n in proyectos if n.casefold() == nombre_pedido.casefold()]
        if not candidatos:
            candidatos = [n for n in proyectos if normalizar_nombre(n) == normalizar_nombre(nombre_pedido)]
        if len(candidatos) > 1:
            return True, 'Hay varios proyectos con nombres parecidos. Indica el nombre exacto de /proyectos.'
        nombre_real = candidatos[0] if candidatos else None
        if nombre_real is None:
            return True, 'Ese proyecto no existe. No cambié el proyecto activo. Usa /proyectos para ver los disponibles.'
        estado['_proyecto_activo'] = nombre_real
        estado.pop('_pagina_memorias', None)
        estado.pop('_listado_completo', None)
        for clave in ('_lista_memorias', '_ultima_pagina_visible', '_memorias'):
            estado.pop(clave, None)
        texto = f"Proyecto activo: {nombre_real}. /recuerdos y las búsquedas se limitarán a ese proyecto. /todos quita el filtro."
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    if q == '/todos':
        estado.pop('_proyecto_activo', None)
        estado.pop('_pagina_memorias', None)
        estado.pop('_listado_completo', None)
        for clave in ('_lista_memorias', '_ultima_pagina_visible', '_memorias'):
            estado.pop(clave, None)
        texto = 'Consultas sin proyecto activo. /recuerdos mostrará todos los proyectos.'
        historial.extend([{'role':'user','content':pregunta}, {'role':'assistant','content':texto}])
        return True, texto
    if q == '/ayuda' or q.startswith('/ayuda '):
        return True, ayuda(q[len('/ayuda'):].strip())
    if q == '/nuevo':
        historial[:] = [{'role':'system', 'content':sistema}]
        estado.clear()
        return True, 'Conversación nueva. Los recuerdos guardados siguen disponibles.'
    if q in {'/mas', '/anterior', '/actualizar'}:
        pagina = estado.get('_pagina_memorias')
        if pagina is None:
            return True, 'Primero escribe /recuerdos para abrir un listado.'
        siguiente = pagina.get('siguiente_desplazamiento')
        if q == '/anterior':
            if pagina.get('desplazamiento', 0) == 0:
                return True, 'Ya estás en la primera página.'
            siguiente = max(0, pagina['desplazamiento'] - pagina.get('tamano', 5))
            estado['_reutilizar_listado'] = True
        elif q == '/actualizar':
            estado.pop('_listado_completo', None)
            origen = estado.get('_origen_listado', {})
            if origen.get('nombre') in {'buscar_memoria', 'buscar_memoria_semantica'}:
                r = ejecutar(origen['nombre'], origen['argumentos'])
                texto = renderizar(origen['nombre'], r)
                historial.extend([{'role':'user','content':pregunta},{'role':'assistant','content':texto}])
                return True,texto
            siguiente = 0
        if siguiente is None:
            return True, 'Llegaste al final del listado. Usa /recuerdos para actualizarlo.'
        nombre, args = 'listar_memorias', {'desplazamiento':siguiente}
        if pagina.get('proyecto'):
            args['proyecto'] = pagina['proyecto']
        if pagina.get('orden'):
            args['orden'] = pagina['orden']
    elif q in {'/proyectos', '/recuerdos', '/estado'}:
        nombre = {'/proyectos':'listar_proyectos', '/recuerdos':'listar_memorias', '/estado':'consultar_estado_cerebro'}[q]
        args = {'proyecto': filtro} if filtro is not None else ({'proyecto':estado['_proyecto_activo']} if nombre == 'listar_memorias' and estado.get('_proyecto_activo') else {})
        if orden is not None:
            args['orden'] = orden
    else:
        return (True, sugerir(q)) if q.startswith('/') else (False, '')
    resultado = ejecutar(nombre, args)
    texto = renderizar(nombre, resultado)
    historial.extend([{'role':'user','content':pregunta},
                     {'role':'assistant','content':texto}])
    return True, texto


def normalizar_nombre(nombre):
    return ''.join(c for c in unicodedata.normalize('NFD', nombre.strip().casefold()) if unicodedata.category(c) != 'Mn')
