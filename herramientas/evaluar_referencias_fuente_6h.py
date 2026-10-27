"""Corpus acotado de nombres/exclusiones; clasificación, sin abrir documentos."""
import argparse
import hashlib
import json
from pathlib import Path

import recuperacion_hibrida as H

RAIZ=Path(__file__).resolve().parents[1]/'registros/reportes/mejora_6h_20261014/referencias_fuentes'
FUENTE={'nombre':'anexo_a.txt','ruta':'/trabajo/anexo_a.txt','_nombre_cita':'carpeta/anexo_a.txt'}
CASOS=[
 ('Usa anexo_a.txt para contestar.',1),
 ('Lee "anexo_a.txt" antes de responder.',1),
 ('Consulta carpeta/anexo_a.txt aunque otro archivo trate el tema.',1),
 ('Usa /trabajo/anexo_a.txt para contestar.',1),
 ('No uses anexo_a.txt; responde con el otro.',-1),
 ('Nunca leas anexo_a.txt para esta pregunta.',-1),
 ('Excluye anexo_a.txt de esta respuesta.',-1),
 ('Ignora anexo_a.txt al revisar la tanda.',-1),
 ('Descarta anexo_a.txt para esta pregunta.',-1),
 ('No ignores anexo_a.txt al revisar la tanda.',1),
 ('No excluyas anexo_a.txt de esta respuesta.',1),
 ('Nunca descartes anexo_a.txt para esta pregunta.',1),
 ('Revisa todo sin excluir anexo_a.txt.',1),
 ('Revisa todo salvo anexo_a.txt.',-1),
 ('Revisa todos excepto anexo_a.txt.',-1),
 ('Omite anexo_a.txt en esta pregunta.',-1),
 ('No omitas anexo_a.txt en esta pregunta.',1),
 ('No uses anexo_b.txt, consulta anexo_a.txt.',1),
 ('No uses anexo_a.txt ni anexo_b.txt.',-1),
 ('No uses anexo_b.txt ni anexo_a.txt.',-1),
 ('No uses anexo_b.txt y anexo_a.txt.',-1),
 ('No uses anexo_b.txt, tampoco anexo_a.txt.',-1),
 ('No uses anexo_a.txt, pero finalmente consulta anexo_a.txt.',1),
 ('Consulta anexo_a.txt, pero finalmente no uses anexo_a.txt.',-1),
 ('El ejemplo dice "no uses anexo_a.txt"; explícame el ejemplo.',0),
 ('El ejemplo dice «excluye anexo_a.txt»; explícame el ejemplo.',0),
 ('Consulta /ruta/ajena/anexo_a.txt.',0),
 ('Consulta prefijo_anexo_a.txt.',0),
 ('Consulta anexo_a.txt_backup.',0),
 ('Necesito información de otro documento.',0),
]


def main(ronda=None):
    d={'fuente_ficticia':FUENTE,'casos':[{'id':f'RF6-{i:03d}','pregunta':q,'estado_oro':oro} for i,(q,oro) in enumerate(CASOS,1)],
       'rubrica':'-1 excluida,0 no mencionada como instrucción,1 referencia positiva. No abre rutas ni concede permisos.'}
    raw=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode();sha=hashlib.sha256(raw).hexdigest()
    RAIZ.mkdir(parents=True,exist_ok=True);RAIZ.chmod(0o700);corpus=RAIZ/'corpus.json'
    if corpus.exists() and corpus.read_bytes()!=raw:raise ValueError('No modificar el corpus congelado.')
    if not corpus.exists():corpus.write_bytes(raw)
    corpus.chmod(0o600);corpus.with_suffix('.sha256').write_text(sha+'\n');corpus.with_suffix('.sha256').chmod(0o600)
    if not ronda:print(json.dumps({'casos':len(CASOS),'sha256':sha}));return
    if not ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    destino=RAIZ/(ronda+'.json')
    if destino.exists():raise ValueError('Usa otra ronda para conservar la anterior.')
    filas=[]
    for c in d['casos']:
        estado=H.estado_fuente(c['pregunta'],FUENTE);filas.append(dict(c,estado_obtenido=estado,ok=estado==c['estado_oro']))
    r={'corpus_sha256':sha,'sha256_interprete':hashlib.sha256(Path(H.__file__).read_bytes()).hexdigest(),'casos':len(filas),
       'aprobados':sum(f['ok'] for f in filas),'fallidos':[f['id'] for f in filas if not f['ok']],'resultados':filas}
    destino.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');destino.chmod(0o600)
    print(json.dumps({k:v for k,v in r.items() if k!='resultados'},ensure_ascii=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ronda');a=ap.parse_args();main(a.ronda)
