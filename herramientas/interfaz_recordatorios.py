"""Lenguaje natural y herramientas de recordatorios, sin depender de Ollama."""
import re
import subprocess
import sys
from pathlib import Path
from entorno_jarvis import PROYECTO, en_pruebas
from lenguaje_jarvis import limpiar,normalizar
import recordatorios_jarvis as R
import lenguaje_recordatorios as NLP

NOMBRES={'listar_recordatorios','crear_recordatorio','modificar_recordatorio','eliminar_recordatorio'}


def iniciar_panel(gestionar=False):
    if en_pruebas():return
    log=PROYECTO/'registros'/'recordatorios_escritorio.log';log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('a') as salida:
        subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('recordatorios_escritorio.py')),
                          '--gestionar' if gestionar else '--refrescar'],stdout=salida,stderr=salida,start_new_session=True)


def separar_fecha(texto):
    if '|' in texto:
        contenido,fecha=texto.rsplit('|',1)
        return contenido.strip(),fecha.strip()
    patron=r'\s+(?:(?:desde|para|el)\s+)?(siempre|permanente|todo el tiempo|(?:hoy|ma[nñ]ana|pasado ma[nñ]ana|pasadoma[nñ]ana|(?:pr[oó]ximo\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)|\d{1,2}[/-]\d{1,2}(?:[/-]\d{4})?|\d{4}-\d{2}-\d{2}|\d{1,2} de (?:'+'|'.join(R.MESES)+r')(?: (?:de |del )?\d{4})?)(?:\s+(?:a las?\s+)?\d{1,2}(?::\d{2})?(?:\s*(?:am|pm|de la ma[nñ]ana|de la tarde|de la noche))?)?|(?:en|dentro de)\s+\d+\s*(?:minutos?|horas?|d[ií]as?))$'
    m=re.search(patron,texto,re.I)
    return (texto[:m.start()].strip(),m[1]) if m else (texto.strip(),'siempre')


def ejecutar(nombre,args,estado,confirmar):
    try:
        if nombre!='listar_recordatorios':
            import hilo_conversacion as H
            H.marcar_accion(estado,nombre)
        if nombre=='listar_recordatorios':
            items=R.listar();estado['_recordatorios_visibles']={n:(r['id'],R.revision(r)) for n,r in enumerate(items,1)}
            if len(items)==1:estado['_recordatorio_foco']=(items[0]['id'],R.revision(items[0]))
            else:estado.pop('_recordatorio_foco',None)
            return {'ok':True,'recordatorios':items,'respuesta':R.presentar(items)}
        if nombre=='crear_recordatorio':
            texto=args['texto'];plan=R.plan_fecha(**{k:v for k,v in args.items() if k in {'fecha','evento','anticipacion_dias','mostrar_hasta','anticipacion_minutos'}})
            if not isinstance(texto,str) or not 1<=len(texto.strip())<=4000:raise ValueError('Escribe un recordatorio de 1 a 4000 caracteres.')
            pedido=f"Crear recordatorio de escritorio:\n\n{texto}\n\n{R.texto_fecha(plan)}"
            if not confirmar(pedido):return {'ok':False,'error':'No autorizaste el recordatorio; no lo guardé.'}
            # Congela las fechas mostradas: no desplaza plazos durante la confirmación.
            item=R.crear(texto,plan['fecha'] or 'siempre',evento=plan['evento'],anticipacion_dias=plan['anticipacion_dias'],mostrar_hasta=plan['mostrar_hasta'],anticipacion_minutos=plan['anticipacion_minutos'])
            estado['_recordatorio_foco']=(item['id'],R.revision(item))
            iniciar_panel()
            return {'ok':True,'recordatorio':item,'respuesta':f"Recordatorio guardado: {item['texto']}\n{R.texto_fecha(item)}. Aparecerá en el panel de escritorio cuando corresponda."}
        numero=args.get('numero')
        if args.get('referencia'):
            referencia=normalizar(args['referencia']).strip('«»"').strip()
            candidatos=[r for r in R.listar() if referencia and referencia in normalizar(r['texto'])]
            if len(candidatos)!=1:raise ValueError('No encontré un único recordatorio con ese texto. Lista los recordatorios y elige su número.')
            seleccion=(candidatos[0]['id'],R.revision(candidatos[0]))
        elif numero is not None:
            if type(numero) is not int or numero<1:raise ValueError('Indica el número del último listado de recordatorios.')
            seleccion=estado.get('_recordatorios_visibles',{}).get(numero)
        else:seleccion=estado.get('_recordatorio_foco')
        if seleccion is None:raise ValueError('Primero lista los recordatorios; no elegí uno por suposición.')
        ident,esperado=seleccion
        item=next((r for r in R.listar() if r['id']==ident),None)
        if item is None or R.revision(item)!=esperado:raise ValueError('Ese recordatorio cambió. Actualiza /recordatorios antes de modificarlo.')
        if nombre=='eliminar_recordatorio':cambios={'estado':'eliminado'};accion='Eliminar'
        else:
            cambios={k:v for k,v in args.items() if k in {'texto','fecha','estado','evento','anticipacion_dias','mostrar_hasta','anticipacion_minutos'}};accion='Modificar'
            if not cambios:raise ValueError('Indica un texto, una fecha o un estado nuevo.')
        preview=R.proyectar(item,**cambios)
        for k in ('fecha','evento','mostrar_hasta'):
            if k in cambios:cambios[k]=preview[k] or ('siempre' if k=='fecha' else cambios[k])
        if not confirmar(f"{accion} este recordatorio:\n\n{item['texto']}\n{R.texto_fecha(item)}\n\nResultado:\n{preview['texto']}\n{R.texto_fecha(preview)}\nEstado: {preview['estado']}"):
            return {'ok':False,'error':'No autorizaste el cambio; conservé el recordatorio.'}
        r=R.modificar(ident,esperado=esperado,**cambios)
        for n,(id_anterior,_) in list(estado.get('_recordatorios_visibles',{}).items()):
            if id_anterior==r['id']:
                if r['estado']=='activo':estado['_recordatorios_visibles'][n]=(r['id'],R.revision(r))
                else:estado['_recordatorios_visibles'].pop(n)
        if r['estado']=='activo':estado['_recordatorio_foco']=(r['id'],R.revision(r))
        else:estado.pop('_recordatorio_foco',None)
        iniciar_panel()
        resultado='eliminado del panel' if r['estado']=='eliminado' else 'completado' if r['estado']=='hecho' else 'actualizado'
        return {'ok':True,'recordatorio':r,'respuesta':f"Recordatorio {resultado}: {r['texto']}\n{R.texto_fecha(r)}."}
    except (ValueError,OSError,TypeError,KeyError) as e:return {'ok':False,'error':str(e)}


def comando(pregunta,estado,confirmar,historial=None):
    p=limpiar(pregunta);n=normalizar(p)
    if n.startswith('recuerda que '):return False,''
    if NLP.no_es_orden(p):return False,''
    pendiente=estado.get('_aclaracion_recordatorio')
    if pendiente:
        if n in {'cancela','cancelalo','mejor no','no','/cancelar_recordatorio'}:
            estado.pop('_aclaracion_recordatorio',None);return True,'Cancelé el cambio; el recordatorio sigue igual.'
        campo='evento' if n in {'el evento','la prueba','fecha del evento','la fecha de la prueba'} else 'fecha' if n in {'el aviso','el recordatorio','inicio del aviso','cuando aparece','la fecha del aviso'} else None
        if campo:
            estado.pop('_aclaracion_recordatorio',None)
            estado['_recordatorio_foco']=pendiente['seleccion']
            r=ejecutar('modificar_recordatorio',{campo:pendiente['valor']},estado,confirmar)
            return True,r.get('respuesta',r.get('error',''))
    if estado.get('_borrador_recordatorio'):
        if n in {'no','mejor no','cancela','cancelalo','cancelar recordatorio','/cancelar_recordatorio'}:
            estado.pop('_borrador_recordatorio',None);return True,'Descarté el recordatorio pendiente; no se había guardado.'
        try:
            cuando=R.interpretar_fecha(p)
            if cuando is not None:
                args=dict(estado.pop('_borrador_recordatorio'))
                if 'anticipacion_dias' in args or 'anticipacion_minutos' in args:args.pop('fecha',None);args['evento']=cuando
                else:args['fecha']=cuando
                r=ejecutar('crear_recordatorio',args,estado,confirmar);return True,r.get('respuesta',r.get('error',''))
        except ValueError:pass
    intencion=NLP.interpretar(p)
    if intencion:
        if intencion['nombre']=='aclarar':
            if intencion.get('borrador'):estado['_borrador_recordatorio']=intencion['borrador']
            from vocabulario_pendientes import aclarar
            return True,aclarar(pregunta,intencion['respuesta'],explicita=True)
        if intencion.get('referencia_corta'):
            respuestas=[m.get('content','') for m in (historial or []) if m.get('role')=='assistant']
            referencia_clara=bool(estado.get('_recordatorio_foco')) and (historial is None or respuestas and respuestas[-1].startswith(('Recordatorio ','Recordatorios:')))
            if not referencia_clara:return True,'¿Qué recordatorio quieres cambiar? Usa /recordatorios y dime su número; no elegí uno por suposición.'
            ident=estado['_recordatorio_foco'][0];item=next((r for r in R.listar() if r['id']==ident),None)
            if item and item.get('evento') and item['evento']!=item['fecha'] and intencion.get('fecha_ambigua'):
                estado['_aclaracion_recordatorio']={'seleccion':estado['_recordatorio_foco'],'valor':intencion['argumentos']['fecha']}
                return True,'¿Quieres cambiar la fecha de la prueba o la fecha del aviso? Son distintas; conservaré el recordatorio hasta que lo precises.'
        r=ejecutar(intencion['nombre'],intencion['argumentos'],estado,confirmar)
        return True,r.get('respuesta',r.get('error',''))
    if NLP.compuesta(p):return False,''
    if n in {'/recordatorios','recordatorios','mis recordatorios','muestrame mis recordatorios','lista los recordatorios','que recordatorios tengo'}:
        r=ejecutar('listar_recordatorios',{},estado,confirmar);return True,r.get('respuesta',r.get('error',''))
    if n in {'/escritorio','muestra los recordatorios en el escritorio','abre los recordatorios','abre el panel de recordatorios'}:
        iniciar_panel(True);return True,'Abrí el panel de recordatorios de escritorio.' if not en_pruebas() else 'Panel solicitado (sin abrir ventanas durante la prueba).'
    crear=re.fullmatch(r'(?:/recordar|recu[eé]rdame|recordame|recuerda|recordar|av[ií]same|(?:crea|crear|haz|a[nñ]ade|agrega) (?:un )?recordatorio(?: de escritorio)?(?: para)?)\s+(.+)',p,re.I|re.S)
    editar=re.fullmatch(r'(?:/editar_recordatorio|(?:edita|modifica|cambia) (?:el )?recordatorio)\s+(\d+)\s+(?:a\s+|por\s+|para\s+)?(.+)',p,re.I|re.S)
    eliminar=re.fullmatch(r'(?:/eliminar_recordatorio|(?:elimina|borra|quita) (?:el )?recordatorio)\s+(\d+)',p,re.I)
    posponer=re.fullmatch(r'(?:/posponer_recordatorio|(?:pospon|posponer|pospone|reprograma) (?:el )?recordatorio)\s+(\d+)\s+(?:para\s+)?(.+)',p,re.I)
    mostrar_fecha=re.fullmatch(r'(?:muestra|mu[eé]strame|pon|deja) (?:el )?recordatorio\s+(\d+)\s+(?:desde\s+|para\s+)?(.+)',p,re.I)
    hecho=re.fullmatch(r'(?:/completar_recordatorio|(?:completa|termina|marca como hecho) (?:el )?recordatorio)\s+(\d+)',p,re.I)
    if crear:
        texto,fecha=separar_fecha(crear[1]);nombre='crear_recordatorio';args={'texto':texto,'fecha':fecha}
    elif editar:
        texto,fecha=separar_fecha(editar[2]);nombre='modificar_recordatorio';args={'numero':int(editar[1]),'texto':texto}
        if fecha!='siempre' or re.search(r'(?:siempre|permanente|\|\s*siempre)$',editar[2],re.I):args['fecha']=fecha
    elif eliminar:nombre='eliminar_recordatorio';args={'numero':int(eliminar[1])}
    elif posponer:nombre='modificar_recordatorio';args={'numero':int(posponer[1]),'fecha':posponer[2]}
    elif mostrar_fecha:nombre='modificar_recordatorio';args={'numero':int(mostrar_fecha[1]),'fecha':mostrar_fecha[2]}
    elif hecho:nombre='modificar_recordatorio';args={'numero':int(hecho[1]),'estado':'hecho'}
    else:return False,''
    r=ejecutar(nombre,args,estado,confirmar);return True,r.get('respuesta',r.get('error',''))
