"""Mide el corpus inmutable sin ejecutar acciones, nube o capturas de pruebas."""
import argparse
import hashlib
import json
import os
import shlex
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
REPORTES=BASE/'registros/reportes/mejora_6h_20261014'

def clasificar(c):
    import lenguaje_jarvis as N
    import lenguaje_recordatorios as R
    import interfaz_archivos as A
    import seguimiento_conversacion as S
    import ordenes_compuestas as O
    p=c['pedido']
    estado={'_lista_memorias':{i:1000+i for i in range(1,6)},'_tipo_ultimo_listado':'memorias',**c['estado']}
    memoria=N.interpretar(p,estado)
    recordatorio=R.interpretar(p)
    archivo=A.acceso_natural(p)
    local=getattr(N,'acceso_vocabulario',lambda *_:None)(p,estado)
    confirmacion=getattr(N,'confirmacion_conversacional',lambda _: '')(p)
    continuacion=S.continuacion(p)
    cadenas=O.separar(p)
    guia=S.es_guia(p)
    return dict(memoria=None if not memoria else dict(nombre=memoria.nombre,argumentos=memoria.argumentos,respuesta=memoria.respuesta),
                recordatorio=recordatorio,archivo=archivo,local=local,
                confirmacion=confirmacion,continuacion=continuacion,guia=guia,cadenas=cadenas)

def comprobar(c,resultado):
    import recordatorios_jarvis as R
    e=c['esperado'];m=resultado['memoria'];r=resultado['recordatorio']
    candidatos=[x for x in (m,r) if x]
    errores=[]
    def exigir(ok,texto):
        if not ok:errores.append(texto)
    sensibles={'clasificar_recuerdos','crear_proyecto','crear_recordatorio','modificar_recordatorio','eliminar_recordatorio','corregir_memoria','olvidar_memoria'}
    mutaciones=('/copiar','/mover','/carpeta','/deshacer','/aplicar','/anotar','/recordar','/eliminar','/editar')
    if e.get('seguro') or e.get('sin_accion'):
        exigir(not any(x['nombre'] in sensibles for x in candidatos),'Produjo una operación de escritura/modificación')
        exigir(not any((resultado[k] or '').startswith(mutaciones) for k in ('archivo','local')),'Traducido a un comando de modificación')
    if e.get('aclarar'):
        aclaraciones=[x for x in candidatos if x['nombre']=='aclarar']
        exigir(bool(aclaraciones),'Falta aclaración explícita')
        exigir(not any(x['nombre'] in sensibles for x in candidatos),'La ambigüedad produjo una acción')
        exigir(all((x.get('respuesta') or '').count('?')<=1 for x in aclaraciones),'Más de una pregunta de aclaración')
    if 'nombre' in e:
        elegidos=[x for x in candidatos if x['nombre']==e['nombre']]
        exigir(bool(elegidos),'No coincide el nombre de intención')
        if elegidos:
            a=elegidos[0].get('argumentos',{})
            for k,v in e.items():
                if k in {'nombre','fecha_canonica'}:continue
                exigir(a.get(k)==v,'Argumento literal/campo distinto: '+k)
            if 'fecha_canonica' in e:
                base=datetime(2026,10,14,12,0,tzinfo=R.ZONA)
                try:exigir(R.interpretar_fecha(a.get('fecha',''),base)==R.interpretar_fecha(e['fecha_canonica'],base),'Fecha u hora distinta')
                except ValueError as error:errores.append('Fecha no interpretable: '+str(error))
    if 'acceso' in e:
        acceso=resultado['local'] or resultado['archivo'] or (m['nombre'] if m and m['nombre'].startswith('/') else '')
        exigir(bool(acceso) and shlex.split(acceso)[0]==e['acceso'],'No coincide el comando local')
        for literal in e.get('literales',[]):exigir(literal in shlex.split(acceso or ''),'Literal/ruta modificado: '+literal)
    if 'confirmacion' in e:exigir(resultado['confirmacion']==e['confirmacion'],'Aceptación conversacional no reconocida')
    if e.get('continuacion'):exigir(resultado['continuacion'],'No reconoció continuación del hilo')
    if e.get('guia'):exigir(resultado['guia'],'No reconoce petición de guía')
    if 'partes' in e:
        exigir(len(resultado['cadenas'])==e['partes'],'No separó los tres pasos')
        for literal in e['cadena_literales']:exigir(any(literal in p for p in resultado['cadenas']),'Literal de cadena alterado')
    return errores

def evaluar(ronda):
    os.environ['JARVIS_PRUEBAS']='1'
    corpus=REPORTES/'corpus_6h_vocabulario_v1.json';raw=corpus.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    exigir=(REPORTES/'corpus_6h_vocabulario_v1.sha256').read_text().split()[0]
    if sha!=exigir:raise ValueError('La huella del corpus congelado cambió')
    destino=REPORTES/f'vocabulario_{ronda}.jsonl'
    resumen_path=REPORTES/f'vocabulario_{ronda}.json'
    if destino.exists() or resumen_path.exists():raise ValueError('La ronda existe; no sobrescribas auditorías')
    resultados=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-6h-vocabulario-') as tmp:
        os.environ['JARVIS_DIR']=tmp
        with destino.open('w',encoding='utf8') as salida:
            destino.chmod(0o600)
            for c in json.loads(raw)['frases']:
                try:r=clasificar(c);errores=comprobar(c,r)
                except Exception as error:r={};errores=[type(error).__name__+': '+str(error)]
                fila=dict(id=c['id'],familia=c['familia'],pedido=c['pedido'],esperado=c['esperado'],
                          resultado=r,ok=not errores,errores=errores)
                resultados.append(fila);salida.write(json.dumps(fila,ensure_ascii=False)+'\n')
    familias=Counter(x['familia'] for x in resultados)
    resumen=dict(ronda=ronda,corpus_sha256=sha,total=len(resultados),aprobados=sum(x['ok'] for x in resultados),
                 por_familia={f:dict(total=n,aprobados=sum(x['ok'] for x in resultados if x['familia']==f)) for f,n in familias.items()},
                 fallos=[x['id'] for x in resultados if not x['ok']],
                 ollama=0,escrituras_de_usuario=0,capturas_segundo_cerebro=0,
                 alcance='Intérprete y comandos locales, sin ejecutar acciones ni consultar un modelo.')
    resumen_path.write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n');resumen_path.chmod(0o600)
    print(json.dumps(resumen,ensure_ascii=False,indent=2))
    return resumen

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ronda',required=True,choices=['inicial_bruto','arnes_corregido','final','revision_1','revision_2','revision_3','cierre_adversario'])
    evaluar(parser.parse_args().ronda)
