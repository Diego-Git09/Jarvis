"""Cien turnos reales en Ollama y persistencia sintética; nunca publica memorias."""
import json
import os
from pathlib import Path
import tempfile
import time

def main():
    destino=Path('/home/usuario/Jarvis/registros/reportes/ampliacion_20261014/resistencia_modelo_100.json')
    with tempfile.TemporaryDirectory(prefix='jarvis-resistencia-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        import cliente_ollama as O
        import jarvis_agente as J
        from conversaciones_jarvis import _atomic
        p=Path(tmp)/'historial.json';historial=[];resultados=[];inicio=time.monotonic()
        for i in range(100):
            pedido=f'Turno sintético {i}. Devuelve únicamente PRUEBA_{i}. No uses herramientas.'
            historial.append({'role':'user','content':pedido})
            r=O.solicitar('/api/chat',{'model':'qwen3:8b','stream':False,'think':False,'messages':[{'role':'system','content':J.prompt_para_turno(pedido)}]+historial[-20:],'options':{'num_ctx':8192,'num_predict':32,'temperature':0}},timeout=60)
            texto=r['message']['content'];historial.append({'role':'assistant','content':texto})
            resultados.append({'turno':i,'ok':texto.strip()==f'PRUEBA_{i}','respuesta':texto})
            _atomic(p,historial)
            if i==49:
                anterior=historial;historial=json.loads(p.read_text());assert historial==anterior
        restaurado=json.loads(p.read_text());assert restaurado==historial and len(restaurado)==200
        destino.write_text(json.dumps({'turnos':100,'mensajes_persistidos':200,'reapertura_turno':50,'reapertura_sin_perdidas':True,'modelo':'qwen3:8b','criterio':'Literal actual exacto; persistencia de todas las preguntas/respuestas. No mide recuerdo semántico de 100 turnos en contexto limitado.','aciertos':sum(x['ok'] for x in resultados),'segundos':round(time.monotonic()-inicio,2),'resultados':resultados},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
