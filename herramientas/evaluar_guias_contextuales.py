"""Veinte seguimientos reales con Qwen y un documento sintético local."""
import copy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import tempfile
import zipfile

VARIANTES=['haceme una guia de como hacerlo','hazme una guía de cómo hacerlo','hace una guia paso a paso',
 'armame un instructivo','me lo explicas paso a paso','ahora dame los pasos','dame un tutorial',
 'por donde empiezo','cómo empiezo','que hago primero','ayudame con esto','explicame esto',
 'me explicas eso','pasamelo a una guia para implementarlo','guía completa de ese caso',
 'quiero una guia detallada','necesito un paso a paso','preparame una guia completa','mas detallado','sigamos']


def main():
    salida=Path('registros/reportes/guias_contextuales_2026-10-14.json').resolve();filas=[];llamadas=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-guias-contextuales-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1')
        import jarvis_agente as J
        import adjuntos_jarvis as A
        import seguimiento_conversacion as S
        import cliente_ollama as O
        from entorno_jarvis import TRABAJO
        TRABAJO.mkdir(exist_ok=True);fuente=TRABAJO/'Tienda_Ejemplo.docx'
        texto=('Caso Tienda Ejemplo: desarrollar una aplicación Android para registrar entradas por CUATRO accesos. '
               'Requisitos: registrar número de acceso, fecha y hora; distinguir compradores de personas en tránsito; '
               'mostrar un resumen de conteos por acceso. Solo datos ficticios. Entrega: MVP y explicación del código. '
               'Kotlin, Compose y Room son propuestas posibles, no tecnologías obligatorias del enunciado. '
               'Spring Boot y un backend no son requisitos obligatorios; no inventar credenciales ni conexiones a sistemas reales.')
        with zipfile.ZipFile(fuente,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'+texto+'</w:t></w:r></w:p></w:body></w:document>')
        class SinCerebro:
            def llamar(self,*_a,**_k):raise ConnectionError('La evaluación no accede a Segundo Cerebro.')
        J.CEREBRO=SinCerebro();original=O.solicitar
        def real(endpoint,payload,**kw):
            r=original(endpoint,payload,**kw);llamadas.append({'modelo':payload.get('model'),'entrada':r.get('prompt_eval_count'),'salida':r.get('eval_count')});return r
        O.solicitar=real;J.OPCIONES['num_predict']=1400;J.AJUSTES['num_predict']=1400
        estado={};A.recordar_referencia([A.leer_adjunto(fuente)],estado)
        h=[{'role':'system','content':J.prompt_para_turno('explicame esto',estado)},{'role':'user','content':'explicame esto'}]
        primera=J.ejecutar_turno(h,J.enviar_a_ollama,lambda _:False,estado,mostrar=lambda _:None)
        for i,pedido in enumerate(VARIANTES):
            historia=copy.deepcopy(h);e=copy.deepcopy(estado);historia[0]['content']=J.prompt_para_turno(pedido,e);historia.append({'role':'user','content':pedido})
            inicio=len(llamadas)
            try:
                respuesta=J.ejecutar_turno(historia,J.enviar_a_ollama,lambda _:False,e,mostrar=lambda _:None)
                n=respuesta.casefold()
                olvido=any(x in n for x in ['¿de qué tema','de que tema','qué tema quieres','cocinar, programar','qué es lo que quieres hacer'])
                ok=bool(respuesta) and not olvido and any(x in n for x in ['acceso','tienda ejemplo','compradores','tránsito','transito']) and not any(m.get('role')=='tool' and m.get('tool_name') in J.SENSIBLES|J.REQUIEREN_PERMISO for m in historia[len(h):])
                error='' if ok else 'Perdió el referente o propuso una escritura al pedir explicación.'
            except Exception as exc:respuesta='';ok=False;error=type(exc).__name__+': '+str(exc)
            filas.append({'caso':i,'pedido':pedido,'respuesta':respuesta,'ok':ok,'error':error,'llamadas_reales':len(llamadas)-inicio})
            resumen={'fecha':datetime.now(timezone.utc).isoformat(),'modelo':'qwen3:8b','casos':len(filas),'correctos':sum(f['ok'] for f in filas),'fallidos':sum(not f['ok'] for f in filas),'llamadas_reales':len(llamadas),'primera_explicacion':primera,'resultados':filas,'alcance':'Controlador real, lector DOCX real, Qwen local. Un caso ficticio con veinte seguimientos que parten de la explicación inicial; no veinte proyectos. Confirmación de escritura denegada; SC y nube bloqueados.'}
            salida.write_text(json.dumps(resumen,ensure_ascii=False,indent=2));print(json.dumps({'casos':len(filas),'correctos':resumen['correctos'],'fallidos':resumen['fallidos']}),flush=True)
    return 0 if all(f['ok'] for f in filas) else 1

if __name__=='__main__':raise SystemExit(main())
