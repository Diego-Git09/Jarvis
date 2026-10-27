"""Revisión del usuario separada de las anclas y de la opinión de Codex."""
import fcntl
import hashlib
import json
import re
from datetime import datetime,timezone
from entorno_jarvis import DATOS,REGISTROS
from conversaciones_jarvis import _atomic,_redactar

ARCHIVO=DATOS/'revision_respuestas.json'
ORIGEN=REGISTROS/'reportes/ronda3_20261020'
MARCA=re.compile(r'^(bien|parcial|mal)(?:\s*[:;,]?\s+(.+))?$',re.I|re.S)

def leer():
    if ARCHIVO.is_symlink() or any(p.is_symlink() for p in ARCHIVO.parents):raise ValueError('Ruta de revisión no segura')
    try:
        if ARCHIVO.stat().st_size>2_000_000:raise ValueError('Revisión demasiado grande')
        d=json.loads(ARCHIVO.read_text())
        if not isinstance(d,dict) or d.get('version')!=1 or not isinstance(d.get('marcas'),dict):raise ValueError('Marcas dañadas; no se sobrescriben')
        return d
    except FileNotFoundError:return {'version':1,'marcas':{}}

def cargar(tanda):
    fuentes=[('seleccion_40_r8.jsonl',None)] if tanda=='ronda3' else [
        ('seleccion_40_r8.jsonl',{18}),('piloto_adicional/piloto_r3.jsonl',{1}),('piloto_adicional/piloto_r4.jsonl',{1})]
    if tanda not in {'ronda3','parciales'}:raise ValueError('Elige ronda3 o parciales')
    filas=[]
    for nombre,ids in fuentes:
        p=ORIGEN/nombre
        if p.is_symlink() or any(x.is_symlink() for x in p.parents) or p.stat().st_size>50_000_000:raise ValueError('Fuente de medición no segura')
        for l in p.read_text().splitlines():
            r=json.loads(l)
            if ids is not None and r['id'] not in ids:continue
            pregunta=r['pregunta'];respuesta=r['respuesta_original_jarvis']
            if not isinstance(pregunta,str) or not isinstance(respuesta,str):raise ValueError('Caso inválido')
            sha=hashlib.sha256((pregunta+'\0'+respuesta).encode()).hexdigest()
            filas.append({'clave':nombre+':'+str(r['id'])+':'+sha,'id':r['id'],'fuente':nombre,'sha256':sha,'pregunta':_redactar(pregunta),'respuesta':_redactar(respuesta)})
    if not filas:raise ValueError('No hay respuestas en esta tanda')
    return filas

def presentar(filas,pos):
    if pos>=len(filas):return 'Terminaste esta tanda. /revisar_respuestas resumen muestra TU revisión. /revisar_respuestas parciales abre los casos parciales conservados.'
    x=filas[pos]
    return f"Revisión tuya: {pos+1}/{len(filas)} · caso {x['id']} · {x['fuente']}\n\nTu pregunta del banco:\n{x['pregunta']}\n\nRespuesta original:\n{x['respuesta']}\n\nMarca bien, parcial o mal; puedes añadir un comentario. Se pide s/n antes de guardar. «siguiente» omite sin calificar. /revisar_respuestas salir vuelve al chat."

def resumen(tanda='ronda3'):
    filas=cargar(tanda);d=leer()['marcas'];conteos={k:0 for k in ('bien','parcial','mal')}
    for x in filas:
        m=d.get(x['clave'],{})
        if m.get('autor')=='usuario' and m.get('marca') in conteos:conteos[m['marca']]+=1
    total=sum(conteos.values())
    return f"TU revisión de {tanda}: {total}/{len(filas)} calificadas; bien {conteos['bien']}, parcial {conteos['parcial']}, mal {conteos['mal']}; pendientes {len(filas)-total}.\nOpinión anterior de Codex, separada (ronda3 R8): 39 útiles, 1 parcial, 0 fallidas. No se sustituye por tu revisión ni se suman evaluaciones."

def comando(p,estado,confirmar):
    p=p.strip();n=p.casefold();activa=estado.get('_revision_respuestas')
    if n.startswith('/revisar_respuestas'):
        opcion=n.partition(' ')[2].strip() or 'ronda3'
        if opcion=='salir':estado.pop('_revision_respuestas',None);return True,'Revisión pausada. Las marcas guardadas siguen locales.'
        if opcion=='resumen':return True,resumen(activa['tanda'] if activa else 'ronda3')
        if opcion in {'ronda3','parciales'}:
            filas=cargar(opcion);marcas=leer()['marcas'];pos=next((i for i,x in enumerate(filas) if x['clave'] not in marcas),len(filas))
            estado['_revision_respuestas']={'tanda':opcion,'pos':pos};return True,presentar(filas,pos)
        if opcion not in {'siguiente','anterior'}:return True,'Usa /revisar_respuestas ronda3|parciales|resumen|siguiente|anterior|salir.'
        n=opcion
    if not activa:return False,''
    filas=cargar(activa['tanda']);pos=activa['pos']
    if n in {'siguiente','anterior'}:
        activa['pos']=max(0,min(len(filas),pos+(1 if n=='siguiente' else -1)))
        return True,presentar(filas,activa['pos'])
    m=MARCA.fullmatch(p)
    if not m:return False,''
    if pos>=len(filas):return True,presentar(filas,pos)
    x=filas[pos];antes=leer();comentario=_redactar((m[2] or '').strip())[:1000]
    if not confirmar(f"Guardar TU marca «{m[1].casefold()}» para el caso {x['id']} de {x['fuente']}?\nComentario: {comentario or '(sin comentario)'}\nSolo archivo privado local; no se publica en Segundo Cerebro."):
        return True,'Marca sin guardar. Puedes marcar otra vez o decir siguiente.'
    DATOS.mkdir(parents=True,exist_ok=True,mode=0o700);lock=DATOS/'revision_respuestas.lock'
    if lock.is_symlink():raise ValueError('Bloqueo de revisión no seguro')
    with lock.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        if leer()!=antes:raise ValueError('La revisión cambió; comprueba el caso de nuevo')
        antes['marcas'][x['clave']]={'autor':'usuario','marca':m[1].casefold(),'comentario':comentario,'fecha':datetime.now(timezone.utc).isoformat(),'sha256_respuesta':x['sha256']}
        _atomic(ARCHIVO,antes)
    if leer()!=antes:raise ValueError('No pude comprobar tu marca')
    activa['pos']+=1
    return True,'Tu marca quedó guardada localmente.\n\n'+presentar(filas,activa['pos'])
