"""Prototipos de ordenamiento offline sobre vectores reales ya registrados.

No sustituye la búsqueda de producción, sus controles ni una prueba de
latencia completa. No genera vectores nuevos ni llama a modelos/MCP.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

RAIZ=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/recuperacion_semantica'


def palabras(t):return Counter(re.findall(r'\w{2,}',t.casefold()))
def coseno(a,b):return sum(x*y for x,y in zip(a,b))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))


def main(ronda):
    if not ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    salida=RAIZ/(ronda+'_prototipos.json')
    if salida.exists():raise ValueError('No sobrescribir prototipos anteriores.')
    datos=json.loads((RAIZ/'corpus.json').read_text());recursos=RAIZ/(ronda+'.recursos.json')
    vectores={(x['tipo'],x['sha256_texto']):x['vector'] for x in json.loads(recursos.read_text())['embeddings']}
    def vector(tipo,texto):return vectores[(tipo,hashlib.sha256(texto.encode()).hexdigest())]
    db=sqlite3.connect(':memory:');db.execute('CREATE VIRTUAL TABLE docs USING fts5(texto,referencia)')
    fuentes=datos['fuentes'];filas=[]
    for f in fuentes:db.execute('INSERT INTO docs VALUES (?,?)',(f['texto'],f['nombre']+' · líneas 1-1'))
    for q in datos['consultas']:
        tokens=palabras(q['consulta']);match=' OR '.join('"'+w.replace('"','""')+'"' for w in tokens)
        ft=[r[0]-1 for r in db.execute('SELECT rowid FROM docs WHERE docs MATCH ? ORDER BY bm25(docs),rowid DESC',(match,))] if match else []
        lexical={i:sum(min(n,palabras(f['texto']+' '+f['nombre']+' · líneas 1-1')[w]) for w,n in tokens.items()) for i,f in enumerate(fuentes)}
        consulta=vector('consulta',q['consulta']);sim={i:coseno(consulta,vector('documento',f['texto'])) for i,f in enumerate(fuentes)}
        vr=sorted(range(len(fuentes)),key=lambda i:(sim[i],fuentes[i]['nombre']),reverse=True)
        rr={i:1/(60+n+1) for n,i in enumerate(vr)}
        for n,i in enumerate(ft):rr[i]=rr.get(i,0)+1/(60+n+1)
        mencion={i:int(re.search(r'(?<![\w/])'+re.escape(f['nombre'])+r'(?!\w)',q['consulta'],re.I) is not None) for i,f in enumerate(fuentes)}
        ordenes={'suma_actual':sorted(range(len(fuentes)),key=lambda i:(lexical[i]+10*sim[i],fuentes[i]['nombre']),reverse=True),
            'suma_con_metadatos':sorted(range(len(fuentes)),key=lambda i:(mencion[i],lexical[i]+10*sim[i],fuentes[i]['nombre']),reverse=True),
            'vector':vr,'fts_bm25':ft,'rrf':sorted(rr,key=lambda i:(rr[i],fuentes[i]['nombre']),reverse=True),
            'rrf_con_metadatos':sorted(rr,key=lambda i:(mencion[i],rr[i],fuentes[i]['nombre']),reverse=True)}
        for modo,orden in ordenes.items():
            indice=next(i for i,f in enumerate(fuentes) if f['nombre']==q['fuente_oro']);pos=orden.index(indice)+1 if indice in orden else None
            filas.append({'id':q['id'],'clase':q['clase'],'modo':modo,'rango_oro':pos,'recall8':pos is not None and pos<=8,'top1':pos==1})
    db.close();resumen=[]
    for modo in dict.fromkeys(f['modo'] for f in filas):
        xs=[f for f in filas if f['modo']==modo]
        resumen.append({'modo':modo,'recall8':sum(x['recall8'] for x in xs),'top1':sum(x['top1'] for x in xs),
            'fallos_recall':[x['id'] for x in xs if not x['recall8']],'fallos_top1':[x['id'] for x in xs if not x['top1']]})
    r={'vectores':recursos.name,'corpus_sha256':(RAIZ/'corpus.sha256').read_text().strip(),'resumen':resumen,'casos':filas,
        'alcance':'Prototipos offline sobre40 fuentes y40 consultas congeladas, con vectores reales registrados. No es cambio de producción, prueba de controles/citas ni latencia de búsqueda completa. La mención de archivo aún no distingue negativas; antes de promoverla requiere controles.'}
    salida.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');salida.chmod(0o600);print(json.dumps(resumen,ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ronda',required=True);a=ap.parse_args();main(a.ronda)
