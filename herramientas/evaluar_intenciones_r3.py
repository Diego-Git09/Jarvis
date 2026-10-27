"""Evaluación por intención y por variante; sin IA y sin ejecutar acciones."""
import json
from pathlib import Path
from normalizacion_entrada import plegar
from comprension_peticion import principal

def corpus():
    return json.loads(Path(__file__).with_name('corpus_intenciones_r3.json').read_text())

def variantes(frase):
    # Transformaciones fijadas antes de medir, mismas etiquetas que el manual.
    return {'manual':frase,'sin_tildes':plegar(frase),'mayusculas':frase.upper(),
        'mayuscula_intercalada':''.join(c.upper() if i%2 else c for i,c in enumerate(frase)),
        'sin_signos':frase.replace('¿','').replace('?','').replace('.',''),
        'pregunta_espaciada':frase+' ?', 'espacios':frase.replace(' ','   '),
        'cortesia':'porfa '+frase,'modal':'puedes '+frase,
        'vocativo_tipeado':'jarveis, '+frase,
        'abreviaciones':frase.replace('que ','q ').replace('tambien','tmb'),
        'voseo':frase.replace('hazme','haceme').replace('muestrame','mostrame'),
        'pegada':'holajarvis '+frase,'chilenismo':'oye '+frase+' po'}

def evaluar():
    por_intencion={};por_categoria={};fallos=[]
    for x in corpus():
        for categoria,frase in variantes(x['frase']).items():
            obtenido=principal(frase);ok=obtenido==x['intencion']
            for tabla,k in [(por_intencion,x['intencion']),(por_categoria,categoria)]:
                t=tabla.setdefault(k,{'total':0,'aciertos':0});t['total']+=1;t['aciertos']+=int(ok)
            if not ok:fallos.append({'id':x['id'],'categoria':categoria,'frase':frase,'esperado':x['intencion'],'obtenido':obtenido})
    for tabla in (por_intencion,por_categoria):
        for t in tabla.values():t['porcentaje']=round(100*t['aciertos']/t['total'],2)
    return {'alcance':'Clasificador de intenciones, sin inferencia ni ejecución; no mide calidad del modelo. Frases manuales sintéticas, distintas de las líneas observadas.',
        'manuales':len(corpus()),'por_intencion':por_intencion,'por_categoria':por_categoria,'fallos':fallos}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--salida',required=True);a=p.parse_args()
    r=evaluar();destino=Path(a.salida)
    with destino.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k!='fallos'},ensure_ascii=False,indent=2))
