"""Estabilidad de sesiones con servidores sintéticos; nunca usa modelos ni memoria."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
import signal
from pathlib import Path
import tempfile
import threading
import time

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duracion',type=float,required=True)
    parser.add_argument('--intervalo',type=float,default=15)
    parser.add_argument('--salida',type=Path,required=True)
    args=parser.parse_args()
    if not 1<=args.duracion<=10800 or not 2<=args.intervalo<=300:parser.error('Duración 1..10800 s, intervalo 2..300 s.')
    inicio=time.monotonic();fin=inicio+args.duracion;resultados=[];fallos=[]
    detener=threading.Event()
    for signo in (signal.SIGINT,signal.SIGTERM):signal.signal(signo,lambda *_:detener.set())
    args.salida.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='jarvis-estabilidad-') as tmp:
        proyecto=Path(tmp)/'Jarvis';proyecto.mkdir()
        os.environ['JARVIS_DIR']=str(proyecto);os.environ['JARVIS_PRUEBAS']='1'
        from aislamiento_pruebas import verificar_previo
        verificar_previo(proyecto,nativo=True,evidencias=args.salida.parent)
        from servicio_ollama import SesionOllama
        from salud_ollama import comprobar
        from soporte_pruebas_servicio import ejecutable,puerto_libre,esperar
        def huella():
            archivos=('servicio_ollama.py','supervisor_ollama.py','salud_ollama.py','lectura_http.py')
            return hashlib.sha256(b''.join(Path(__file__).with_name(x).read_bytes() for x in archivos)).hexdigest()
        fd_inicial=len(list(Path('/proc/self/fd').iterdir()))
        diario=args.salida.with_suffix('.jsonl')
        fd=os.open(diario,os.O_CREAT|os.O_TRUNC|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as log:
            ciclo=0
            while time.monotonic()<fin and not detener.is_set():
                ciclo+=1;antes=time.monotonic();sesiones=[];ok=False;tipo_error=''
                fuente=huella()
                with tempfile.TemporaryDirectory(prefix='ciclo-',dir=proyecto) as t:
                    root=Path(t);url='http://127.0.0.1:'+str(puerto_libre())
                    try:
                        exe=ejecutable(root,fallar=(ciclo%5==0))
                        def nueva(raiz='control'):
                            s=SesionOllama(url,raiz=root/raiz,ejecutable=exe,permitir_pruebas=True)
                            sesiones.append(s);return s
                        a=nueva();r=a.asegurar(timeout=4)
                        if ciclo%5==0:
                            assert not r['ok'],'Un proceso fallido se presentó como disponible'
                        else:
                            assert r['ok'],r
                            b=nueva();assert b.asegurar(timeout=4)['ok']
                            if ciclo%3==0:
                                c=nueva('preexistente');v=c.asegurar(timeout=2)
                                assert v['ok'] and v['gestion']=='preexistente'
                                c.cerrar()
                            a.cerrar();time.sleep(.25)
                            assert comprobar(url,.3)['ok'],'El primer cierre apagó a la otra sesión'
                            b.cerrar()
                        assert esperar(lambda:not comprobar(url,.1)['ok'],timeout=5),'Servidor sintético huérfano'
                        ok=True
                    except Exception as e:
                        tipo_error=type(e).__name__+': '+str(e)[:500]
                    finally:
                        for s in sesiones:s.cerrar()
                        for s in sesiones:
                            p=getattr(s,'_supervisor',None)
                            if p is not None:
                                try:p.wait(timeout=6)
                                except Exception:ok=False;tipo_error='El supervisor no terminó; requiere revisión'
                    fds=len(list(Path('/proc/self/fd').iterdir()))
                    if fds>fd_inicial+2:ok=False;tipo_error='Crecimiento de descriptores: '+str(fds-fd_inicial)
                fila={'ciclo':ciclo,'ok':ok,'segundos':round(time.monotonic()-antes,4),
                      'fd_abiertos':fds,'fd_base':fd_inicial,'fuentes_sha256':fuente,
                      'fuentes_iguales_al_final':fuente==huella(),'error':tipo_error,
                      'categoria':'fallo_de_arranque' if ciclo%5==0 else 'preexistente' if ciclo%3==0 else 'sesiones_compartidas'}
                resultados.append(fila);log.write(json.dumps(fila)+'\n');log.flush()
                if not ok:
                    fallos.append(ciclo);print(json.dumps(fila),flush=True);break
                if ciclo==1 or ciclo%20==0:
                    print(json.dumps({'ciclos':ciclo,'fallos':len(fallos),'transcurrido_s':round(time.monotonic()-inicio),'fd_abiertos':fds}),flush=True)
                pausa=min(args.intervalo-(time.monotonic()-antes),fin-time.monotonic())
                if pausa>0:detener.wait(pausa)
    d={'fecha_utc':datetime.now(timezone.utc).isoformat(),'segundos':round(time.monotonic()-inicio,3),
       'ciclos':len(resultados),'fallos':fallos,'interrumpida':detener.is_set(),'tipo':'procesos y HTTP sintéticos reales; sin modelos ni IA externa',
       'resultados':resultados}
    fd=os.open(args.salida,os.O_CREAT|os.O_TRUNC|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in d.items() if k!='resultados'}),flush=True)
    return 1 if fallos else 0

if __name__=='__main__':raise SystemExit(main())
