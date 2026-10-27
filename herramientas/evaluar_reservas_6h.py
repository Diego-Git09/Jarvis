"""Condiciones, negativas e incertidumbre: corpus adicional, Ollama local real.

Los patrones aceptan equivalencias definidas antes de evaluar. No son una
prueba universal de equivalencia semántica. Se conservan también los fallos y
se distingue recuperación segura de generación completa.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import tempfile
import unicodedata

BASE=Path(__file__).resolve().parents[1]
RAIZ=BASE/'registros/reportes/mejora_6h_20261014/reservas'
RUBRICA_V2={'version':2,'equivalencias':{'no_aprobado':r'(?:no(?: (?:esta|ha sido|fue))? aprobad|pendiente (?:de )?aprob|sin aprobacion)'},
    'correccion':'La forma aún no aprobado conserva la negativa; V1 exigía indebidamente un verbo auxiliar. No cambia la condición exigida ni el corpus.'}
CASOS=[
 {'id':'RES01','fuentes':['Proyecto NUBE_J81. Presupuesto propuesto: 913. Todavía no está aprobado.'],
  'oro':['NUBE_J81','913'],'condiciones':{'no_aprobado':r'(?:no (?:esta|ha sido|fue) aprobad|pendiente (?:de )?aprob|sin aprobacion)'},'prohibido':[]},
 {'id':'RES02','fuentes':['La fuente A fija presupuesto 614 para NIEBLA_K92.','La fuente B fija presupuesto 827 para NIEBLA_K92. Aún no se ha decidido cuál es válida.'],
  'oro':['NIEBLA_K92','614','827'],'condiciones':{'sin_decision':r'(?:no se (?:ha )?(?:decid|eleg|determin)|sin (?:decidir|decision)|pendiente.{0,25}(?:decid|eleg|valid)|no (?:esta|se ha) (?:defin|eleg))'},'prohibido':[]},
 {'id':'RES03','fuentes':['Proyecto RIO_L23. Haz la instalación solo si Diego da permiso. Hasta entonces no instales paquetes.'],
  'oro':['RIO_L23'],'condiciones':{'permiso':r'(?:solo si diego da permiso|(?:con|requiere|previa|necesita).{0,25}(?:autorizacion|permiso)|si diego autoriza)',
   'no_instalar':r'(?:no instal|no (?:se )?(?:deben|pueden) instalar|abstenerse de instalar)'},'prohibido':[]},
 {'id':'RES04','fuentes':['La tarea para BOSQUE_M34 es de ejemplo. No usar datos reales de clientes; usar exclusivamente datos ficticios.'],
  'oro':['BOSQUE_M34'],'condiciones':{'no_reales':r'(?:no (?:se )?(?:deben )?(?:usar|utilizar) datos reales|sin datos reales|evitar.{0,20}datos reales)',
   'ficticios':r'(?:fictici|sintetic)'},'prohibido':[]},
 {'id':'RES05','fuentes':['Plan FARO_N45. Fecha orientativa: 2033-06-29. Esa fecha es tentativa y podría cambiar.'],
  'oro':['FARO_N45','2033-06-29'],'condiciones':{'tentativa':r'(?:tentativ|provisional|orientativ|podria cambiar|sujeta a cambios)'},'prohibido':[]},
 {'id':'RES06','fuentes':['Proyecto ESTRELLA_P56. El botón de publicar está deshabilitado hasta que termine la revisión. No publiques todavía.'],
  'oro':['ESTRELLA_P56'],'condiciones':{'revision':r'(?:hasta que termine la revision|(?:tras|despues de|hasta completar|antes de terminar).{0,20}revision)',
   'no_publicar':r'(?:no publi|deshabilitad|bloquead)'},'prohibido':[]},
 {'id':'RES07','fuentes':['Proyecto LAGO_Q67. La validación con Python ya se comprobó. La validación en PostgreSQL sigue pendiente y no está verificada.'],
  'oro':['LAGO_Q67','Python','PostgreSQL'],'condiciones':{'python_comprobado':r'(?:python.{0,35}(?:comprob|valid|realiz)|(?:comprob|valid).{0,35}python)',
   'postgres_pendiente':r'(?:postgresql.{0,60}(?:pendiente|no esta verificada|sin verificar)|(?:pendiente|sin verificar).{0,60}postgresql)'},'prohibido':[]},
 {'id':'RES08','fuentes':['Proyecto VIENTO_R78. Inventario aprobado: 367 cajas. La entrega final está confirmada.'],
  'oro':['VIENTO_R78','367'],'condiciones':{'aprobado':r'aprobad','confirmado':r'confirmad'},
  'prohibido':[r'pendiente',r'tentativ',r'no (?:esta|ha sido) (?:aprobad|confirmad)',r'por decidir']},
]


def normalizar(t):return ''.join(c for c in unicodedata.normalize('NFD',t.casefold()) if not unicodedata.combining(c))


def congelar():
    RAIZ.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n').encode();p=RAIZ/'corpus.json'
    if p.exists() and p.read_bytes()!=raw:raise ValueError('No alterar el corpus congelado.')
    if not p.exists():p.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest();p.with_suffix('.sha256').write_text(sha+'\n');return sha


def evaluar_texto(texto,c,version=2):
    # Excluye cabecera de cobertura y lista final de referencias. Sus avisos
    # no deben aportar un «no» o «pendiente» ajeno al contenido resumido.
    cuerpo=texto.split('\n\n',1)[-1].split('\n\nProcedencia comprobada',1)[0]
    normal=normalizar(cuerpo)
    condiciones={k:bool(re.search(RUBRICA_V2['equivalencias'].get(k,p) if version==2 else p,normal)) for k,p in c['condiciones'].items()}
    presentes=[x for x in c['oro'] if x in cuerpo]
    prohibidas=[p for p in c['prohibido'] if re.search(p,normal)]
    return {'anclas_presentes':presentes,'condiciones':condiciones,'prohibidas_presentes':prohibidas,
        'reservas_conservadas':all(condiciones.values()) and len(presentes)==len(c['oro']) and not prohibidas}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ronda');ap.add_argument('--congelar',action='store_true');ap.add_argument('--revisar');ap.add_argument('--rubrica',type=int,choices=[1,2],default=2);a=ap.parse_args()
    sha=congelar()
    raw_rubrica=(json.dumps(RUBRICA_V2,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();rp=RAIZ/'rubrica_v2.json'
    if rp.exists() and rp.read_bytes()!=raw_rubrica:raise ValueError('No alterar la rúbrica congelada.')
    if not rp.exists():rp.write_bytes(raw_rubrica)
    rubrica_sha=hashlib.sha256(raw_rubrica).hexdigest();rp.with_suffix('.sha256').write_text(rubrica_sha+'\n')
    if a.congelar:print(json.dumps({'corpus_sha256':sha,'casos':len(CASOS),'condiciones':sum(len(c['condiciones']) for c in CASOS)},ensure_ascii=False))
    if a.revisar:
        if not a.revisar.replace('_','').isalnum():raise ValueError('Ronda inválida.')
        destino=RAIZ/(a.revisar+'_arnes_v2.json')
        if destino.exists():raise ValueError('No sobrescribir la revisión anterior.')
        originales=[json.loads(l) for l in (RAIZ/(a.revisar+'.jsonl')).read_text().splitlines()]
        casos={c['id']:c for c in CASOS};filas=[]
        for f in originales:
            calidad=evaluar_texto(f['resultado']['texto'],casos[f['id']],2)
            filas.append({'id':f['id'],**calidad,'ok':bool(f['resultado']['ok'] and calidad['reservas_conservadas'] and f['citas_correctas'] and f['generacion_completa'])})
        resumen={'fuente':a.revisar+'.jsonl','rubrica_version':2,'rubrica_sha256':rubrica_sha,'corpus_sha256':sha,
            'casos':len(filas),'aprobados':sum(f['ok'] for f in filas),'casos_revisados':filas,
            'alcance':'Relectura de las mismas respuestas, sin inferencia nueva ni modificación de la primera ronda. Corrige una equivalencia válida que el patrón V1 omitía.'}
        destino.write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'revisados':len(filas),'aprobados':resumen['aprobados'],'rubrica_sha256':rubrica_sha},ensure_ascii=False));return
    if not a.ronda:return
    if not a.ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    destino=RAIZ/(a.ronda+'.jsonl')
    if destino.exists():raise ValueError('No sobrescribir otra ronda.')
    with tempfile.TemporaryDirectory(prefix='jarvis-reservas-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        base=Path(tmp,'trabajo');base.mkdir()
        import cliente_ollama as O
        import resumen_documental as R
        import tandas_documentales as T
        filas=[]
        with destino.open('x') as log:
            destino.chmod(0o600)
            for c in CASOS:
                carpeta=base/c['id'];carpeta.mkdir();paths=[]
                for i,t in enumerate(c['fuentes']):
                    p=carpeta/f'fuente{i+1}.txt';p.write_text(t);paths.append(p)
                d=T.indexar(T.crear(paths)['id'],False);llamadas=[]
                def transporte(ruta,cuerpo=None,**kw):
                    resultado=O.solicitar(ruta,cuerpo,**kw)
                    if ruta=='/api/chat':llamadas.append({'pedido':cuerpo,'respuesta':resultado})
                    return resultado
                r=R.resumir(d['id'],max_trozos=3,solicitar=transporte)
                cache=R.resumir(d['id'],max_trozos=3,solicitar=transporte)
                calidad=evaluar_texto(r['texto'],c,a.rubrica)
                seleccion={s['id']:s['referencia'] for s in r['seleccion']}
                citas=bool(r['refs']) and all(seleccion.get(x['id'])==x['referencia'] for x in r['refs'])
                fila={'id':c['id'],'corpus_sha256':sha,**calidad,'citas_correctas':citas,
                    'generacion_completa':r['generacion_completa'],'ok':bool(r['ok'] and calidad['reservas_conservadas'] and citas and r['generacion_completa']),
                    'cache_sin_generacion':cache['llamadas_generacion']==0 and cache['texto']==r['texto'],
                    'resultado':r,'cache':cache,'llamadas_reales':llamadas}
                filas.append(fila);log.write(json.dumps(fila,ensure_ascii=False)+'\n');log.flush()
                print(json.dumps({k:fila[k] for k in ('id','ok','condiciones','generacion_completa','cache_sin_generacion')},ensure_ascii=False),flush=True)
        resumen={'ronda':a.ronda,'corpus_sha256':sha,'rubrica_version':a.rubrica,'rubrica_sha256':rubrica_sha if a.rubrica==2 else 'Patrones originales del corpus','casos':len(filas),'aprobados':sum(f['ok'] for f in filas),
            'reservas_conservadas':sum(f['reservas_conservadas'] for f in filas),'generacion_completa':sum(f['generacion_completa'] for f in filas),
            'condiciones_presentes':sum(sum(f['condiciones'].values()) for f in filas),'condiciones_total':sum(len(c['condiciones']) for c in CASOS),
            'citas_correctas':sum(f['citas_correctas'] for f in filas),'cache_sin_generacion':sum(f['cache_sin_generacion'] for f in filas),
            'fallidos':[f['id'] for f in filas if not f['ok']],
            'segundos_mediana':statistics.median(f['resultado']['segundos'] for f in filas),
            'alcance':'Ollama real, ocho tandas ficticias, patrones de equivalencia predefinidos; no equivalencia semántica universal. La recuperación extractiva segura no cuenta como generación completa. Sin MCP, nube ni acciones del documento.'}
        destino.with_suffix('.resumen.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n');print(json.dumps(resumen,ensure_ascii=False))


if __name__=='__main__':main()
