"""Contrasta escaneo y FTS5 sobre las mismas fuentes y referencias oro.

Datos sintéticos, búsqueda lexical; no representa calidad vectorial ni del LLM.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import tempfile
import time

def main(salida):
    with tempfile.TemporaryDirectory(prefix='jarvis-fts-') as tmp:
        raiz=Path(tmp);os.environ.update(JARVIS_DIR=str(raiz),JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1');trabajo=raiz/'trabajo';trabajo.mkdir()
        import tandas_documentales as T
        p=trabajo/'referencias.txt'
        with p.open('w') as f:
            for i in range(2500):f.write(f'OROFTS{i:05d} Existencias {i+7}. '+('relleno seguro '*50)+'\n')
        consultas=[{'id':f'FTS_{i:02d}','consulta':f'OROFTS{n:05d}','oro':f'Existencias {n+7}.','linea':n+1} for i,n in enumerate(range(0,2500,100))]
        corpus=json.dumps(consultas,ensure_ascii=False,indent=2)+'\n';salida.parent.mkdir(parents=True,exist_ok=True);cp=salida.with_name('corpus_fts.json')
        if cp.exists() and cp.read_text()!=corpus:raise ValueError('Corpus de FTS ya congelado diferente.')
        cp.write_text(corpus);sha=hashlib.sha256(cp.read_bytes()).hexdigest();cp.with_suffix('.sha256').write_text(sha+'\n')
        T.configurar(dict(T.DEFAULT,trozo=400));inicio=time.monotonic();d=T.indexar(T.crear([p])['id'],False);indexacion=time.monotonic()-inicio;rs=[]
        for usar in (False,True):
            for c in consultas:
                inicio=time.monotonic();r=T.buscar(d['id'],c['consulta'],usar_fts=usar,presupuesto=6000);segundos=time.monotonic()-inicio
                oro=[x for x in r['trozos'] if c['consulta'] in x['texto'] and c['oro'] in x['texto'] and f'línea {c["linea"]},' in x['referencia']]
                rs.append({'id':c['id'],'fts':usar,'segundos':round(segundos,6),'recall_8':int(bool(oro)),'cita_correcta':bool(oro),'total_trozos':r['total_trozos'],'metodo':r['metodo']})
        resumen={'sintetico':True,'ollama':False,'corpus_sha256':sha,'bytes':p.stat().st_size,'trozos':d['archivos'][0]['trozos'],'segundos_indexacion':round(indexacion,4),'rondas':[]}
        for usar in (False,True):
            xs=[x for x in rs if x['fts']==usar];resumen['rondas'].append({'fts':usar,'casos':len(xs),'recall_8':sum(x['recall_8'] for x in xs)/len(xs),'citas_correctas':sum(x['cita_correcta'] for x in xs),'mediana_segundos':round(statistics.median(x['segundos'] for x in xs),6),'fallidos':[x['id'] for x in xs if not x['cita_correcta']]})
        salida.write_text(json.dumps({'resumen':resumen,'auditoria':rs},ensure_ascii=False,indent=2));os.chmod(salida,0o600);print(json.dumps(resumen,ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--salida',type=Path,required=True);a=ap.parse_args();main(a.salida)
