"""Accesos de archivos. La ejecución y los permisos siguen en el controlador."""
import re
import shlex
from datetime import datetime
from zoneinfo import ZoneInfo
from lenguaje_jarvis import limpiar, normalizar, limpiar_prefijos

ACCESOS=('/archivos','/leer','/buscar_archivos','/reemplazar','/carpeta','/copiar','/mover','/cambios','/deshacer','/propuestas','/aplicar','/cancelar','/info','/comparar','/encontrar')


def acceso_natural(frase):
    # Solo elimina cortesía al principio/final: los espacios del nombre son literales.
    t=limpiar_prefijos(frase)
    t=re.sub(r'\s+(?:por favor|porfa)$','',t,flags=re.I)
    # Las partículas después de una ruta completa no forman parte del nombre;
    # un destino literal llamado «po» sin extensión sigue conservándose.
    t=re.sub(r'(["\']|\.[A-Za-z0-9]{1,8})\s+(?:po|poh|al tiro|al toque)$',r'\1',t,flags=re.I)
    n=normalizar(t).strip(' ¿?¡!.')
    if n in {'muestra mis archivos','muestrame los archivos','lista los archivos','que archivos hay','que archivos tengo','mis archivos'}:return '/archivos'
    if n in {'muestra los cambios','muestrame los cambios','historial de cambios','que cambios hiciste'}:return '/cambios'
    if n in {'deshaz el ultimo cambio','revierte el ultimo cambio','deshacer el ultimo cambio','vuelve a la version anterior','desas'}:return '/deshacer'
    if n in {'muestra las propuestas','propuestas pendientes','muestrame las propuestas'}:return '/propuestas'
    if n in {'cancela las propuestas','descarta las propuestas','cancela la propuesta','descarta la propuesta'}:return '/cancelar'
    if n in {'aplica la propuesta','aplica el cambio propuesto'}:return '/aplicar'
    visible=normalizar(re.sub(r'"[^"\n]*"|\'[^\'\n]*\'',' ',t))
    if re.search(r'\b(?:no|nunca|si|despues|luego|pero)\b',visible):return None
    ruta=r'("[^"\n]+"|\'[^\'\n]+\'|[^\s]+)'
    info=re.fullmatch(r'(?:dame|muestra|mu[eé]strame|consulta)\s+(?:la\s+)?(?:informaci[oó]n|tama[nñ]o|detalles)\s+(?:del?\s+)?(?:archivo\s+)?'+ruta,t,re.I)
    if info:return '/info '+shlex.quote(shlex.split(info[1])[0])
    comparar=re.fullmatch(r'(?:compara|comparar)\s+(?:los\s+archivos\s+)?'+ruta+r'\s+(?:con|y)\s+'+ruta,t,re.I)
    if comparar:return '/comparar '+shlex.quote(shlex.split(comparar[1])[0])+' '+shlex.quote(shlex.split(comparar[2])[0])
    leer=re.fullmatch(r'(?:lee|l[eé]eme|abre|muestra|mu[eé]strame|ens[eé][nñ]ame)\s+(?:el\s+)?(?:archivo|fichero)\s+'+ruta,t,re.I)
    if leer:return '/leer '+shlex.quote(shlex.split(leer[1])[0])
    carpeta=re.fullmatch(r'(?:crea|crear|haz|genera|arma)\s+(?:una\s+|la\s+)?(?:carpeta|directorio)\s+(?:llamad[ao]\s+)?'+ruta,t,re.I)
    if carpeta:return '/carpeta '+shlex.quote(shlex.split(carpeta[1])[0])
    mover=re.fullmatch(r'(copia|copiar|duplica|duplicar|mueve|mover|traslada|trasladar|renombra|renombrar)\s+(?:el\s+)?(?:archivo\s+)?'+ruta+r'\s+(?:a|como|con el nombre)\s+'+ruta,t,re.I)
    if mover:
        acceso='/copiar' if normalizar(mover[1]) in {'copia','copiar','duplica','duplicar'} else '/mover'
        return acceso+' '+shlex.quote(shlex.split(mover[2])[0])+' '+shlex.quote(shlex.split(mover[3])[0])
    return None


def renderizar_archivos(nombre,r):
    if not r.get('ok'):
        from errores_usuario import presentar
        return presentar(r.get('error','No pude completar la acción.'))
    if nombre=='proponer_edicion':
        return f"Propuesta para {r['ruta']} — todavía sin escribir:\n{r['diferencia']}\n/propuestas permite revisarla; /aplicar solicita autorización y /cancelar la descarta."
    if nombre=='informacion_archivo':
        fecha=datetime.fromisoformat(r['modificado']).astimezone(ZoneInfo('America/Santiago'))
        return f"{r['ruta']}\nTamaño: {r['bytes']} bytes\nTipo: {r['tipo']}\nModificado: {fecha:%d/%m/%Y %H:%M:%S} (Chile)\nTexto UTF-8: {'sí' if r['texto_utf8'] else 'no confirmado'}"+ (' (comprobado solo en una muestra)' if r['muestra_parcial'] else '')
    if nombre=='comparar_archivos':
        if r['iguales']:return 'Los archivos tienen el mismo contenido.'
        return f"Diferencias entre {r['primero']} y {r['segundo']}:\n{r['diferencia']}\nSalto de línea final: primero {'sí' if r['salto_final_primero'] else 'no'}, segundo {'sí' if r['salto_final_segundo'] else 'no'}."+ ('\n[Diferencia abreviada: supera 20000 caracteres.]' if r['recortado'] else '')
    if nombre=='encontrar_archivos':
        texto='\n'.join(f"• {m['ruta']} ({m['bytes']} bytes)" for m in r['archivos']) or 'No encontré archivos con ese nombre.'
        return texto+ ('\nBúsqueda acotada: usa una carpeta o un nombre más específico.' if r['limite_alcanzado'] else '')
    if nombre=='listar_archivos':
        return f"Archivos en {r.get('ruta','.')}:\n"+'\n'.join(f"• {i['nombre']} ({i['tipo']}{', '+str(i['bytes'])+' bytes' if 'bytes' in i else ''})" for i in r.get('items',[]))
    if nombre in {'leer_archivo','leer_lineas'}:
        if 'siguiente_documento' in r:
            from interfaz_documentos import presentar
            return presentar(r)
        if nombre=='leer_lineas':
            texto='\n'.join(f"{r['inicio']+n}: {linea}" for n,linea in enumerate(r.get('lineas',[])))
            return f"{r['ruta']} · {r['total_lineas']} líneas\n{texto}\n"+(f"Siguiente tramo: /leer {shlex.quote(r['ruta'])} {r['siguiente']}" if r.get('siguiente') else 'Fin del archivo.')
        return r.get('contenido','')+ ('\n[Contenido recortado; /leer RUTA INICIO permite leer por líneas.]' if r.get('cortado') else '')
    if nombre=='buscar_texto':
        rows=r.get('resultados',[])
        return '\n'.join(f"• {m['archivo']}:{m['linea']} — {m['texto']}" for m in rows) if rows else 'No encontré ese texto en los archivos.'
    if nombre=='listar_cambios':
        rows=r.get('cambios',[])
        return '\n'.join(f"{n}. {m['tipo']} · {m['ruta']} · {'deshecho' if m['revertido'] else 'no aplicado' if not m.get('aplicado',True) else 'registro pendiente' if m.get('estado')=='registro_pendiente' else 'activo'} · {datetime.fromtimestamp(m['fecha']).astimezone():%d/%m/%Y %H:%M}" for n,m in enumerate(rows,1)) if rows else 'No hay cambios de archivos registrados.'
    return 'Cambio realizado y comprobado.' if r.get('verificado') else 'El resultado no pudo comprobarse.'


def comando_archivos(pregunta,historial,estado,ejecutar):
    original=pregunta
    if not pregunta.startswith('/'):
        pregunta=acceso_natural(pregunta)
        if pregunta is None:return False,''
    try:partes=shlex.split(pregunta)
    except ValueError:return (True,'Revisa las comillas de la ruta.') if pregunta.startswith('/') else (False,'')
    if not partes:return False,''
    acceso=partes[0].casefold()
    if acceso not in ACCESOS:
        return False,''
    try:
        if acceso in {'/propuestas','/aplicar','/cancelar'}:
            pendientes={k:v for k,v in estado.items() if re.fullmatch(r'[0-9a-f]{8,32}',str(k)) and isinstance(v,dict) and 'diferencia' in v and 'ruta' in v}
            if acceso=='/cancelar':
                if len(partes)!=1:raise ValueError('Uso: /cancelar (descarta las propuestas pendientes de esta conversación)')
                for k in pendientes:estado.pop(k,None)
                estado.pop('_propuestas_visibles',None)
                texto=f'Descarté {len(pendientes)} propuesta(s) pendiente(s) de esta conversación. Los archivos no cambiaron.'
            elif acceso=='/propuestas':
                if len(partes)!=1:raise ValueError('Uso: /propuestas')
                estado['_propuestas_visibles']=list(pendientes)
                texto='\n\n'.join(f"{i}. {v['ruta']} — pendiente, sin escribir\n{v['diferencia']}" for i,v in enumerate(pendientes.values(),1)) if pendientes else 'No hay propuestas pendientes en esta conversación.'
                if pendientes:texto+='\n/aplicar N solicita permiso para escribir; /cancelar descarta las propuestas.'
            else:
                if len(partes)>2:raise ValueError('Uso: /aplicar [N]')
                if len(partes)==1:
                    if len(pendientes)!=1:raise ValueError('Usa /propuestas y elige el número; hay varias propuestas o ninguna.')
                    ident=next(iter(pendientes))
                else:
                    numero=int(partes[1]);visibles=estado.get('_propuestas_visibles',[])
                    if not 1<=numero<=len(visibles) or visibles[numero-1] not in pendientes:raise ValueError('Usa /propuestas y elige un número pendiente del listado.')
                    ident=visibles[numero-1]
                r=ejecutar('aplicar_edicion',{'id_propuesta':ident})
                texto=renderizar_archivos('aplicar_edicion',r)
            historial.extend([{'role':'user','content':original},{'role':'assistant','content':texto}])
            return True,texto
        if acceso=='/info':
            if len(partes)!=2:raise ValueError('Uso: /info RUTA')
            nombre,args='informacion_archivo',{'ruta':partes[1]}
        elif acceso=='/comparar':
            if len(partes)!=3:raise ValueError('Uso: /comparar PRIMERO SEGUNDO')
            nombre,args='comparar_archivos',{'primero':partes[1],'segundo':partes[2]}
        elif acceso=='/encontrar':
            if not 2<=len(partes)<=3:raise ValueError('Uso: /encontrar NOMBRE [CARPETA]')
            nombre,args='encontrar_archivos',{'nombre':partes[1],'ruta':partes[2] if len(partes)==3 else '.'}
        elif acceso=='/archivos':
            if len(partes)>2:raise ValueError('Uso: /archivos [CARPETA]')
            nombre,args='listar_archivos',{'ruta':partes[1] if len(partes)>1 else '.'}
        elif acceso=='/leer':
            if not 2<=len(partes)<=4:raise ValueError('Uso: /leer RUTA [INICIO] [CANTIDAD]')
            from interfaz_documentos import resolver_referencia
            nombre,args='leer_lineas',{'ruta':resolver_referencia(partes[1],estado)}
            if len(partes)>2:args['inicio']=int(partes[2])
            if len(partes)>3:args['cantidad']=int(partes[3])
        elif acceso=='/buscar_archivos':
            if len(partes)<2:raise ValueError('Uso: /buscar_archivos TEXTO')
            nombre,args='buscar_texto',{'texto':' '.join(partes[1:])}
        elif acceso=='/reemplazar':
            if len(partes) not in {4,5} or (len(partes)==5 and partes[4]!='--todos'):raise ValueError('Uso: /reemplazar RUTA \"texto actual\" \"texto nuevo\" [--todos]')
            nombre,args='reemplazar_texto',{'ruta':partes[1],'texto_actual':partes[2],'texto_nuevo':partes[3],'todas':len(partes)==5}
        elif acceso=='/carpeta':
            if len(partes)!=2:raise ValueError('Uso: /carpeta RUTA')
            nombre,args='crear_carpeta',{'ruta':partes[1]}
        elif acceso in {'/copiar','/mover'}:
            if len(partes)!=3:raise ValueError(f'Uso: {acceso} ORIGEN DESTINO (comillas si hay espacios)')
            nombre,args='copiar_archivo' if acceso=='/copiar' else 'mover_archivo',{'origen':partes[1],'destino':partes[2]}
        else:
            r=ejecutar('listar_cambios',{'limite':20})
            if not r.get('ok'):return True,renderizar_archivos('listar_cambios',r)
            cambios=r.get('cambios',[])
            if acceso=='/cambios':
                estado['_cambios_visibles']=cambios
                return True,renderizar_archivos('listar_cambios',r)+'\n/deshacer N deshace el cambio numerado; /deshacer usa el último activo.'
            if len(partes)>2:raise ValueError('Uso: /deshacer [N]')
            if len(partes)==2:
                numero=int(partes[1]);visibles=estado.get('_cambios_visibles',[])
                if not 1<=numero<=len(visibles):raise ValueError('Primero usa /cambios y elige su número')
                cambio=visibles[numero-1]
            else:
                cambio=next((m for m in cambios if not m['revertido'] and m.get('aplicado',True)),None)
                if cambio is None:return True,'No hay un cambio activo que deshacer.'
            nombre,args='revertir_cambio',{'id_cambio':cambio['id_cambio']}
        r=ejecutar(nombre,args);texto=renderizar_archivos(nombre,r)
        from interfaz_documentos import recordar_resultado
        recordar_resultado(nombre,r,estado)
        if r.get('ok') and nombre in {'listar_archivos','leer_archivo','leer_lineas','informacion_archivo','comparar_archivos','encontrar_archivos','buscar_texto'}:
            estado['_tipo_ultimo_listado']='archivos'
        historial.extend([{'role':'user','content':original},{'role':'assistant','content':texto}])
        return True,texto
    except ValueError as e:return True,str(e)
