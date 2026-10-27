"""Credenciales ficticias en bordes de lectura; nunca registra sus valores."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import lectores_adjuntos as L

RAIZ=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/redaccion_bordes'
DESPLAZAMIENTOS=[8190,8192,16112,16120,16124,16127,16128,16129,16376,16384,32248,32256]
FAMILIAS=['campo','cabecera','url','pem','env','espacios']
PUBLICO='FIN_PUBLICO_BORDE_73'


def preparar(c):
    valor='FICTICIO_NO_ES_CREDENCIAL_71_Z9';usuario='usuario_ficticio_73';pos=c['desplazamiento'];f=c['familia']
    prefijo='x'*(pos-1)+' '
    dato={'campo':'API_KEY='+valor,'cabecera':'Authorization: Bearer '+valor,'url':'https://'+usuario+':'+valor+'@example.invalid/ruta',
          'pem':'-----BEGIN PRIVATE KEY-----\n'+(valor+'\n')*2000+'-----END PRIVATE KEY-----',
          'env':'NOMBRE='+valor,'espacios':'PASSWORD'+(' '*20000)+'='+valor}[f]
    if f=='env':prefijo='N'*pos
    texto=prefijo+dato+'\n'+PUBLICO+'\n'
    return texto.encode(c['codificacion']),[valor,usuario] if f=='url' else [valor]


def corpus():
    return [{'id':f'RB6-{i:03d}','familia':f,'desplazamiento':p,'codificacion':e} for i,(f,p,e) in enumerate(
        ((f,p,e) for f in FAMILIAS for p in DESPLAZAMIENTOS for e in ['utf-8','utf-16']),1)]


def congelar():
    casos=corpus()
    for c in casos:c['sha256_fuente']=hashlib.sha256(preparar(c)[0]).hexdigest()
    d={'casos':casos,'rubrica':'Cero ventanas de8 caracteres de valores privados ficticios en la salida; marcador público posterior presente; lectura acotada y sin ejecución. No prueba todos los formatos de secreto.'}
    raw=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode();sha=hashlib.sha256(raw).hexdigest()
    RAIZ.mkdir(parents=True,exist_ok=True);RAIZ.chmod(0o700);p=RAIZ/'corpus.json'
    if p.exists() and p.read_bytes()!=raw:raise ValueError('No modificar corpus congelado.')
    if not p.exists():p.write_bytes(raw)
    p.chmod(0o600);p.with_suffix('.sha256').write_text(sha+'\n');p.with_suffix('.sha256').chmod(0o600)
    return d,sha


def main(ronda=None,rubrica=2):
    d,sha=congelar()
    if not ronda:print(json.dumps({'casos':len(d['casos']),'sha256':sha}));return
    if not ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    p=RAIZ/(ronda+'.json');
    if p.exists():raise ValueError('No sobrescribir rondas anteriores.')
    filas=[];rubrica_sha=None
    if rubrica==2:
        regla={'version':2,'cambio':'Excluir solo la etiqueta completa [CREDENCIALES REDACTADAS] antes de buscar ventanas privadas; CREDENCIAL también aparece en el valor ficticio y causaba un falso positivo. El valor fuera de esa etiqueta sigue prohibido. No cambia corpus ni detección del lector.'}
        raw_regla=(json.dumps(regla,ensure_ascii=False,indent=2)+'\n').encode();rubrica_sha=hashlib.sha256(raw_regla).hexdigest();pr=RAIZ/'rubrica_2.json'
        if pr.exists() and pr.read_bytes()!=raw_regla:raise ValueError('No modificar rúbrica congelada.')
        if not pr.exists():pr.write_bytes(raw_regla)
        pr.chmod(0o600)
    for c in d['casos']:
        raw,privados=preparar(c);item={'nombre':'fuente.env' if c['familia']=='env' else 'fuente.txt'}
        try:
            unidades=list(L.bloques_texto(io.BytesIO(raw),item,200000));texto=''.join(t for _,t in unidades)
            ventanas={v[i:i+8] for v in privados for i in range(len(v)-7)}
            cotejo=texto.replace('[CREDENCIALES REDACTADAS]','') if rubrica==2 else texto
            filtradas=sum(v in cotejo for v in ventanas);publico=PUBLICO in texto
            filas.append(dict(c,ok=filtradas==0 and publico,ventanas_privadas_presentes=filtradas,publico_conservado=publico,
                caracteres_salida=len(texto),unidades=len(unidades),estado_parcial=bool(item.get('cortado')),aviso=item.get('aviso','')))
        except Exception as e:filas.append(dict(c,ok=False,error=type(e).__name__))
    r={'corpus_sha256':sha,'rubrica':rubrica,'rubrica_sha256':rubrica_sha,'sha256_lector':hashlib.sha256(Path(L.__file__).read_bytes()).hexdigest(),'casos':len(filas),'aprobados':sum(x['ok'] for x in filas),
       'fallidos':[x['id'] for x in filas if not x['ok']],'por_familia':{f:{'casos':sum(x['familia']==f for x in filas),'aprobados':sum(x['ok'] for x in filas if x['familia']==f)} for f in FAMILIAS},'resultados':filas}
    p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600)
    print(json.dumps({k:v for k,v in r.items() if k!='resultados'},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ronda');ap.add_argument('--rubrica',type=int,choices=[1,2],default=2);a=ap.parse_args();main(a.ronda,a.rubrica)
