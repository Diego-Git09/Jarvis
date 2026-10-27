"""Recordatorios persistentes, horarios de Chile y modificaciones atómicas."""
import fcntl
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from entorno_jarvis import DATOS
from lenguaje_jarvis import normalizar
from fechas_naturales import preparar_fecha

ARCHIVO=DATOS/'recordatorios.json'
ZONA=ZoneInfo('America/Santiago')
MAX_ITEMS=5000
MESES={'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
DIAS=('lunes','martes','miercoles','jueves','viernes','sabado','domingo')


def ahora():return datetime.now(ZONA)


def interpretar_fecha(expresion,base=None):
    """Siempre = None; sin hora explícita una fecha comienza a las 09:00 de Chile."""
    if not isinstance(expresion,str):raise ValueError('Indica una fecha o «siempre».')
    n=preparar_fecha(expresion).strip(' .¿?');base=(base or ahora()).astimezone(ZONA)
    if n in {'siempre','permanente','todo el tiempo','sin fecha'}:return None
    if n in {'ahora','hoy ahora'}:return base.isoformat(timespec='seconds')
    relativo=re.fullmatch(r'(?:en|dentro de)\s+(\d+)\s*(minutos?|horas?|dias?)',n)
    if relativo:
        cantidad=int(relativo[1])
        if not 1<=cantidad<=10000:raise ValueError('El plazo debe estar entre 1 y 10000.')
        factor=60 if relativo[2].startswith('minuto') else 3600 if relativo[2].startswith('hora') else 86400
        return (base.astimezone(timezone.utc)+timedelta(seconds=cantidad*factor)).astimezone(ZONA).isoformat(timespec='seconds')
    # ISO con zona admite los horarios que devuelva el modelo, validando el instante.
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})',expresion.strip()):
        return datetime.fromisoformat(expresion.strip().replace('Z','+00:00')).astimezone(ZONA).isoformat(timespec='seconds')
    for _ in range(3):n=re.sub(r'^(?:desde|para|el|a partir de)\s+','',n)
    hm=re.search(r'\s+(?:a las?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|de la manana|de la tarde|de la noche)?$',n)
    hora,minuto=9,0
    if hm and (':' in hm[0] or 'a la' in hm[0] or hm[3]):
        hora=int(hm[1]);minuto=int(hm[2] or 0);mer=hm[3]
        if mer and mer in {'pm','de la tarde','de la noche'} and hora<12:hora+=12
        if mer and mer in {'am','de la manana'} and hora==12:hora=0
        n=n[:hm.start()].strip()
    if n in {'hoy','manana','pasado manana','pasadomanana'}:
        fecha=base.date()+timedelta(days={'hoy':0,'manana':1,'pasado manana':2,'pasadomanana':2}[n])
    elif n in DIAS or n.startswith('proximo ') and n[8:] in DIAS or n.startswith('este ') and n[5:] in DIAS:
        dia=n.removeprefix('proximo ').removeprefix('este ');delta=(DIAS.index(dia)-base.weekday())%7
        fecha=base.date()+timedelta(days=delta)
        if delta==0 and (n.startswith('proximo ') or not n.startswith('este ') and base.hour*60+base.minute>=hora*60+minuto):fecha+=timedelta(days=7)
    else:
        m=re.fullmatch(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?',n)
        iso=re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})',n)
        letras=re.fullmatch(r'(\d{1,2}) de ('+'|'.join(MESES)+r')(?: (?:de |del )?(\d{4}))?',n)
        try:
            if m:fecha=datetime(int(m[3] or base.year),int(m[2]),int(m[1])).date()
            elif iso:fecha=datetime(*map(int,iso.groups())).date()
            elif letras:fecha=datetime(int(letras[3] or base.year),MESES[letras[2]],int(letras[1])).date()
            else:raise ValueError('No reconocí la fecha. Usa «mañana a las 09:00», «14/10/2026 09:00», «en 2 horas» o «siempre».')
            if (m and not m[3] or letras and not letras[3]) and fecha<base.date():fecha=fecha.replace(year=base.year+1)
        except (TypeError,OverflowError):raise ValueError('La fecha no es válida.')
    try:local=datetime(fecha.year,fecha.month,fecha.day,hora,minuto,tzinfo=ZONA)
    except ValueError:raise ValueError('La fecha u hora no es válida.')
    if local.astimezone(timezone.utc).astimezone(ZONA).replace(tzinfo=None)!=local.replace(tzinfo=None):
        raise ValueError('Esa hora no existe en Chile por el cambio de horario. Elige otra hora.')
    return local.isoformat(timespec='seconds')


def texto_fecha(item):
    def formato(fecha):return datetime.fromisoformat(fecha).astimezone(ZONA).strftime('%d/%m/%Y %H:%M (Chile)')
    inicio='Siempre visible' if item['fecha'] is None else 'Desde '+formato(item['fecha'])
    if item.get('evento'):
        inicio='Evento: '+formato(item['evento'])+'\n'+inicio
        if item.get('anticipacion_dias') is not None:inicio+=f" · {item['anticipacion_dias']} día(s) antes"
        elif item.get('anticipacion_minutos') is not None:
            minutos=item['anticipacion_minutos'];inicio+=f" · {minutos//60} hora(s) antes" if minutos%60==0 else f" · {minutos} minuto(s) antes"
    if item.get('mostrar_hasta'):inicio+='\nMostrar hasta: '+formato(item['mostrar_hasta'])
    return inicio


def plan_fecha(fecha=None,evento=None,anticipacion_dias=None,mostrar_hasta=None,anticipacion_minutos=None):
    """Mantiene separados el día del evento y el comienzo de visibilidad."""
    if anticipacion_dias is not None and (type(anticipacion_dias) is not int or not 0<=anticipacion_dias<=3660):
        raise ValueError('La anticipación debe ser un número entero de días entre 0 y 3660.')
    if anticipacion_minutos is not None and (type(anticipacion_minutos) is not int or not 0<=anticipacion_minutos<=5_270_400):raise ValueError('La anticipación en minutos debe ser un entero entre 0 y 5270400.')
    if anticipacion_minutos is not None and anticipacion_dias is not None and anticipacion_minutos!=anticipacion_dias*1440:raise ValueError('Las dos anticipaciones indican plazos distintos. Usa una sola.')
    e=interpretar_fecha(evento) if evento is not None else None
    if evento is not None and e is None:raise ValueError('El evento necesita una fecha concreta; «siempre» describe cuándo mostrarlo.')
    if (anticipacion_dias is not None or anticipacion_minutos is not None) and e is None:raise ValueError('Necesito la fecha del evento para calcular el aviso anticipado.')
    if anticipacion_dias is not None:
        f=(datetime.fromisoformat(e).astimezone(ZONA)-timedelta(days=anticipacion_dias)).isoformat(timespec='seconds')
        if fecha is not None and interpretar_fecha(fecha)!=f:raise ValueError('La fecha de aparición y la anticipación indican horarios diferentes. Precisa cuál quieres.')
    elif anticipacion_minutos is not None:
        f=(datetime.fromisoformat(e).astimezone(timezone.utc)-timedelta(minutes=anticipacion_minutos)).astimezone(ZONA).isoformat(timespec='seconds')
        if fecha is not None and interpretar_fecha(fecha)!=f:raise ValueError('La fecha de aparición y la anticipación indican horarios diferentes.')
    else:f=interpretar_fecha(fecha) if fecha is not None else e
    fin_abierto=normalizar(mostrar_hasta or '') in {'sin fin','sin limite','siempre'}
    hasta=interpretar_fecha(mostrar_hasta) if mostrar_hasta is not None and not fin_abierto else None
    if mostrar_hasta is not None and hasta is None and not fin_abierto:raise ValueError('Para terminar de mostrarlo necesito una fecha concreta.')
    if hasta is not None and f is not None and datetime.fromisoformat(hasta)<datetime.fromisoformat(f):raise ValueError('El final no puede ser anterior al inicio del aviso.')
    return {'fecha':f,'evento':e,'anticipacion_dias':anticipacion_dias,'anticipacion_minutos':anticipacion_minutos,'mostrar_hasta':hasta}


def revision(item):
    return hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def listar(incluir_hechos=False,ruta=None):
    ruta=ruta or ARCHIVO
    if not ruta.exists():return []
    if ruta.is_symlink() or ruta.stat().st_size>5_000_000:raise ValueError('Archivo de recordatorios inválido; no se sobrescribió.')
    datos=json.loads(ruta.read_text(encoding='utf-8'))
    if not isinstance(datos,list) or len(datos)>MAX_ITEMS:raise ValueError('Lista de recordatorios inválida.')
    ids=set()
    for r in datos:
        if not isinstance(r,dict) or not re.fullmatch(r'[0-9a-f]{32}',str(r.get('id',''))) or r['id'] in ids or not isinstance(r.get('texto'),str) or not 1<=len(r['texto'])<=4000 or r.get('estado') not in {'activo','hecho','eliminado'} or 'fecha' not in r:
            raise ValueError('Hay recordatorios inválidos; no se sobrescribió la lista.')
        ids.add(r['id'])
        if r['fecha'] is not None:
            if not isinstance(r['fecha'],str) or datetime.fromisoformat(r['fecha']).tzinfo is None:raise ValueError('Fecha guardada inválida.')
        for campo in ('evento','mostrar_hasta'):
            if r.get(campo) is not None and (not isinstance(r[campo],str) or datetime.fromisoformat(r[campo]).tzinfo is None):raise ValueError('Fecha guardada inválida.')
        dias=r.get('anticipacion_dias')
        if dias is not None and (type(dias) is not int or not 0<=dias<=3660 or not r.get('evento')):raise ValueError('Anticipación guardada inválida.')
        minutos=r.get('anticipacion_minutos')
        if minutos is not None and (type(minutos) is not int or not 0<=minutos<=5_270_400 or not r.get('evento')):raise ValueError('Anticipación guardada inválida.')
    return [r for r in datos if incluir_hechos or r['estado']=='activo']


def _actualizar(funcion,ruta=None):
    ruta=ruta or ARCHIVO;ruta.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    bloqueo_ruta=ruta.with_suffix('.lock')
    fd_lock=os.open(bloqueo_ruta,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd_lock,'a') as bloqueo:
        fcntl.flock(bloqueo,fcntl.LOCK_EX);datos=listar(True,ruta);resultado=funcion(datos)
        fd,tmp=tempfile.mkstemp(prefix='.recordatorios-',dir=ruta.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(datos,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,ruta)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return resultado


def crear(texto,fecha=None,ruta=None,evento=None,anticipacion_dias=None,mostrar_hasta=None,anticipacion_minutos=None):
    if not isinstance(texto,str) or not 1<=len(texto.strip())<=4000:raise ValueError('Escribe un recordatorio de 1 a 4000 caracteres.')
    plan=plan_fecha(fecha,evento,anticipacion_dias,mostrar_hasta,anticipacion_minutos)
    def aplicar(datos):
        if len(datos)>=MAX_ITEMS:raise ValueError('La lista llegó a 5000 recordatorios.')
        r={'id':uuid.uuid4().hex,'texto':texto.strip(),**plan,'estado':'activo','actualizado':ahora().isoformat(timespec='microseconds')}
        datos.append(r);return dict(r)
    return _actualizar(aplicar,ruta)


def proyectar(item,texto=None,fecha=None,estado=None,evento=None,anticipacion_dias=None,mostrar_hasta=None,anticipacion_minutos=None):
    cambios={}
    if texto is not None:
        if not isinstance(texto,str) or not 1<=len(texto.strip())<=4000:raise ValueError('Escribe un recordatorio de 1 a 4000 caracteres.')
        cambios['texto']=texto.strip()
    if fecha is not None:cambios.update(fecha=interpretar_fecha(fecha),anticipacion_dias=None,anticipacion_minutos=None)
    if estado is not None:
        if estado not in {'activo','hecho','eliminado'}:raise ValueError('Estado inválido.')
        cambios['estado']=estado
    if not cambios and all(v is None for v in (evento,anticipacion_dias,mostrar_hasta,anticipacion_minutos)):raise ValueError('No indicaste qué cambiar.')
    if evento is not None or anticipacion_dias is not None or anticipacion_minutos is not None:
        dias=anticipacion_dias if anticipacion_dias is not None else None if anticipacion_minutos is not None else item.get('anticipacion_dias')
        minutos=anticipacion_minutos if anticipacion_minutos is not None else None if anticipacion_dias is not None else item.get('anticipacion_minutos')
        fecha_nueva=fecha if fecha is not None else ('siempre' if item['fecha'] is None and dias is None and minutos is None else None)
        cambios.update(plan_fecha(fecha_nueva,evento or item.get('evento'),dias,mostrar_hasta or item.get('mostrar_hasta'),minutos))
    elif mostrar_hasta is not None:cambios['mostrar_hasta']=None if normalizar(mostrar_hasta) in {'sin fin','sin limite','siempre'} else interpretar_fecha(mostrar_hasta)
    resultado=dict(item,**cambios)
    hasta=resultado.get('mostrar_hasta');desde=resultado['fecha']
    if mostrar_hasta is not None and hasta is None and normalizar(mostrar_hasta) not in {'sin fin','sin limite','siempre'}:raise ValueError('Indica una fecha concreta para terminar de mostrarlo.')
    if hasta and desde and datetime.fromisoformat(hasta)<datetime.fromisoformat(desde):raise ValueError('El final no puede ser anterior al aviso.')
    return resultado


def modificar(ident,texto=None,fecha=None,estado=None,esperado=None,ruta=None,evento=None,anticipacion_dias=None,mostrar_hasta=None,anticipacion_minutos=None):
    def aplicar(datos):
        r=next((r for r in datos if r['id']==ident),None)
        if r is None:raise ValueError('El recordatorio ya no existe. Actualiza el listado.')
        if esperado is not None and revision(r)!=esperado:raise ValueError('El recordatorio cambió desde que lo consultaste. Actualiza antes de modificarlo.')
        r.update(proyectar(r,texto,fecha,estado,evento,anticipacion_dias,mostrar_hasta,anticipacion_minutos))
        r['actualizado']=ahora().isoformat(timespec='microseconds');return dict(r)
    return _actualizar(aplicar,ruta)


def visibles(items,base=None):
    base=base or ahora()
    return [r for r in items if r['estado']=='activo' and (r['fecha'] is None or datetime.fromisoformat(r['fecha'])<=base) and (not r.get('mostrar_hasta') or base<=datetime.fromisoformat(r['mostrar_hasta']))]


def presentar(items):
    if not items:return 'No tienes recordatorios pendientes.'
    return 'Recordatorios:\n\n'+'\n\n'.join(f"{n}. {r['texto']}\n   {texto_fecha(r)}" for n,r in enumerate(items,1))+'\n\nPuedes modificarlos, posponerlos, completarlos o eliminarlos por su número.'
