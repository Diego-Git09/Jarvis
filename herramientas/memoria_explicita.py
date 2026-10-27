"""Guardado literal solicitado por el usuario; fuera de las herramientas del modelo.

La captura automática sigue siendo la vía habitual. Este acceso solo reconoce
una orden con proyecto, título y contenido explícitos, muestra el texto y pide
permiso. No modifica recuerdos existentes ni reintenta una escritura incierta.
"""
import fcntl
import hashlib
import json
import os
import re

from entorno_jarvis import DATOS
from cerebro_mcp import ErrorCerebro
from conversaciones_jarvis import _atomic, _redactar
from lenguaje_jarvis import normalizar

CARPETA=DATOS/'recuerdos_explicitos'
INICIO=re.compile(r'(?is)^\s*(?:jarvis[, :]+)?(?:guarda|guardar|guárdame|guardame|almacena)\s+(?:un\s+)?(?:(?:único|unico|solo)\s+)?(?:recuerdo|memoria|en (?:el )?(?:segundo|2do) cerebro)\b')
ROTULO=r'^\s*(?:\*\*)?(?:título|titulo|contenido)(?:\*\*)?\s*:(?:\*\*)?'


def cabecera(pedido):
    """Separa el encargo del contenido etiquetado, sin reescribir sus literales."""
    if INICIO.match(pedido) and re.search(ROTULO,pedido,re.I|re.M):
        return re.split(ROTULO,pedido,maxsplit=1,flags=re.I|re.M)[0].strip()
    return pedido


def interpretar(pedido):
    if not isinstance(pedido,str) or not INICIO.match(pedido):return None
    corto=re.fullmatch(r'(?is)\s*(?:jarvis[, :]+)?(?:guarda|guardar|guardame|guárdame|almacena)\s+en\s+(?:el\s+)?(?:segundo|2do)\s+cerebro\s+(?:que|q)\s+(.+)',pedido)
    if corto:
        contenido=corto[1].strip()
        if len(contenido)>8000:raise ValueError('El recuerdo supera 8000 caracteres. Divídelo; no guardé nada.')
        if _redactar(contenido)!=contenido:
            raise ValueError('Ese texto contiene posibles credenciales. No guardaré una contraseña. Escribe una nota sin secretos.')
        return {'proyecto':'sin_clasificar','titulo':contenido.splitlines()[0][:120],'contenido':contenido}
    lineas=pedido.strip().splitlines();primera=lineas[0]
    if not re.search(r'(?i)segundo\s+cerebro',primera):return None
    proyecto=re.search(r'(?i)\bproyecto\s+(?:existente\s+)?(.+?)\s*\.?$',primera)
    titulo=re.search(r'(?im)^\s*(?:\*\*)?(?:título|titulo)(?:\*\*)?\s*:(?:\*\*)?\s*(.+?)\s*$',pedido)
    contenido=re.search(r'(?ims)^\s*(?:\*\*)?contenido(?:\*\*)?\s*:(?:\*\*)?\s*\n(.*)$',pedido)
    if not proyecto or not titulo or not contenido:
        raise ValueError('Indica el proyecto existente, «Título: ...» y «Contenido:» seguido del texto en otra línea. No guardé nada.')
    nombre=proyecto[1].strip().removesuffix('.').strip().strip('*`"«»').strip()
    texto=contenido[1].strip()
    # Esta línea final es la instrucción de control del ejemplo del usuario,
    # fuera del contenido. No se eliminan coincidencias dentro del documento.
    cierre='Solicita autorización antes de guardar y confirma el ID creado.'
    texto=re.sub(r'(?:\r?\n){2}'+re.escape(cierre)+r'$', '',texto).rstrip()
    datos={'proyecto':nombre,'titulo':titulo[1].strip(),'contenido':texto}
    if any(not x for x in datos.values()) or len(nombre)>100 or len(datos['titulo'])>300 or len(texto)>8000:
        raise ValueError('El recuerdo necesita proyecto, título (hasta 300 caracteres) y contenido (hasta 8000 caracteres). No guardé nada.')
    return datos


def _coincidencias(cliente,dato):
    # La búsqueda textual devuelve solo veinte coincidencias: conversaciones
    # que citen el título pueden ocultar un recuerdo antiguo. La comprobación
    # previa recorre metadatos paginados y después lee completo solo el ID.
    candidatos=[];vistos=set()
    for desplazamiento in range(0,10000,100):
        resultado=cliente.llamar('listar_memorias',{'proyecto':dato['proyecto'],
            'orden':'antiguos','desplazamiento':desplazamiento,'limite':100})
        filas=resultado.get('memorias')
        if not resultado.get('ok') or not isinstance(filas,list) or len(filas)>100:
            raise ErrorCerebro('No pude comprobar si ese recuerdo ya existe. No repetí la escritura.')
        for m in filas:
            if (not isinstance(m,dict) or type(m.get('id')) is not int or m['id']<=0
                or m.get('proyecto')!=dato['proyecto'] or not isinstance(m.get('titulo'),str)):
                raise ErrorCerebro('El listado de recuerdos no es verificable. No guardé otra copia.')
            if m['id'] in vistos:
                raise ErrorCerebro('El listado cambió durante la comprobación. Vuelve a consultarlo antes de guardar; no escribí nada.')
            vistos.add(m['id'])
            if m['titulo']==dato['titulo'] and m.get('tipo','recuerdo')=='recuerdo':candidatos.append(m)
        if len(filas)<100:return candidatos
    raise ErrorCerebro('El proyecto supera el límite de comprobación de 10000 registros. No creé otra copia; consulta el recuerdo antes de guardar.')


def _comprobar(cliente,ident,dato):
    if type(ident) is not int or ident<=0:raise ErrorCerebro('El servidor no devolvió un ID válido.')
    respuesta=cliente.llamar('consultar_memoria',{'id_memoria':ident})
    filas=respuesta.get('memorias',[])
    if not respuesta.get('ok') or len(filas)!=1 or filas[0].get('id')!=ident or filas[0].get('tipo','recuerdo')!='recuerdo' or any(filas[0].get(k)!=v for k,v in dato.items()):
        raise ErrorCerebro('La lectura posterior no coincide con el recuerdo solicitado; verifica su estado antes de repetir.')
    return ident


def guardar(cliente,dato,confirmar,antes_de_escribir=lambda:None):
    dato={k:_redactar(v).strip() for k,v in dato.items()}
    proyectos=cliente.llamar('listar_proyectos',{})
    filas=proyectos.get('proyectos',proyectos.get('memorias',[]))
    nombres=[x.get('proyecto',x.get('nombre','')) if isinstance(x,dict) else x for x in filas] if isinstance(filas,list) else []
    exactos=[x for x in nombres if isinstance(x,str) and normalizar(x)==normalizar(dato['proyecto'])]
    if not proyectos.get('ok') or len(exactos)!=1:
        raise ErrorCerebro('No pude identificar un único proyecto existente con ese nombre. No creé otro proyecto ni guardé el recuerdo.')
    dato=dict(dato,proyecto=exactos[0])
    if CARPETA.is_symlink():raise ErrorCerebro('La carpeta de comprobantes no puede ser un enlace. No guardé nada.')
    CARPETA.mkdir(parents=True,exist_ok=True,mode=0o700)
    ruta_lock=CARPETA/'guardar.lock'
    fd=os.open(ruta_lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as candado:
        fcntl.flock(candado,fcntl.LOCK_EX)
        clave=hashlib.sha256(json.dumps(dato,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        pendiente=CARPETA/(clave+'.json')
        candidatos=_coincidencias(cliente,dato)
        if len(candidatos)>1:raise ErrorCerebro('Hay varios recuerdos con ese título. No creé otra copia ni modifiqué ninguno.')
        if candidatos:
            ident=_comprobar(cliente,candidatos[0].get('id'),dato)
            if pendiente.exists() and not pendiente.is_symlink():pendiente.unlink()
            return f'Ya existe ese recuerdo con el mismo texto en «{dato["proyecto"]}». ID: {ident}. Lo comprobé; no creé otra copia.'
        if pendiente.exists():
            raise ErrorCerebro('El guardado anterior quedó sin confirmar. No repetí la escritura: consulta Segundo Cerebro antes de intentarlo de nuevo.')
        vista=f'Guardar un único recuerdo en «{dato["proyecto"]}»:\nTítulo: {dato["titulo"]}\n\nContenido:\n{dato["contenido"]}'
        if not confirmar(vista):return 'No autorizaste el guardado. No creé el recuerdo.'
        antes_de_escribir()
        # Persistir antes del envío: un corte tras aceptar el servidor nunca
        # desencadena otra escritura automática, incluso al reabrir Jarvis.
        _atomic(pendiente,{'estado':'resultado_incierto','sha256':clave})
        try:
            if not cliente.iniciado:cliente._iniciar()
            bruto=cliente._enviar('tools/call',{'name':'guardar_memoria','arguments':dato})
            if not isinstance(bruto,dict) or bruto.get('isError'):raise ErrorCerebro('El servidor no confirmó el guardado.')
            estructurado=bruto.get('structuredContent')
            texto=estructurado.get('result','') if isinstance(estructurado,dict) else '\n'.join(p.get('text','') for p in bruto.get('content',[]) if isinstance(p,dict))
            match=re.search(r'Memoria guardada\. ID: (\d+)',str(texto))
            if not match:raise ErrorCerebro('El resultado del guardado es incierto; no lo repetí.')
            ident=_comprobar(cliente,int(match[1]),dato)
        except (OSError,ValueError,KeyError,TypeError,ConnectionError) as e:
            raise ErrorCerebro('No pude comprobar el guardado. Conservé el bloqueo de reintento para evitar duplicados; consulta Segundo Cerebro antes de repetir.') from e
        pendiente.unlink()
        return f'Recuerdo guardado y comprobado en «{dato["proyecto"]}». ID creado: {ident}.'


def comando(pedido,cliente,confirmar,estado):
    # Durante una práctica, la siguiente respuesta describe el comportamiento
    # deseado. Hasta una orden literal completa sigue siendo un ejemplo.
    if estado.get('_entrenamiento_pendiente'):return False,''
    try:
        dato=interpretar(pedido)
        if dato is None:return False,''
        if cliente is None:return True,'No hay cliente de Segundo Cerebro disponible. No guardé nada.'
        import hilo_conversacion as H
        return True,guardar(cliente,dato,confirmar,lambda:H.marcar_accion(estado,'guardar_memoria_explicita'))
    except (ValueError,OSError,ConnectionError) as e:
        return True,str(e)
