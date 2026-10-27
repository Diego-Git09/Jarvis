"""Números y formas de fecha; nunca normaliza nombres ni texto del recordatorio."""
import re
from lenguaje_jarvis import normalizar, ESTILO_USUARIO

UNIDADES={'cero':0,'un':1,'uno':1,'una':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'diecisiete':17,'dieciocho':18,'diecinueve':19,'veinte':20,'veintiuno':21,'veintiun':21,'veintidos':22,'veintitres':23,'veinticuatro':24,'veinticinco':25,'veintiseis':26,'veintisiete':27,'veintiocho':28,'veintinueve':29,'treinta':30,'cuarenta':40,'cincuenta':50,'sesenta':60,'un par':2}
NUMERO=r'(?:\d+|treinta y uno|veinte y (?:uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve)|un par|'+ '|'.join(sorted(UNIDADES,key=len,reverse=True))+r')'


def numero(texto):
    n=normalizar(texto).strip()
    if n.isdigit():return int(n)
    if n in UNIDADES:return UNIDADES[n]
    if ' y ' in n:
        partes=n.split(' y ')
        if len(partes)==2 and partes[0] in UNIDADES and partes[1] in UNIDADES and UNIDADES[partes[0]]>=20 and UNIDADES[partes[1]]<10:
            return UNIDADES[partes[0]]+UNIDADES[partes[1]]
    raise ValueError('No reconocí ese número. Puedes escribirlo con cifras.')


def preparar_fecha(texto):
    n=normalizar(texto).strip()
    for abreviatura, completo in ESTILO_USUARIO.get('abreviaturas',{}).get('fechas',{}).items():
        n=re.sub(r'(?<!\w)'+re.escape(normalizar(abreviatura))+r'(?!\w)',normalizar(completo),n)
    for _ in range(4):n=re.sub(r'^(?:para|desde|el|dia|a partir de)\s+','',n)
    n=n.replace('pasao manana','pasado manana').replace('pasado manana','pasadomanana')
    n=re.sub(r'\b(?:mananna|mananaaa|mañanna)\b','manana',n)
    n=re.sub(r'\b(?:a mediodia|al mediodia)\b','a las 12:00',n)
    n=re.sub(r'\b(?:a medianoche|a la medianoche)\b','a las 00:00',n)
    # «Todo el día» describe visibilidad: se conserva el inicio por defecto
    # 09:00. No inventa un fin ni borra el recordatorio al acabar ese día.
    if re.search(r'\btodo el dia\b',n):
        if re.search(r'\ba las?\b|\d+:\d+',n):raise ValueError('Indica una hora o «todo el día», para no mezclar horarios distintos.')
        n=re.sub(r'\s+todo el dia\b',' a las 09:00',n)
    if re.search(r'\ben la (?:manana|tarde|noche)\b',n):
        raise ValueError('¿A qué hora concreta? «En la mañana/tarde/noche» indica un periodo, no una hora.')
    n=re.sub(r'\b(?:en|dentro de)\s+('+NUMERO+r')\s+(minutos?|horas?|dias?|semanas?)\b',lambda m:'en '+str(numero(m[1]))+' '+m[2],n)
    n=re.sub(r'\ben\s+(\d+)\s+semanas?\b',lambda m:'en '+str(int(m[1])*7)+' dias',n)
    n=re.sub(r'^('+NUMERO+r')(?=\s+de\s+)',lambda m:str(numero(m[1])),n)
    hora=re.search(r'\ba las?\s+('+NUMERO+r')(?:\s+(y media|y cuarto|menos cuarto))?',n)
    if hora and n[hora.end():hora.end()+1]!=':':
        h=numero(hora[1]);minuto={'y media':30,'y cuarto':15,'menos cuarto':45}.get(hora[2],0)
        if hora[2]=='menos cuarto':h-=1
        n=n[:hora.start()]+f'a las {h:02d}:{minuto:02d}'+n[hora.end():]
    return n
