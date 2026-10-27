"""Mediciones comparables con preguntas sintéticas; no ejecuta herramientas ni captura chats."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import threading
import time

CASOS = [
 ('calculo','Dime solo el resultado de 15 por ciento de 200.',r'\b30\b'),
 ('sql','Necesito la cantidad de ventas por zona, no sumar montos. ¿COUNT o SUM? Explica en una línea.',r'(?i)COUNT'),
 ('python','Para frecuencias de palabras Python, ¿Counter(texto) o Counter(texto.split())? Elige y explica.',r'(?i)split'),
 ('java','En Java, contar valores distintos >= 3: ¿filtrar antes de Set o contar posiciones? Explica en una línea.',r'(?i)(filtr|>=\s*3)'),
 ('ubuntu','Comando Ubuntu para mostrar la ruta del directorio actual. Solo el comando.',r'\bpwd\b'),
 ('android','Primeros dos pasos para una app Android Studio nueva sin inventar versiones. Sé breve.',r'(?i)(android|proyecto)'),
 ('guia','Haceme una guía de cómo hacerlo, con dos pasos breves.',r'(?i)(acceso|tienda)'),
 ('memoria','¿Puedes consultar Segundo Cerebro? Distingue tener herramientas de haberlo consultado ahora.',r'(?i)(consult|herramienta)'),
 ('literal','Conserva exactamente CASO_40. Di en una línea que falta verificar los archivos; no cambies la etiqueta.',r'CASO_40'),
 ('fuente','El documento ficticio exige cuatro accesos. ¿Cuántos exige? Responde brevemente sin agregar otros requisitos.',r'(?i)(cuatro|\b4\b)')]

def recursos():
    memoria=Path('/proc/meminfo').read_text()
    valores={k:int(v) for k,v in re.findall(r'^(MemTotal|MemAvailable):\s+(\d+)',memoria,re.M)}
    r={'ram_usada_mib':round((valores['MemTotal']-valores['MemAvailable'])/1024,1)}
    try:
        p=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        if p.returncode==0:
            usadas,total,uso=map(int,p.stdout.splitlines()[0].split(','));r.update(vram_mib=usadas,vram_total_mib=total,gpu_porcentaje=uso)
        else:r['gpu_disponible']=False
    except (OSError,ValueError,subprocess.TimeoutExpired):r['gpu_disponible']=False
    return r

def medir(modelo,ctx,hilos,keep_alive,prompt):
    import cliente_ollama as O
    import protocolo_deepseek as DS
    O.acreditar_pesos_locales(modelo)
    iniciales=O.solicitar('/api/ps').get('models',[])
    resultados=[];muestras=[];terminar=threading.Event()
    def muestrear():
        while not terminar.is_set():
            muestras.append(recursos());terminar.wait(1)
    hilo=threading.Thread(target=muestrear,daemon=True);hilo.start()
    try:
        for nombre,pedido,patron in CASOS:
            mensajes=[{'role':'system','content':prompt}]
            if nombre=='guia':mensajes.extend([{'role':'user','content':'Explica el caso de la tienda'},{'role':'assistant','content':'La tienda necesita una app Android para registrar entradas por cuatro accesos, con fecha y distinción entre compradores y tránsito.'}])
            mensajes.append({'role':'user','content':pedido})
            opciones={'num_ctx':ctx,'num_predict':512,'temperature':0.1}
            if hilos:opciones['num_thread']=hilos
            cuerpo={'model':modelo,'stream':True,'think':False,'keep_alive':keep_alive,'messages':mensajes,'options':opciones}
            estructurado=DS.aplica(modelo)
            if estructurado:cuerpo=DS.preparar(cuerpo)
            inicio=time.monotonic();primero=None;texto='';final={};error=''
            try:
                with O.abrir_flujo_chat(cuerpo,timeout=240) as r:
                    for linea in r:
                        d=json.loads(linea);parte=d.get('message',{}).get('content','')
                        if parte and primero is None:primero=time.monotonic()-inicio
                        texto+=parte
                        if d.get('done'):final=d
                if not final:error='Ollama cerró sin confirmar fin'
                if final and estructurado:texto=DS.interpretar({'message':{'content':texto},'done_reason':final.get('done_reason')},[])['content']
            except Exception as e:error=type(e).__name__
            fila={'caso':nombre,'pedido':pedido,'respuesta':texto,'primer_token_s':primero,'total_s':round(time.monotonic()-inicio,3),'ok':bool(not error and re.search(patron,texto)),'error':error,'tokens_entrada':final.get('prompt_eval_count'),'tokens_salida':final.get('eval_count'),'fin':final.get('done_reason')}
            resultados.append(fila);print(json.dumps({k:v for k,v in fila.items() if k not in {'pedido','respuesta'}},ensure_ascii=False),flush=True)
    finally:terminar.set();hilo.join(4)
    cargados=O.solicitar('/api/ps').get('models',[])
    return {'modelo':modelo,'num_ctx':ctx,'hilos':hilos,'keep_alive':keep_alive,'casos':resultados,'correctos_iniciales':sum(x['ok'] for x in resultados),'muestras':muestras,'vram_max_mib':max((x.get('vram_mib',0) for x in muestras),default=0),'ram_max_mib':max((x['ram_usada_mib'] for x in muestras),default=0),'modelos_cargados':cargados,'modelos_iniciales':iniciales,'modo_gpu':O.leer()[0].get('modo_gpu','auto'),'alcance':'Transporte streaming y prompt de Jarvis; no latencia completa de ejecutar herramientas. Diez peticiones sintéticas con respuesta acotada a 512 tokens y rúbrica fija.'}

def main():
    import configuracion_jarvis as C
    ajustes,aviso=C.leer()
    if aviso:raise ValueError('No pude leer la configuración. Revisa /diagnostico antes de medir.')
    p=argparse.ArgumentParser()
    p.add_argument('--modelo',default=ajustes['modelo']);p.add_argument('--ctx',type=int,default=ajustes['num_ctx'])
    p.add_argument('--hilos',type=int,default=ajustes['hilos']);p.add_argument('--keep-alive',default=ajustes['keep_alive'])
    p.add_argument('--informe',required=True);a=p.parse_args()
    C.validar(dict(ajustes,modelo=a.modelo,num_ctx=a.ctx,hilos=a.hilos,keep_alive=a.keep_alive))
    # Solo reglas del programa, sin preferencias, historial, herramientas ni MCP.
    # Mantiene la instalación para compartir reserva y ajustes de CPU/reposo.
    import prompt_jarvis
    import protocolo_deepseek as DS
    prompt=(DS.BASE if DS.aplica(a.modelo) else prompt_jarvis.BASE)+'\nEsta es una medición sintética sin herramientas. No afirmes acciones ni consultas no realizadas.'
    r=medir(a.modelo,a.ctx,a.hilos,a.keep_alive,prompt)
    dest=Path(a.informe);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
