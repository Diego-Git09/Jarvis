"""Evalúa intérprete y Qwen con datos temporales, sin nube ni captura de memoria."""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reporte',type=Path,required=True);p.add_argument('--sin-modelo',action='store_true');args=p.parse_args()
    os.environ['JARVIS_PRUEBAS']='1'
    with tempfile.TemporaryDirectory(prefix='jarvis-vocabulario-eval-') as tmp:
        os.environ['JARVIS_DIR']=tmp
        import jarvis_agente as J
        import recordatorios_jarvis as R
        import interfaz_recordatorios as I
        from prueba_vocabulario_personal import corpus
        resultados=[]
        for c in corpus():
            inicio=time.monotonic();estado={};antes=len(R.listar());permisos=[]
            hecho,texto=I.comando(c['pedido'],estado,lambda t:permisos.append(t) or True)
            items=R.listar();r=items[-1] if len(items)==antes+1 else {}
            ok=hecho and r.get('texto')==c['texto'] and r.get('evento')==c['evento'] and r.get('fecha')==c['aviso']
            resultados.append({'pedido':c['pedido'],'ruta':'intérprete','ok':ok,'permisos':len(permisos),'segundos':round(time.monotonic()-inicio,3)})
        if not args.sin_modelo:
            casos=[
                ('Oye socio, tengo control de historia el 25 de octubre a las diez. ¿Me dejai algo en el escritorio que avise un par de días antes?',True,'2026-10-25','2026-10-23'),
                ('Quiero que el 25 de octubre sea el día de mi examen, pero verlo desde el 23 de octubre en el escritorio.',True,'2026-10-25','2026-10-23'),
                ('Hazme una nota flotante para un examen el 25 de octubre; que salga dos días antes.',True,'2026-10-25','2026-10-23'),
                ('Mi prueba es el 25 de octubre; la quiero visible en el desktop desde dos días antes.',True,'2026-10-25','2026-10-23'),
                ('No crees nada: estoy preguntando si puedes avisarme dos días antes de una prueba.',False,None,None),
            ]
            for pedido,crea,evento,aviso in casos:
                estado={};h=[{'role':'system','content':J.prompt_para_turno(pedido,estado)},{'role':'user','content':pedido}];antes=len(R.listar());permisos=[];inicio=time.monotonic()
                try:
                    confirmar=lambda t:permisos.append(t) or True
                    manejado,texto=I.comando(pedido,estado,confirmar)
                    if not manejado:texto=J.ejecutar_turno(h,J.enviar_a_ollama,confirmar,estado,mostrar=lambda _:None)
                    nuevos=R.listar()[antes:];r=nuevos[0] if len(nuevos)==1 else {}
                    ok=(len(nuevos)==1 and (r.get('evento') or '')[:10]==evento and (r.get('fecha') or '')[:10]==aviso) if crea else not nuevos and not permisos
                    fila={'pedido':pedido,'ruta':'intérprete' if manejado else 'qwen3:8b','ok':ok,'respuesta':texto,'permisos':len(permisos),'evento':r.get('evento'),'aviso':r.get('fecha'),'segundos':round(time.monotonic()-inicio,2),'estadisticas':{} if manejado else dict(J.ESTADISTICAS)}
                except Exception as e:fila={'pedido':pedido,'ruta':'qwen3:8b','ok':False,'error':str(e),'segundos':round(time.monotonic()-inicio,2)}
                resultados.append(fila);print(json.dumps(fila,ensure_ascii=False),flush=True)
                args.reporte.parent.mkdir(parents=True,exist_ok=True);args.reporte.write_text(json.dumps(resultados,ensure_ascii=False,indent=2)+'\n')
        args.reporte.parent.mkdir(parents=True,exist_ok=True);args.reporte.write_text(json.dumps(resultados,ensure_ascii=False,indent=2)+'\n')
        print(f"{sum(r['ok'] for r in resultados)}/{len(resultados)} casos correctos",flush=True)
        return 0 if all(r['ok'] for r in resultados) else 1


if __name__=='__main__':raise SystemExit(main())
