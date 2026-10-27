"""Admisión conservadora de cargas locales. Nunca administra otros programas."""
from pathlib import Path
import subprocess
import re
import time
import threading
import queue
import json
from datetime import datetime,timezone
from cache_recursos import breve,invalidar as invalidar_lecturas

MIB=1024**2
GIB=1024**3
AVISOS=queue.SimpleQueue()
_REGISTRO={}
_CONFIGURACIONES={}
_LOCK=threading.Lock()
_VIGILANTE=None
_VACIANDO_HASTA=0.0
_ULTIMO_AVISO=None


@breve(lambda:Path.read_text)
def ram():
    d={}
    for l in Path('/proc/meminfo').read_text().splitlines():
        k,v=l.split(':',1)
        if k in {'MemTotal','MemAvailable'}:d[k]=int(v.split()[0])*1024
    if set(d)!={'MemTotal','MemAvailable'} or not 0<=d['MemAvailable']<=d['MemTotal']:raise ValueError('RAM sin lectura válida')
    return {'total':d['MemTotal'],'disponible':d['MemAvailable'],'usada':d['MemTotal']-d['MemAvailable'],'tope':int(d['MemTotal']*.8)}


def _motor_ollama(pid,ruta):
    if '/ollama/' in ruta or Path(ruta).name=='ollama':return True
    # NVIDIA puede abreviar la ruta. Validar el padre evita confundir un
    # servidor llama de otra aplicación con un runner del servicio Ollama.
    if not str(pid).isdigit():return False
    try:
        estado=Path('/proc',str(pid),'status').read_text()
        padre=re.search(r'^PPid:\s*(\d+)',estado,re.M)
        return bool(padre and Path('/proc',padre[1],'comm').read_text().strip()=='ollama')
    except OSError:return False


@breve(lambda:(subprocess.run,Path.glob,Path.read_text))
def procesos():
    nombres=set();pesados=[];propios=set()
    for p in Path('/proc').glob('[0-9]*/comm'):
        try:n=p.read_text().strip().casefold()
        except OSError:continue
        if re.fullmatch(r'(?:steam|lutris|wine(?:64)?|wineserver|steam_app.*)',n):nombres.add(n)
    # El listado compute y la tabla gráfica cubren procesos distintos en
    # algunos controladores; ambos se reutilizan dentro del mismo TTL.
    try:
        r=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        if r.returncode==0:
            for l in r.stdout[:16000].splitlines():
                pid,ruta,uso=(x.strip() for x in l.split(',',2));n=Path(ruta).name
                if _motor_ollama(pid,ruta):propios.add(pid)
                elif uso.isdigit() and int(uso)>2048:pesados.append({'nombre':n,'mib':int(uso)})
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    try:
        r=subprocess.run(['nvidia-smi'],capture_output=True,text=True,timeout=3)
        for l in r.stdout[:32000].splitlines():
            m=re.search(r'\|\s*\d+\s+\S+\s+\S+\s+(\d+)\s+[CG+]+\s+(.+?)\s+(\d+)MiB\s*\|',l)
            if m and int(m[3])>2048:
                nombre=Path(m[2].strip()).name
                if m[1] not in propios and not _motor_ollama(m[1],m[2].strip()) and nombre not in {p['nombre'] for p in pesados}:pesados.append({'nombre':nombre,'mib':int(m[3])})
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    return {'juegos':sorted(nombres),'pesados':pesados}


def instantanea():
    import recursos_ollama
    return {'ram':ram(),'gpu':recursos_ollama.gpu(),'termica':termica(),**procesos()}

@breve(lambda:subprocess.run)
def termica():
    """Sensores opcionales. Umbrales de política, no máximos del fabricante."""
    datos={'temperatura':None,'limite_w':None,'consumo_w':None,'cpu_c':None,'cpu_w':None}
    import recursos_ollama
    gpu=recursos_ollama.gpu()
    for k in ('temperatura','limite_w','consumo_w'):
        valores=[g[k] for g in gpu.get('gpu',[]) if type(g.get(k)) in {int,float}]
        if valores:datos[k]=min(valores) if k=='limite_w' else max(valores)
    try:
        r=subprocess.run(['nvidia-smi','--query-gpu=temperature.gpu,power.limit,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3) if not gpu.get('ok') else None
        filas=[l.split(',') for l in r.stdout.strip().splitlines()] if r is not None and r.returncode==0 else []
        for i,k in enumerate(('temperatura','limite_w','consumo_w')):
            valores=[float(f[i].strip()) for f in filas if len(f)>i and re.fullmatch(r'\d+(?:\.\d+)?',f[i].strip())]
            if valores:datos[k]=min(valores) if k=='limite_w' else max(valores)
    except (OSError,ValueError,subprocess.TimeoutExpired):pass
    try:
        r=subprocess.run(['sensors','-j'],capture_output=True,text=True,timeout=3)
        sensores=json.loads(r.stdout[:100000]) if r.returncode==0 else {}
        temperaturas=[];potencias=[]
        for chip,grupos in sensores.items():
            if not re.search(r'coretemp|k10temp|cpu|zenpower',chip,re.I) or not isinstance(grupos,dict):continue
            for valores in grupos.values():
                if not isinstance(valores,dict):continue
                temperaturas.extend(v for k,v in valores.items() if re.fullmatch(r'temp\d+_input',k) and type(v) in {int,float} and -20<=v<=130)
                potencias.extend(v for k,v in valores.items() if re.fullmatch(r'power\d+_input',k) and type(v) in {int,float} and 0<=v<=500)
        if temperaturas:datos['cpu_c']=max(temperaturas)
        if potencias:datos['cpu_w']=max(potencias)
    except (OSError,ValueError,TypeError,AttributeError,subprocess.TimeoutExpired):pass
    return datos


def diagnostico_termico():
    from politica_termica import leer
    try:u=leer();nota=''
    except (OSError,ValueError):u={'gpu':80,'cpu':90};nota=' · configuración ilegible, umbrales preventivos iniciales'
    t=termica()
    def dato(k,unidad):return str(t[k])+' '+unidad if t.get(k) is not None else 'no disponible'
    return ['• Sensores consultados ahora: GPU '+dato('temperatura','°C')+', consumo '+dato('consumo_w','W')+'; CPU '+dato('cpu_c','°C')+', consumo '+dato('cpu_w','W')+'.',
            f"• Umbrales de Jarvis: GPU {u['gpu']} °C; CPU {u['cpu']} °C"+nota+'.',
            '• Último aviso de recursos en esta sesión: '+(json.dumps(_ULTIMO_AVISO,ensure_ascii=False) if _ULTIMO_AVISO else 'ninguno registrado')]


def estimar(info,opciones,peso_bytes=None):
    """KV f16 + pesos conservadores + margen; no representa una reserva del SO."""
    m=info.get('model_info',{});arq=m.get('general.architecture','')
    parametros=m.get('general.parameter_count',0)
    bloques=m.get(arq+'.block_count',0)
    embedding=m.get(arq+'.embedding_length',0)
    heads=m.get(arq+'.attention.head_count',0)
    kvheads=m.get(arq+'.attention.head_count_kv',heads)
    dim=m.get(arq+'.attention.key_length') or (embedding//heads if heads else 0)
    if not all(type(x) is int and x>0 for x in (parametros,bloques,dim,kvheads)):
        raise ValueError('No pude estimar memoria a partir de los metadatos del modelo; no inicié la carga.')
    # Q4 se aproxima por arriba; otras cuantizaciones y f16 usan un margen mayor.
    cuant=str(info.get('details',{}).get('quantization_level','')).upper()
    bytes_peso=.75 if cuant.startswith(('Q4','IQ4')) else 1.1 if cuant.startswith(('Q5','Q6','Q8')) else 2.1
    calibrado=arq=='qwen3' and 8_000_000_000<=parametros<=8_400_000_000 and cuant.startswith('Q4') and type(peso_bytes) is int and peso_bytes>0
    # Perfil contrastado con /api/ps en 4096/8192 para estos dos Q4 8B.
    # Mantiene 128 MiB de grafo y otros 128 MiB de margen de admisión.
    pesos=int(peso_bytes*(1 if calibrado else 1.03)) if type(peso_bytes) is int and peso_bytes>0 else int(parametros*bytes_peso)
    ctx=opciones.get('num_ctx',8192);capas=opciones.get('num_gpu',-1)
    if type(ctx) is not int or not 512<=ctx<=32768:raise ValueError('Ventana fuera del límite seguro de 512–32768 tokens.')
    if type(capas) is not int or capas < -1 or capas>bloques+1:raise ValueError(f'Este modelo admite hasta {bloques+1} capas para /gpu mixto N.')
    proporcion=1 if capas==-1 else min(1,capas/(bloques+1))
    kv=ctx*bloques*kvheads*dim*4
    return {'capas_modelo':bloques+1,'contexto':ctx,'pesos':pesos,'kv':kv,
            'margen_vram':128*MIB if calibrado else 256*MIB,
            'vram':int((pesos+kv)*proporcion)+((128 if calibrado else 512)*MIB if proporcion else 0),
            'ram':int((pesos+kv)*(1-proporcion))+1024*MIB}


def evaluar(foto,estimacion,residentes=()):
    r=foto['ram'];gpu=foto.get('gpu',{});v=estimacion['vram'];host=estimacion['ram']
    # La RAM del residente ya está incluida en MemAvailable. Solo se descuenta
    # si se mantiene exactamente el contexto y la distribución solicitados.
    host_actual=sum(max(0,m.get('size',0)-m.get('size_vram',0)) for m in residentes)
    vram_actual=sum(m.get('size_vram',0) for m in residentes)
    # Con una carga reutilizable no se vuelven a reservar pesos/KV: PS
    # acredita el mismo contexto/configuración. Sigue exigiendo margen libre.
    vram_nueva=0 if residentes else v
    causas=[]
    from politica_termica import leer
    try:umbrales=leer()
    except (OSError,ValueError):umbrales={'gpu':80,'cpu':90};causas.append('no se pudieron validar los umbrales guardados')
    t=foto.get('termica',{});cpu=t.get('cpu_c')
    if type(cpu) in {int,float} and cpu>=umbrales['cpu']:causas.append(f"temperatura CPU alta según el umbral preventivo de Jarvis ({umbrales['cpu']} °C)")
    proyectada=r['usada']+max(0,host-host_actual)
    if proyectada>r['tope']:causas.append(f"RAM estimada {proyectada/GIB:.1f} GiB supera el tope del 80 % ({r['tope']/GIB:.1f} GiB)")
    if v:
        t=foto.get('termica',{});temperatura=t.get('temperatura');potencia=t.get('limite_w')
        if type(temperatura) in {int,float} and temperatura>=umbrales['gpu']:causas.append(f"temperatura GPU alta según el umbral preventivo de Jarvis ({umbrales['gpu']} °C)")
        if type(potencia) in {int,float} and 0<potencia<40:causas.append('límite de potencia GPU bajo según la política preventiva de Jarvis (menos de 40 W)')
        if gpu.get('ok') and any(type(g.get('uso_porcentaje')) in {int,float} and g['uso_porcentaje']>=85 for g in gpu.get('gpu',[])):
            causas.append('actividad GPU alta (85 % o más); el nombre de un lanzador por sí solo no bloquea')
        if foto.get('pesados'):causas.append('otro proceso usa más de 2 GiB de VRAM')
        if gpu.get('ok'):
            libre=max(g['libre_mib'] for g in gpu['gpu'])*MIB
            if libre < vram_nueva+estimacion.get('margen_vram',256*MIB):causas.append(f'VRAM insuficiente según la estimación: se necesitan {vram_nueva/MIB:.0f} MiB nuevos más margen')
        # Sin lectura NVIDIA, Ollama aún puede usar CPU u otra GPU. El límite
        # RAM considera entonces también la parte que se quería descargar.
        elif proyectada+v>r['tope']:causas.append('GPU sin lectura y la carga completa en RAM superaría el 80 %')
    texto=''
    if causas:
        texto='Carga detenida para cuidar los recursos: '+ '; '.join(causas)+'. No cerré otros programas. Opciones: 1) esperar y decir reintenta; 2) /gpu cpu y reintentar (comprueba RAM y temperatura CPU); 3) /liberar para descargar solo modelos de Jarvis; 4) /contexto 4096 para reducir contexto. Los cambios piden s/n; reducir contexto no enfría el equipo por sí solo.'
    return {'permitido':not causas,'motivos':causas,'aviso':texto,'ram_proyectada':proyectada,'vram_nueva_estimada':vram_nueva,'vram_residente':vram_actual,'estimacion':estimacion}


def residente_reutilizable(m,cuerpo,estimacion):
    if type(m.get('size')) is not int or type(m.get('size_vram')) is not int or not 0<=m['size_vram']<=m['size']:return False
    if m.get('name')!=cuerpo['model'] or m.get('context_length')!=estimacion['contexto']:return False
    capas=cuerpo.get('options',{}).get('num_gpu',-1)
    if capas==0:return not m.get('size_vram')
    if capas in {-1,estimacion['capas_modelo']}:return m.get('size_vram',0)>=.95*m.get('size',1)
    # PS no informa num_gpu. Solo dar crédito a una mezcla pedida con éxito
    # por este proceso, en la misma ventana/contexto; sin inferir capas de RAM.
    return _CONFIGURACIONES.get(cuerpo['model'])==(estimacion['contexto'],capas) and 0<m.get('size_vram',0)<m.get('size',0)


def intercambiar_propio(cliente,cuerpo,foto,ps,estimacion,resultado,plazo_fin):
    """Solo libera nombres propios ante insuficiencia atribuible a sus modelos.

    Ya se está dentro de la reserva de inferencia. PS y sensores se vuelven a
    leer: una descarga solicitada nunca acredita memoria libre por sí sola.
    """
    from configuracion_jarvis import MODELO_PREDETERMINADO,MODELO_BASE_DEEPSEEK,MODELO_COTIDIANO
    propios={MODELO_PREDETERMINADO,MODELO_BASE_DEEPSEEK,MODELO_COTIDIANO}|modelos_propios()
    motivos=resultado['motivos']
    if not (foto.get('gpu',{}).get('ok') and len(motivos)==1 and motivos[0].startswith('VRAM insuficiente')):
        return foto,ps,resultado
    candidatos=[m['name'] for m in ps if m.get('name') in propios and m['name']!=cuerpo['model'] and m.get('size_vram',0)>0]
    if not candidatos or any(m.get('size_vram',0)>0 and m.get('name') not in propios for m in ps):
        return foto,ps,resultado
    fin=min(time.monotonic()+10,plazo_fin) if plazo_fin is not None else time.monotonic()+10
    for nombre in candidatos:
        if time.monotonic()>=fin:return foto,ps,resultado
        cliente.solicitar('/api/generate',{'model':nombre,'keep_alive':0,'stream':False},timeout=max(.01,fin-time.monotonic()))
    while time.monotonic()<fin:
        invalidar_lecturas()
        foto=instantanea()
        ps=cliente.solicitar('/api/ps',timeout=min(3,max(.01,fin-time.monotonic()))).get('models',[])
        reutilizables=[m for m in ps if residente_reutilizable(m,cuerpo,estimacion)]
        resultado=evaluar(foto,estimacion,reutilizables)
        pendientes={m.get('name') for m in ps}&set(candidatos)
        if not pendientes and resultado['permitido']:
            AVISOS.put('Cambio de modelo: descarga de '+', '.join(candidatos)+' comprobada con Ollama; cargaré '+cuerpo['model']+'.')
            resultado['descargados_para_cambio']=candidatos
            return foto,ps,resultado
        if foto.get('pesados') or any(not m.startswith('VRAM insuficiente') for m in resultado['motivos']):break
        time.sleep(min(.2,max(0,fin-time.monotonic())))
    # No dar por descargado un modelo que reapareció mientras se comprobaba.
    if {m.get('name') for m in ps}&set(candidatos):
        resultado=dict(resultado,permitido=False,aviso='No pude comprobar la descarga del modelo anterior. Puede estar compartido con otra aplicación. Espera y di reintenta, o revisa /modelo y /diagnostico.')
    return foto,ps,resultado


def comprobar(cliente,cuerpo,plazo_fin=None):
    """Se llama dentro de la reserva, inmediatamente antes de la inferencia."""
    from entorno_jarvis import en_pruebas
    if en_pruebas() or not cuerpo or not cuerpo.get('model'):return
    if cuerpo.get('keep_alive') in (0,'0') and not cuerpo.get('messages') and not cuerpo.get('prompt') and not cuerpo.get('input'):return
    try:
        foto=instantanea();info=cliente.acreditar_pesos_locales(cuerpo['model'])
        tags=cliente.solicitar('/api/tags',timeout=3).get('models',[])
        peso=next((m.get('size') for m in tags if m.get('name')==cuerpo['model']),None)
        estimacion=estimar(info,cuerpo.get('options',{}),peso)
        ps=cliente.solicitar('/api/ps',timeout=3).get('models',[])
        # No restar un residente que Ollama tendrá que recargar de otra forma.
        residentes=[m for m in ps if residente_reutilizable(m,cuerpo,estimacion)]
        resultado=evaluar(foto,estimacion,residentes)
        foto,ps,resultado=intercambiar_propio(cliente,cuerpo,foto,ps,estimacion,resultado,plazo_fin)
        inicio=time.monotonic()
        fin_transicion=inicio+3
        if plazo_fin is not None:fin_transicion=min(fin_transicion,plazo_fin)
        def transicion_posible():
            # PS puede vaciarse antes de que NVIDIA refleje una descarga.
            # Solo releer: no dar crédito a pesos ausentes ni liberar modelos.
            return (not ps and len(resultado['motivos'])==1 and
                    resultado['motivos'][0].startswith('VRAM insuficiente') and
                    time.monotonic()<fin_transicion)
        # keep_alive=0 puede responder antes de que el controlador NVIDIA
        # refleje la VRAM liberada. También esperar brevemente ante PS vacío.
        while not resultado['permitido'] and not foto.get('pesados'):
            fin_propio=_VACIANDO_HASTA
            if plazo_fin is not None:fin_propio=min(fin_propio,plazo_fin)
            if not transicion_posible() and time.monotonic()>=fin_propio:break
            restante=max(fin_transicion if transicion_posible() else 0,fin_propio)-time.monotonic()
            if restante<=0:break
            time.sleep(min(.2,restante))
            if plazo_fin is not None and time.monotonic()>=plazo_fin:break
            invalidar_lecturas()
            foto=instantanea()
            restante_ps=3 if plazo_fin is None else min(3,max(.01,plazo_fin-time.monotonic()))
            ps=cliente.solicitar('/api/ps',timeout=restante_ps).get('models',[])
            residentes=[m for m in ps if residente_reutilizable(m,cuerpo,estimacion)]
            resultado=evaluar(foto,estimacion,residentes)
        resultado['espera_coherencia_s']=round(time.monotonic()-inicio,3)
    except (OSError,ValueError) as e:
        raise cliente.ErrorOllama('No pude comprobar recursos antes de cargar: '+str(e),tipo='recursos') from e
    if not resultado['permitido']:
        global _ULTIMO_AVISO
        _ULTIMO_AVISO={'fecha':datetime.now(timezone.utc).isoformat(),'gpu_c':foto.get('termica',{}).get('temperatura'),'cpu_c':foto.get('termica',{}).get('cpu_c'),'motivos':len(resultado['motivos'])}
        error=cliente.ErrorOllama(resultado['aviso'],tipo='recursos');error.recursos={'lectura':foto,'evaluacion':resultado,'residentes_ollama':ps}
        raise error
    return resultado


def registrar(cliente,cuerpo):
    from entorno_jarvis import en_pruebas
    if en_pruebas() or not cuerpo or not cuerpo.get('model'):return
    invalidar_lecturas()
    valor=str(cuerpo.get('keep_alive','5m'))
    m=re.fullmatch(r'(\d+)(ms|s|m|h)?',valor)
    if not m:return
    segundos=int(m[1])*{None:1,'ms':.001,'s':1,'m':60,'h':3600}[m[2]]
    global _VIGILANTE,_VACIANDO_HASTA
    if segundos==0:_VACIANDO_HASTA=time.monotonic()+10
    if segundos==0 and not cuerpo.get('messages') and not cuerpo.get('prompt') and not cuerpo.get('input'):
        # /liberar ya entrega su comprobante; no repetirlo como reposo.
        with _LOCK:
            _REGISTRO.pop(cuerpo['model'],None);_CONFIGURACIONES.pop(cuerpo['model'],None)
        return
    with _LOCK:
        _REGISTRO[cuerpo['model']]=time.monotonic()+segundos
        if segundos==0:_CONFIGURACIONES.pop(cuerpo['model'],None)
        else:
            opciones=cuerpo.get('options',{})
            if 'num_ctx' in opciones:_CONFIGURACIONES[cuerpo['model']]=(opciones['num_ctx'],opciones.get('num_gpu',-1))
        if _VIGILANTE is None or not _VIGILANTE.is_alive():
            _VIGILANTE=threading.Thread(target=_vigilar,args=(cliente,),daemon=True);_VIGILANTE.start()


def comprobar_reposo(cliente,ahora=None):
    ahora=time.monotonic() if ahora is None else ahora
    with _LOCK:vencidos={n:t for n,t in _REGISTRO.items() if ahora>=t}
    if not vencidos:return []
    try:
        modelos=cliente.solicitar('/api/ps',timeout=3).get('models')
        if not isinstance(modelos,list) or any(not isinstance(m,dict) or not isinstance(m.get('name'),str) for m in modelos):return []
        cargados={m['name'] for m in modelos}
    except (OSError,ValueError):return []
    avisos=[]
    with _LOCK:
        for n,t in vencidos.items():
            if n not in cargados and _REGISTRO.get(n)==t:
                _REGISTRO.pop(n,None);_CONFIGURACIONES.pop(n,None);avisos.append('Reposo: '+n+' descargado de memoria, comprobado con Ollama. Sus archivos siguen instalados.')
    for a in avisos:AVISOS.put(a)
    return avisos


def _vigilar(cliente):
    global _VIGILANTE
    while True:
        time.sleep(2)
        comprobar_reposo(cliente)
        with _LOCK:
            if not _REGISTRO:
                _VIGILANTE=None;return


def modelos_propios():
    with _LOCK:return set(_REGISTRO)


def consumir_avisos():
    salida=[]
    while True:
        try:salida.append(AVISOS.get_nowait())
        except queue.Empty:return salida
