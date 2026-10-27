"""Conserva rondas y separa acierto bruto, arnés corregido y presentación final."""
import json
import os
from pathlib import Path
import tempfile
from evaluar_corpus_nuevo import comprobar
from formato_literales import presentar

def main():
    p=Path('/home/usuario/Jarvis/registros/reportes/ampliacion_20261014')
    def filas(n):return [json.loads(l) for l in (p/(n+'.jsonl')).read_text().splitlines() if l]
    original=filas('casos_nuevos');corpus=json.loads((p/'corpus_1200_revision_tipos_v2.json').read_text());casos={(x['contexto'],x['id']):x for x in corpus['casos']}
    d={(x['contexto'],x['id']):dict(x,raw_primer_ok=x['primer_ok'],rondas=[]) for x in original}
    arnes=json.loads((p/'android_arnes_corregido.json').read_text())
    for x in arnes['casos']:
        r=d['android',x['id']];r['primer_ok']=x['primer_ok'];r['final_ok']=x['alguno_ok'];r['rondas'].append('arnes_corregido_sin_nueva_respuesta')
    python=filas('python_tras_negacion')
    with tempfile.TemporaryDirectory(prefix='jarvis-recalificar-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        for x in python:
            oks=[]
            for i,intento in enumerate(x['intentos']):
                try:oks.append(bool(comprobar(intento['respuesta'],casos['python',x['id']],Path(tmp)/f'py{x["id"]}_{i}')))
                except Exception:oks.append(False)
            r=d['python',x['id']];r['modelo_tras_controlador_primer_ok']=bool(oks and oks[0]);r['final_ok']=any(oks);r['rondas'].append('python_negacion_corregida_y_tipos_v2')
        for n in ['python_revision_contratos','sql_revision','java_revision','android_revision','ubuntu_revision','entrenamiento_revision','java_acotar','entrenamiento_pendientes','java_deteccion']:
            if not (p/(n+'.jsonl')).exists():continue
            for x in filas(n):
                r=d[x['contexto'],x['id']];r['final_ok']=r['final_ok'] or any(t['ok'] for t in x['intentos']);r['rondas'].append(n)
                if x['contexto']=='entrenamiento':
                    oks=[]
                    for i,t in enumerate(x['intentos']):
                        texto=presentar(x['pedido'],t['respuesta'])
                        try:oks.append(bool(comprobar(texto,casos[x['contexto'],x['id']],Path(tmp)/f'ent{x["id"]}_{i}')))
                        except Exception:oks.append(False)
                    r['presentacion_final_ok']=any(oks)
    salida={'casos':1200,'primer_intento':sum(x['raw_primer_ok'] for x in d.values()),'primer_arnes_corregido':sum(x['primer_ok'] for x in d.values()),'final':sum(x['final_ok'] for x in d.values()),'final_presentacion':sum(x['final_ok'] or x.get('presentacion_final_ok',False) for x in d.values()),'criterio':'Primer intento bruto conserva el fallo de controlador Python y el arnés Kotlin defectuoso. Corrección del arnés no genera respuestas nuevas. Final es existencia de un intento aprobado conservado, no éxito de cada último intento ni garantía futura. Presentación añade solo la etiqueta literal del usuario, sin modificar el texto semántico. Rondas y corpus no se suman como casos diferentes.','contextos':{}}
    for c in ['python','sql','java','android','ubuntu','entrenamiento']:
        rs=[x for x in d.values() if x['contexto']==c]
        salida['contextos'][c]={'casos':len(rs),'primer_bruto':sum(x['raw_primer_ok'] for x in rs),'primer_arnes_corregido':sum(x['primer_ok'] for x in rs),'modelo_tras_controlador':sum(x.get('modelo_tras_controlador_primer_ok',False) for x in rs) if c=='python' else None,'final_bruto':sum(x['final_ok'] for x in rs),'final_presentacion':sum(x['final_ok'] or x.get('presentacion_final_ok',False) for x in rs),'fallos_ids':[x['id'] for x in rs if not (x['final_ok'] or x.get('presentacion_final_ok',False))]}
    (p/'consolidado_final.json').write_text(json.dumps(salida,ensure_ascii=False,indent=2)+'\n')
    (p/'casos_consolidados.json').write_text(json.dumps(list(d.values()),ensure_ascii=False,indent=2)+'\n');print(json.dumps(salida['contextos'],ensure_ascii=False))
if __name__=='__main__':main()
