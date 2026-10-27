"""Contadores de uso local. No guarda preguntas, respuestas ni comentarios."""
import fcntl, json, os, re, unicodedata
from datetime import datetime,timezone
from entorno_jarvis import DATOS
from conversaciones_jarvis import _atomic

ARCHIVO=DATOS/'metricas_modelos.json'
MODELOS={'qwen3:8b','jarvis-deepseek:8b','deepseek-r1:8b'}
REGLAS={'consulta','comando','saludo','adjuntos','analisis','programacion','texto_extenso','continuacion','respaldo_local','manual','escalado'}
def _segura():
    if ARCHIVO.is_symlink() or any(p.is_symlink() for p in ARCHIVO.parents):raise ValueError('Ruta de métricas no segura')
def leer():
    _segura()
    try:
        if ARCHIVO.stat().st_size>200000:raise ValueError('Métricas demasiado grandes')
        d=json.loads(ARCHIVO.read_text())
    except FileNotFoundError:return {'version':1,'grupos':{}}
    if not isinstance(d,dict) or set(d)!={'version','grupos'} or d['version']!=1 or not isinstance(d['grupos'],dict):raise ValueError('Métricas dañadas')
    for k,v in d['grupos'].items():
        if not re.fullmatch(r'(?:simple|media|compleja|otra)\|[a-z_]+\|(?:qwen3:8b|jarvis-deepseek:8b|deepseek-r1:8b|otro)',k):raise ValueError('Grupo inválido')
        if not isinstance(v,dict) or set(v)!={'respuestas','segundos','quejas','escalados','fecha'} or any(type(v[x]) is not int or v[x]<0 for x in ('respuestas','quejas','escalados')) or type(v['segundos']) not in {int,float} or not 0<=v['segundos']<=1e12 or not re.fullmatch(r'\d{4}-\d\d-\d\dT[0-9:.+\-Z]+',str(v['fecha'])):raise ValueError('Contador inválido')
    return d
def _actualizar(fn):
    _segura();ARCHIVO.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=ARCHIVO.with_suffix('.lock');fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as f:
        fcntl.flock(f,fcntl.LOCK_EX);d=leer();fn(d);_atomic(ARCHIVO,d)
def registrar(estado,decision,segundos):
    estado.pop('_metricas_ultimo',None)
    if decision.get('sin_inferencia'):return
    clase=decision.get('clase');clase=clase if clase in {'simple','media','compleja'} else 'otra'
    regla=decision.get('regla');regla=regla if regla in REGLAS else 'manual'
    modelo=decision.get('modelo');modelo=modelo if modelo in MODELOS else 'otro'
    clave='|'.join((clase,regla,modelo))
    def cambio(d):
        v=d['grupos'].setdefault(clave,{'respuestas':0,'segundos':0,'quejas':0,'escalados':0,'fecha':''})
        v['respuestas']+=1;v['segundos']=round(v['segundos']+max(0,min(float(segundos),3600)),3);v['fecha']=datetime.now(timezone.utc).isoformat()
    try:_actualizar(cambio);estado['_metricas_ultimo']=clave
    except (OSError,ValueError,TypeError):estado['_metricas_error']='No se pudieron guardar los contadores; datos anteriores conservados.'
def entrada(p,estado):
    clave=estado.pop('_metricas_ultimo',None)
    if not clave:return
    n=''.join(x for x in unicodedata.normalize('NFD',p.strip().casefold()) if unicodedata.category(x)!='Mn')
    campo='escalados' if n=='/escalar' else 'quejas' if re.match(r'^(?:no entendi|no entiendo|esta mal|eso esta mal|la respuesta esta mal|respuesta incompleta|me diste la respuesta incompleta)(?:\s|[.!?,]|$)',n) else None
    if not campo:return
    def cambio(d):
        if clave in d['grupos']:d['grupos'][clave][campo]+=1
    try:_actualizar(cambio)
    except (OSError,ValueError,TypeError):estado['_metricas_error']='No se pudo guardar la señal de revisión.'
def presentar():
    try:d=leer()
    except (OSError,ValueError):return 'No pude leer los contadores. Conservé el archivo; no cambié reglas.'
    lineas=['Estadísticas locales por categoría, regla y modelo. Solo cuentan inferencias del agente registradas desde esta mejora; no incluyen rondas anteriores. Una queja es una señal, no una evaluación de calidad.']
    for k,v in sorted(d['grupos'].items()):
        lineas.append(f"{k}: {v['respuestas']} respuestas; promedio {v['segundos']/max(1,v['respuestas']):.2f} s; quejas inmediatas {v['quejas']}; /escalar {v['escalados']}.")
        if v['respuestas']>=5 and v['quejas']>=3 and v['quejas']/v['respuestas']>=.3:
            lineas.append('Propuesta: comparar los dos modelos locales para esta categoría en un banco nuevo. No se cambió el enrutador.')
    if not d['grupos']:lineas.append('Todavía no hay inferencias registradas.')
    return '\n'.join(lineas)+'\nNo se guardan textos. Las marcas de /revisar_respuestas se mantienen aparte.'
