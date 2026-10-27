"""Vista de intención separada del original. Nunca devuelve argumentos ejecutables."""
from dataclasses import dataclass
from pathlib import Path
import json
import re
import unicodedata

BASE=Path(__file__).with_name('lexico_intencion.json')
PROTEGIDO=re.compile(r'```[\s\S]*?```|`[^`\n]*`|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|«[^»]*»|“[^”]*”|(?:https?://|/|~/|[A-Za-z]:\\)\S+|\b[\w.-]+\.(?:py|sql|txt|md|json|csv|java|kt|pdf|docx|xlsx|sh)\b')

def plegar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD',texto.casefold()) if unicodedata.category(c)!='Mn')

def lexico():
    try:
        d=json.loads(BASE.read_text())
        if not isinstance(d,list) or len(d)>1500:raise ValueError('Léxico inválido')
        resultado={plegar(x['forma']):x for x in d if isinstance(x,dict) and isinstance(x.get('forma'),str) and isinstance(x.get('significado'),(str,list))}
        from confirmar_vocabulario import leer
        try:confirmaciones=leer()
        except (OSError,ValueError,TypeError):confirmaciones={}
        for forma,confirmacion in confirmaciones.items():
            if forma in resultado:resultado[forma]=dict(resultado[forma],origen=confirmacion['estado'],evidencia_uso=confirmacion.get('evidencia',''),segura=True if confirmacion['estado']=='observado' and isinstance(resultado[forma]['significado'],str) else resultado[forma].get('segura',True))
        return resultado
    except (OSError,ValueError,KeyError):return {}

@dataclass(frozen=True)
class Entrada:
    original:str
    vista:str
    cambios:tuple
    dudas:tuple

def analizar(texto,personal=True):
    if not isinstance(texto,str):raise TypeError('La entrada debe ser texto')
    datos=lexico()
    if personal:
        from vocabulario_privado import leer
        datos.update({k:{'significado':v,'segura':True} for k,v in leer().items()})
    cambios=[];dudas=[]
    def tramo(t):
        n=plegar(t)
        # Segmentación limitada y comprobable, no adivina nombres ni código.
        for a,b in {'holajarvis':'hola jarvis','puedesconsultar':'puedes consultar','puedesrevisar':'puedes revisar','quieroque':'quiero que','muestrameel':'muestrame el'}.items():
            n=re.sub(r'\b'+a+r'\b',b,n)
        # Un puñado de frases pegadas completas; no segmentar nombres desconocidos.
        for a,b in {'consultasegundocerebro':'consulta segundo cerebro','consultaelestado':'consulta el estado','perfectoautorizado':'perfecto autorizado','empecemosconel':'empecemos con el'}.items():n=re.sub(r'\b'+a+r'\b',b,n)
        n=re.sub(r'\b2do\b','segundo',n)
        def palabra(m):
            p=m[0];base=re.sub(r'(.)\1{2,}',r'\1',p)
            if p not in datos and base in {'hola','si','no','gracias','listo','perfecto','dale'}:p=base
            elif re.fullmatch(r'si+',p):p='si'
            x=datos.get(p)
            if x:
                if x.get('segura',True):
                    destino=plegar(x['significado'])
                    if destino!=m[0]:cambios.append((m[0],destino))
                    return destino
                dudas.append((p,tuple(x['significado']) if isinstance(x['significado'],list) else x['significado']))
            return p
        n=re.sub(r'\b[a-zñ]+\b',palabra,n)
        n=re.sub(r'(?<=\d)(?=(?:gb|mb|wts|watts|w|c|hx)\b)', ' ',n)
        n=re.sub(r'\brtx(?=\d)','rtx ',n)
        n=re.sub(r'\b(\d+)\s*gb\s*ram\b',r'\1 gb ram',n)
        return re.sub(r'\s+',' ',n)
    salida=[];inicio=0
    for m in PROTEGIDO.finditer(texto):
        salida.extend((tramo(texto[inicio:m.start()]),' '+m[0]+' '));inicio=m.end()
    salida.append(tramo(texto[inicio:]))
    vista=''.join(salida).strip()
    # Un verbo cercano desconocido solo genera opciones; jamás una corrección
    # automática ejecutable. El léxico español evita confundir «creo» con «crea».
    primera=re.match(r'^(?:(?:jarvis|por favor|puedes|podrias|quiero que|necesito que)[, ]+)*(\w+)',vista)
    if primera:
        p=primera[1]
        comunes={'creo','crees','puedo','puedes','podrias','hola','si','no','como','que','cual','cuando','donde','por','porque','quiero','necesito','tengo','estoy','esto','eso','el','la','un','una','me','mi','ya','perfecto','gracias','ayuda','guia','modelo','supongamos','explicame','analiza','responde','usa','hazme','dime','se','es'}
        verbos={'borra','crea','copia','mueve','renombra','edita','modifica','guarda','elimina','corrige','ejecuta','instala','actualiza','reinicia'}
        def distancia_uno(a,b):
            if abs(len(a)-len(b))>1:return False
            if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
            corto,largo=(a,b) if len(a)<len(b) else (b,a)
            return any(largo[:i]+largo[i+1:]==corto for i in range(len(largo)))
        if len(p)>=4 and p not in comunes|verbos and p not in datos:
            candidatos=sorted(v for v in verbos if distancia_uno(p,v))
            if candidatos:dudas.append((p,tuple(candidatos[:2]+['otra acción'])))
    return Entrada(texto,vista,tuple(cambios),tuple(dict.fromkeys(dudas)))

def vista(texto):return analizar(texto).vista

def aclaracion(entrada):
    if not entrada.dudas:return ''
    palabra,opciones=entrada.dudas[0]
    if palabra=='fome':return '¿Con «fome» te refieres a que va lento o a que te resulta poco interesante? /confirmar_vocabulario permite confirmar tu uso; todavía no cambié nada.'
    if isinstance(opciones,str):opciones=[opciones,'otro significado']
    return 'Entendí una petición con «'+palabra+'», pero su significado no es seguro. ¿Es así?\n'+'\n'.join(f'{i}. {v}' for i,v in enumerate(opciones[:3],1))+'\nEscribe la petición completa con la opción elegida; todavía no preparé cambios.'

def permiso_claro(respuesta):
    # No se normalizan errores ni frases compuestas para otorgar permisos.
    return plegar(respuesta).strip(' .!') in {'s','si','dale','ok','listo','autorizado','autorizo','confirmo','adelante','de acuerdo'}
