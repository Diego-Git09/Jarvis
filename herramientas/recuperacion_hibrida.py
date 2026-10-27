"""Fusiona listas acotadas; recibe únicamente fuentes ya autorizadas y vigentes.

RRF con k60. Los nombres son señales de recuperación, nunca permisos. No
abre fuentes, ejecuta documentos ni consulta modelos por su cuenta.
"""
import heapq
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter

MAX_CANDIDATOS=80
MAX_VECTOR_JSON=200_000
_SUMPROD=getattr(math,'sumprod',lambda a,b:sum(x*y for x,y in zip(a,b)))
_EXCLUSION={'excluye','excluir','excluyas','excluyes','descarta','descartar','descartes','descartas','ignora','ignorar','ignores','ignoras','omite','omitir','omitas','omites'}


def vector_normalizado(v):
    if not isinstance(v,list) or not 1<=len(v)<=4096:
        raise ValueError('Vector de búsqueda inválido.')
    try:
        if any(type(x) not in {int,float} or not math.isfinite(x) for x in v):raise ValueError('Vector de búsqueda inválido.')
        norma=math.hypot(*v)
    except (OverflowError,TypeError):raise ValueError('Vector de búsqueda inválido.') from None
    if not math.isfinite(norma) or norma<=0:raise ValueError('Vector de búsqueda sin norma válida.')
    return [x/norma for x in v]


def _similitud_cache(raw,consulta):
    v=json.loads(raw)
    if not isinstance(v,list) or len(v)!=len(consulta):raise ValueError('Dimensión incompatible.')
    # JSON solo produce tipos básicos. hypot rechaza estructuras/cadenas y
    # comprueba todos los valores; no se aceptan booleanos como coordenadas.
    norma=math.hypot(*v)
    if not math.isfinite(norma) or norma<=0 or any(x is True or x is False for x in v):raise ValueError('Vector sin norma válida.')
    # Los vectores del índice ya están normalizados. Para el caso usual basta
    # una división escalar; los extremos se escalan antes del producto.
    sim=_SUMPROD(v,consulta)/norma if .5<=norma<=2 else _SUMPROD((x/norma for x in v),consulta)
    if not math.isfinite(sim):raise ValueError('Similitud no finita.')
    return max(-1.,min(1.,sim))


def _negada(prefijo):
    t=''.join(c for c in unicodedata.normalize('NFD',prefijo.casefold()) if not unicodedata.combining(c))
    # El punto de un nombre.txt no termina la instrucción. Una coordinación
    # sin otro verbo hereda la negativa: «no uses A ni B».
    clausula=re.split(r'[;!?\n]|\.(?=\s|$)',t)[-1];negada=False;pendiente=False
    patron=r'\b(no|nunca|jamas|sin|tampoco|pero|sino|salvo|excepto|'+ '|'.join(sorted(_EXCLUSION))+r'|usa|uses?|usar|utiliza|utilices?|utilizar|consulta|consultes?|consultar|abre|abras?|abrir|mira|mires?|mirar|lee|leas?|leer|revisa|revises?|revisar)\b'
    for m in re.finditer(patron,clausula):
        palabra=m[1]
        if palabra in {'pero','sino'}:negada=False;pendiente=False
        elif palabra in {'no','nunca','jamas','sin','tampoco'}:negada=True;pendiente=True
        elif palabra in {'salvo','excepto'}:negada=True;pendiente=False
        elif palabra in _EXCLUSION:negada=not pendiente;pendiente=False
        else:negada=pendiente;pendiente=False
    return negada


def estado_fuente(pregunta,fuente):
    nombres={str(fuente.get(k,'')) for k in ('nombre','ruta','_nombre_cita')}-{''}
    menciones=[];citas=[]
    for q in re.finditer(r'"([^"\n]*)"|\'([^\'\n]*)\'|«([^»]*)»|“([^”]*)”|`([^`]*)`',pregunta):
        citas.append((q.start(),q.end(),next(x for x in q.groups() if x is not None)))
    for nombre in nombres:
        for m in re.finditer(r'(?<![\w/])'+re.escape(nombre)+r'(?!\w)',pregunta,re.I):
            # Las comillas que contienen solo el nombre son una referencia.
            # Una orden completa citada sigue siendo dato, no una exclusión.
            if any(inicio<m.start()<fin and contenido.strip().casefold()!=nombre.casefold() for inicio,fin,contenido in citas):continue
            menciones.append((m.start(),-1 if _negada(pregunta[:m.start()]) else 1))
    return sorted(menciones)[-1][1] if menciones else 0


def prioridad_fuente(pregunta,fuente):return max(0,estado_fuente(pregunta,fuente))


def _referencia(a,ref):
    original=a.get('referencia_cache',a['nombre'])
    return a.get('_nombre_cita',a['nombre'])+ref[len(original):] if ref.startswith(original) else ref


def _poner(heap,dato,cupo):
    if len(heap)<cupo:heapq.heappush(heap,dato)
    elif dato>heap[0]:heapq.heapreplace(heap,dato)


def buscar(db,fuentes,consulta,pregunta,palabras,tope,usar_fts=True):
    cupo=min(MAX_CANDIDATOS,max(64,tope*4));semanticos=[];lexicos=[];metadatos=[];avisos=[];invalidos=0
    consulta=vector_normalizado(consulta);preparadas=[]
    for i,a in enumerate(fuentes):
        preparadas.append(dict(a,_id=i,_prioridad=prioridad_fuente(pregunta,a)))
    # Solo se materializan los mejores candidatos, no los textos/vectores del
    # índice entero. Cada vector temporal tiene dimensiones/JSON acotados.
    for a in preparadas:
        sql='SELECT rowid,numero,referencia,CASE WHEN length(vector)<=? THEN vector ELSE NULL END FROM trozos WHERE clave=? AND numero<?'
        for rowid,numero,ref,raw in db.execute(sql,(MAX_VECTOR_JSON,a['clave'],a['_visibles'])):
            if a['_prioridad']:
                _poner(metadatos,(a['_prioridad'],0.,-numero,_referencia(a,ref),a['_id'],rowid),cupo)
            if raw is not None:
                try:
                    sim=_similitud_cache(raw,consulta)
                except (ValueError,TypeError,OverflowError):invalidos+=1;continue
            else:invalidos+=1;continue
            _poner(semanticos,(a['_prioridad'],sim,-numero,_referencia(a,ref),a['_id'],rowid),cupo)
    fts=False;terminos=list(palabras)
    if len(terminos)>128:
        terminos=terminos[:128];avisos.append('FTS usó hasta128 términos para acotar la búsqueda; la pregunta original se conserva.')
    if usar_fts and terminos and preparadas:
        condiciones=[];args=[]
        for a in preparadas:
            condiciones.append('(trozos.clave=? AND trozos.numero<?)');args.extend((a['clave'],a['_visibles']))
        match=' OR '.join('"'+w.replace('"','""')+'"' for w in terminos)
        sql='SELECT trozos.rowid,trozos.clave,trozos.numero,trozos.referencia,bm25(trozos_fts) FROM trozos_fts CROSS JOIN trozos ON trozos.rowid=trozos_fts.rowid WHERE ('+' OR '.join(condiciones)+') AND trozos_fts MATCH ? ORDER BY bm25(trozos_fts),trozos.rowid DESC LIMIT ?'
        try:
            for rowid,clave,numero,ref,bm25 in db.execute(sql,(*args,match,cupo)):
                for a in preparadas:
                    if a['clave']==clave and numero<a['_visibles']:
                        _poner(lexicos,(a['_prioridad'],-bm25,-numero,_referencia(a,ref),a['_id'],rowid),cupo)
            fts=True
        except sqlite3.OperationalError:
            avisos.append('FTS5 no estuvo disponible; se combinaron texto y vectores.')
    if not fts or (not lexicos and not semanticos):
        for a in preparadas:
            for rowid,numero,ref,txt in db.execute('SELECT rowid,numero,referencia,texto FROM trozos WHERE clave=? AND numero<?',(a['clave'],a['_visibles'])):
                ref=_referencia(a,ref);cuenta=Counter(re.findall(r'\w{2,}',(txt+' '+ref).casefold()))
                score=sum(min(n,cuenta[w]) for w,n in palabras.items())
                if score:_poner(lexicos,(a['_prioridad'],float(score),-numero,ref,a['_id'],rowid),cupo)
    if metadatos:
        unicos={}
        for dato in lexicos+metadatos:
            ident=(dato[4],dato[5])
            if ident not in unicos or dato>unicos[ident]:unicos[ident]=dato
        lexicos=sorted(unicos.values(),reverse=True)[:cupo]
    fusion={};datos={}
    for lista in (sorted(semanticos,reverse=True),sorted(lexicos,reverse=True)):
        for n,dato in enumerate(lista,1):
            ident=(dato[4],dato[5]);fusion[ident]=fusion.get(ident,0)+1/(60+n);datos[ident]=dato
    orden=sorted(fusion,key=lambda ident:(datos[ident][0],fusion[ident],datos[ident][2],datos[ident][3]),reverse=True)
    candidatos=[]
    for ident in orden[:tope]:
        prioridad,_,numero,ref,_,rowid=datos[ident]
        fila=db.execute('SELECT texto FROM trozos WHERE rowid=?',(rowid,)).fetchone()
        if fila:candidatos.append((prioridad,fusion[ident],numero,ref,fila[0]))
    if invalidos:avisos.append(f'Se omitió la señal de {invalidos} vector(es) inválido(s) o ausente(s); se conservaron las demás señales de recuperación.')
    return {'candidatos':candidatos,'metodo':('FTS5' if fts else 'texto')+('+vectores' if semanticos else '')+'+RRF+metadatos','aviso':' '.join(avisos),
        'estadisticas':{'candidatos_semanticos':len(semanticos),'candidatos_lexicos':len(lexicos),'candidatos_fusion':len(fusion),'limite_por_lista':cupo}}
