"""Suplemento congelado de valores ficticios largos y marcadores partidos."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import lectores_adjuntos as L
from evaluar_redaccion_bordes_6h import PUBLICO

RAIZ=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/redaccion_larga'
FAMILIAS=['campo','cabecera','url','token','env','pem_inline']


def preparar(c):
    valor='FICTICIO_NO_ES_CREDENCIAL_71_Z9';largo=valor*1500;pos=c['desplazamiento'];f=c['familia'];prefijo='x'*(pos-1)+' '
    dato={'campo':'API_KEY='+largo,'cabecera':'Authorization: Bearer '+largo,'url':'https://usuario_ficticio_73:'+largo+'@example.invalid/ruta',
          'token':'sk-'+largo,'env':'NOMBRE='+largo,'pem_inline':'-----BEGIN PRIVATE KEY-----'+largo+'-----END PRIVATE KEY-----'}[f]
    if f=='env':prefijo='N'*pos
    return (prefijo+dato+'\n'+PUBLICO+'\n').encode(c['codificacion']),[valor]


def congelar():
    filas=[]
    for f in FAMILIAS:
        for p in [16120,16122,16124,16127]:
            for enc in ['utf-8','utf-16']:
                c={'id':f'RL6-{len(filas)+1:03d}','familia':f,'desplazamiento':p,'codificacion':enc}
                c['sha256_fuente']=hashlib.sha256(preparar(c)[0]).hexdigest();filas.append(c)
    d={'casos':filas,'rubrica':'Cero ventanas privadas de8 caracteres, excluida solo la etiqueta completa [CREDENCIALES REDACTADAS]; marcador público posterior presente. Datos ficticios, sin claves válidas.'}
    raw=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode();sha=hashlib.sha256(raw).hexdigest();RAIZ.mkdir(parents=True,exist_ok=True);RAIZ.chmod(0o700);p=RAIZ/'corpus.json'
    if p.exists() and p.read_bytes()!=raw:raise ValueError('No modificar corpus congelado.')
    if not p.exists():p.write_bytes(raw)
    p.chmod(0o600);p.with_suffix('.sha256').write_text(sha+'\n');p.with_suffix('.sha256').chmod(0o600);return d,sha


def main(ronda=None):
    d,sha=congelar()
    if not ronda:print(json.dumps({'casos':len(d['casos']),'sha256':sha}));return
    if not ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    p=RAIZ/(ronda+'.json')
    if p.exists():raise ValueError('No sobrescribir rondas anteriores.')
    filas=[]
    for c in d['casos']:
        raw,privados=preparar(c);item={'nombre':'fuente.env' if c['familia']=='env' else 'fuente.txt'}
        try:
            unidades=list(L.bloques_texto(io.BytesIO(raw),item,200000));texto=''.join(t for _,t in unidades);cotejo=texto.replace('[CREDENCIALES REDACTADAS]','')
            ventanas={v[i:i+8] for v in privados for i in range(len(v)-7)};filtradas=sum(v in cotejo for v in ventanas);publico=PUBLICO in texto
            filas.append(dict(c,ok=not filtradas and publico,ventanas_privadas_presentes=filtradas,publico_conservado=publico,estado_parcial=bool(item.get('cortado'))))
        except Exception as e:filas.append(dict(c,ok=False,error=type(e).__name__))
    r={'corpus_sha256':sha,'sha256_lector':hashlib.sha256(Path(L.__file__).read_bytes()).hexdigest(),'casos':len(filas),'aprobados':sum(x['ok'] for x in filas),'fallidos':[x['id'] for x in filas if not x['ok']],
       'por_familia':{f:{'casos':sum(x['familia']==f for x in filas),'aprobados':sum(x['ok'] for x in filas if x['familia']==f)} for f in FAMILIAS},'resultados':filas}
    p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600);print(json.dumps({k:v for k,v in r.items() if k!='resultados'},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ronda');a=ap.parse_args();main(a.ronda)
