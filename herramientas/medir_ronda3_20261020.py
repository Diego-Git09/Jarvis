"""Cuarenta peticiones congeladas; clientes importados solo dentro del temporal."""
from pathlib import Path
import medir_seleccion_20261020 as M
M.DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda3_20261020'

def preparar_espera():
    import sys,time,json
    if '--esperar-recursos' not in sys.argv:return
    sys.argv.remove('--esperar-recursos')
    ronda=sys.argv[sys.argv.index('--ronda')+1]
    log=M.DESTINO/(ronda+'_esperas.jsonl')
    if log.exists():raise ValueError('No sobrescribir auditoría de esperas')
    def instalar():
        # Este hook se llama después de fijar JARVIS_DIR y antes del agente.
        import cliente_ollama as O
        real=O.solicitar
        def esperar(ruta,cuerpo=None,**kw):
            inicio=time.monotonic();numero=0
            while True:
                try:return real(ruta,cuerpo,**kw)
                except O.ErrorOllama as e:
                    if e.tipo!='recursos' or ruta!='/api/chat' or time.monotonic()-inicio>310:raise
                    numero+=1
                    with log.open('a') as f:f.write(json.dumps({'modelo':(cuerpo or {}).get('model'),'tipo':'rechazo previo a cargar','numero':numero,'segundos_esperando':round(time.monotonic()-inicio,2),'error':str(e)},ensure_ascii=False)+'\n')
                    time.sleep(3)
        O.solicitar=esperar
    M.ANTES_DE_CLIENTE=instalar

if __name__=='__main__':
    preparar_espera();M.main()
