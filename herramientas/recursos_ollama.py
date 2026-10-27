"""Lecturas de recursos y descarga de RAM/VRAM, sin borrar pesos ni servicios."""
import csv
import io
import subprocess
import time
import re
from cache_recursos import breve


def limitar_reposo(pedido,preferido):
    """Ningún auxiliar puede retener un modelo más que el plazo elegido."""
    def segundos(valor):
        if type(valor) in (int,float):return valor if valor>=0 else float('inf')
        m=re.fullmatch(r'(\d+(?:\.\d+)?)(ms|s|m|h)?',str(valor))
        return float(m[1])*{'ms':.001,'s':1,'m':60,'h':3600,None:1}[m[2]] if m else float('inf')
    return pedido if pedido is not None and segundos(pedido)<=segundos(preferido) else preferido


@breve(lambda:subprocess.run)
def gpu():
    try:
        r=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu,power.limit,power.draw',
                          '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        if r.returncode or len(r.stdout)>16000:return {'ok':False,'error':'NVIDIA no entregó una lectura válida.'}
        filas=[]
        for fila in csv.reader(io.StringIO(r.stdout)):
            if len(fila) not in (4,7):raise ValueError('Columnas inválidas')
            total,usada,libre,uso=(int(c.strip()) for c in fila[:4])
            if min(total,usada,libre,uso)<0 or total==0 or uso>100:raise ValueError('Valores inválidos')
            dato={'total_mib':total,'usada_mib':usada,'libre_mib':libre,'uso_porcentaje':uso}
            if len(fila)==7:
                for clave,valor in zip(('temperatura','limite_w','consumo_w'),fila[4:]):
                    if re.fullmatch(r'\d+(?:\.\d+)?',valor.strip()):dato[clave]=float(valor)
            filas.append(dato)
        return {'ok':bool(filas),'gpu':filas}
    except (OSError,subprocess.TimeoutExpired,ValueError):
        return {'ok':False,'error':'No pude leer NVIDIA; puede faltar el controlador o nvidia-smi. No demuestra que no exista una GPU.'}


def cargados(cliente):
    datos=cliente.solicitar('/api/ps',timeout=3)
    modelos=datos.get('models')
    if not isinstance(modelos,list):raise ValueError('Ollama no entregó la lista de modelos cargados.')
    resultado=[]
    for m in modelos:
        if not isinstance(m,dict) or not isinstance(m.get('name'),str):continue
        r={'nombre':m['name']}
        for campo in ('size','size_vram','context_length'):
            if type(m.get(campo)) is int and m[campo]>=0:r[campo]=m[campo]
        if isinstance(m.get('expires_at'),str):r['expira']=m['expires_at'][:40]
        resultado.append(r)
    return resultado


def plazo(ajustes,modelo,caracteres=0,codigo=False):
    """El límite manual prevalece. El automático amplía tareas costosas, hasta600s."""
    base=ajustes.get('timeout_modelo',120)
    if not ajustes.get('timeout_auto',True):return base
    dinamico=180 if 'deepseek' in modelo.casefold() else 120
    if caracteres>6000:dinamico=max(dinamico,240)
    if codigo:dinamico=max(dinamico,300)
    return min(600,max(base,dinamico))


def esperar_descarga(cliente,nombres,plazo_fin):
    pendientes=set(nombres)
    while pendientes:
        pendientes={m['nombre'] for m in cargados(cliente)}&set(nombres)
        if not pendientes or time.monotonic()>=plazo_fin:break
        time.sleep(min(.2,max(0,plazo_fin-time.monotonic())))
    return pendientes


def liberar(cliente,ajustes,confirmar):
    import configuracion_jarvis as C
    import politica_ia
    politica_ia.comprobar_destino_local(ajustes['modelo'],cliente.BASE)
    if not cliente._TURNO.acquire(blocking=False):
        return 'Hay una inferencia local en curso. Espera a que termine antes de liberar su memoria.'
    try:
        with cliente.reservar(timeout=0):
            from control_recursos import modelos_propios
            candidatos={ajustes['modelo'],C.MODELO_PREDETERMINADO,C.MODELO_BASE_DEEPSEEK,C.MODELO_COTIDIANO}|modelos_propios()
            nombres=[m['nombre'] for m in cargados(cliente) if m['nombre'] in candidatos]
            if not nombres:return 'Los modelos de Jarvis ya están descargados de memoria. Los archivos de los modelos siguen instalados.'
            if not confirmar('Descargar de RAM/VRAM estos modelos: '+', '.join(nombres)+'. Se cargarán de nuevo al consultarlos. Si otra aplicación comparte el mismo modelo, también necesitará recargarlo. No se borrarán archivos.'):
                return 'No descargué los modelos de memoria.'
            plazo_fin=time.monotonic()+20
            for n in nombres:cliente.solicitar('/api/generate',{'model':n,'keep_alive':0,'stream':False},timeout=max(.1,plazo_fin-time.monotonic()))
            restantes=esperar_descarga(cliente,nombres,plazo_fin)
            if restantes:return 'Solicité la descarga, pero siguen cargados: '+', '.join(sorted(restantes))+'. Otra aplicación puede haberlos vuelto a usar; no confirmo memoria liberada.'
            return 'Descarga de memoria comprobada: '+', '.join(nombres)+'. Los modelos siguen instalados y se cargarán cuando los necesites.'
    finally:cliente._TURNO.release()


def lineas_diagnostico(cliente,ajustes):
    import externo_zen
    lineas=['• Procesamiento guardado: '+ajustes.get('modo_gpu','auto')+(' '+str(ajustes.get('capas_gpu',12))+' capas GPU, resto CPU/RAM' if ajustes.get('modo_gpu')=='mixto' else '')+'; /gpu cpu evita descargar capas nuevas a GPU. /api/ps comprueba la carga real.',
            '• Espera del modelo: '+('automática, hasta '+str(plazo(ajustes,ajustes['modelo'],codigo=True))+' s para código' if ajustes.get('timeout_auto',True) else str(ajustes['timeout_modelo'])+' s, límite manual')+'.',
            '• Reposo de modelos: '+ajustes['keep_alive']+' tras cada inferencia; /reposo cambia el plazo y /liberar descarga ahora.']
    import control_recursos
    t=control_recursos.termica()
    from politica_termica import leer as leer_umbrales
    try:umbral=leer_umbrales()['gpu']
    except (OSError,ValueError):umbral=80
    lineas.append('• Sensores: temperatura '+(str(t['temperatura'])+' °C' if t.get('temperatura') is not None else 'sin lectura')+'; límite de potencia '+(str(t['limite_w'])+' W' if t.get('limite_w') is not None else 'sin lectura')+f'. Jarvis avisa desde {umbral} °C o límite inferior a 40 W; no cambia ventiladores ni potencia.')
    lineas.append('• IA externa Zen: '+('encendida' if externo_zen.estado()['encendido'] else 'apagada')+'; clave '+('detectada localmente, sin validar con el servicio' if externo_zen.clave() else 'ausente')+'. /externo estado muestra errores. Otros proveedores bloqueados.')
    try:
        r=control_recursos.ram();lineas.append(f"• RAM: {r['usada']/1024**3:.1f}/{r['total']/1024**3:.1f} GiB; admisión de cargas limitada al 80 % ({r['tope']/1024**3:.1f} GiB). Es una estimación, no una reserva del sistema.")
    except (OSError,ValueError):lineas.append('• RAM: lectura no disponible; no se autorizarán nuevas cargas sin comprobarla.')
    try:
        modelos=cargados(cliente)
        lineas.append('• Modelos cargados: '+(', '.join(m['nombre']+' (VRAM '+str(m['size_vram']//(1024**2))+' MiB)' if 'size_vram' in m else m['nombre'] for m in modelos) or 'ninguno')+'.')
    except (OSError,ValueError):lineas.append('• Modelos cargados: lectura no disponible; no significa que estén descargados.')
    g=gpu()
    if g['ok']:
        for i,m in enumerate(g['gpu']):lineas.append(f"• GPU {i}: {m['usada_mib']}/{m['total_mib']} MiB usados; {m['libre_mib']} MiB libres; actividad {m['uso_porcentaje']}%.")
    else:lineas.append('• GPU: '+g['error'])
    return lineas
