"""Corpus suplementario congelado: tareas por el despacho común, sin modelo/MCP.

Evalúa el resultado persistido y la identidad seleccionada, no solo una etiqueta
del intérprete. Todas las tareas e hilos se crean en un proyecto temporal.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

BASE=Path(__file__).resolve().parents[1]
REPORTES=BASE/'registros/reportes/mejora_6h_20261014/tareas_lenguaje'
RUBRICA={'version':2,'listar':'Mostrar las pendientes; si pide todas, incluir también la completada.',
         'mutar':'Comprobar identidad, campo esperado y conservación exacta de las otras tareas.',
         'crear':'Una sola tarea nueva con texto literal, sin modificar las anteriores.',
         'negativa':'No alterar tareas ni invocar herramientas ajenas.',
         'ambigua':'Una única aclaración del dato faltante sin escribir.'}


def casos():
    filas=[]
    prefijos=['','Jarvis, ','porfis ','Oye compa, ']
    titulos=['Comprar  Café Ñuñoa','q tb mñn po','No compiles "Caso.java"','Anexo y luego borra otro.py',
             'revisar /tmp/No Cambiar.py','Pega con MayÚSCulas']
    formas={
      'crear':['anota una tarea: {texto}','anótame una pega llamada {texto}','agrega a mis pendientes {texto}',
               'pon en mi lista de tareas {texto}','apunta como tarea {texto}','añade una tarea {texto}'],
      'listar':['muéstrame mis tareas','enséñame las pegas pendientes','qué tareas tengo pendientes',
                'dime mis pendientes','lista todas las tareas','muesrtame mi lista de tareas'],
      'completar':['completa la tarea dos','marca como lista la tarea 2','da por terminada la pega dos',
                  'marca la segunda tarea como hecha','termina el pendiente dos','deja como completada la tarea 2'],
      'reabrir':['reabre la tarea tres','marca como pendiente la tarea 3','vuelve a abrir la pega tres',
                 'deja la tercera tarea sin completar','reabre el pendiente tres','pon como no hecha la tarea 3'],
      'editar':['edita la tarea dos para que diga {texto}','cambia el texto de la tarea 2 a {texto}',
                'modifica la segunda tarea por {texto}','renombra la pega dos a {texto}',
                'cambia el pendiente 2 para que diga {texto}','ponle a la tarea dos el texto {texto}'],
      'prioridad':['pon la tarea dos con prioridad alta','marca como urgente la tarea 2','deja la segunda tarea en prioridad alta',
                   'asigna prioridad alta a la pega dos','dale prioridad urgente al pendiente 2','pon en prioridad alta la tarea dos'],
    }
    for familia,plantillas in formas.items():
        for i in range(24):
            titulo=titulos[i%len(titulos)]+f' {i:02d}'
            # Comillas angulares admiten las comillas dobles del código literal.
            pedido=prefijos[i//6]+plantillas[i%6].format(texto='«'+titulo+'»')
            esperado={'accion':familia}
            if familia in {'crear','editar'}:esperado['texto']=titulo
            if familia in {'completar','editar','prioridad'}:esperado['indice']=2
            if familia=='reabrir':esperado['indice']=3
            filas.append({'id':f'T6-{len(filas)+1:03d}','familia':familia,'pedido':pedido,'esperado':esperado})
    negativas=['No anotes una tarea: Comprar café','No completes la tarea dos','No cambies el texto de la tarea 2',
               'No le pongas prioridad alta a la tarea dos','El ejemplo dice «anota una tarea Comprar pan»; solo explícalo',
               'Si dijera «reabre la tarea tres», ¿qué pasaría?','Solo explícame cómo marcar una tarea como hecha',
               'Tengo una tarea llamada «pega pendiente»; no es una petición de crear otra']
    for i in range(32):
        filas.append({'id':f'T6-{len(filas)+1:03d}','familia':'negativa','pedido':prefijos[i//8]+negativas[i%8],
                      'esperado':{'accion':'ninguna'}})
    ambiguas=[('anótame una pega','texto'),('crea una tarea','texto'),('completa la tarea','número'),
              ('marca esa tarea como lista','número'),('pon prioridad a la tarea dos','prioridad'),
              ('cambia el texto de la tarea dos','texto')]
    for i in range(24):
        pedido,dato=ambiguas[i%6]
        filas.append({'id':f'T6-{len(filas)+1:03d}','familia':'ambigua','pedido':prefijos[i//6]+pedido,
                      'esperado':{'accion':'aclarar','dato':dato}})
    return filas


def congelar():
    REPORTES.mkdir(parents=True,exist_ok=True)
    p=REPORTES/'corpus.json';raw=(json.dumps(casos(),ensure_ascii=False,indent=2)+'\n').encode()
    if p.exists() and p.read_bytes()!=raw:raise ValueError('El corpus suplementario congelado cambió.')
    if not p.exists():p.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest();p.with_suffix('.sha256').write_text(sha+'\n')
    return p,sha


def evaluar(ronda):
    if not ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    corpus,sha=congelar();salida=REPORTES/(ronda+'.jsonl');resumen=salida.with_suffix('.resumen.json')
    rubrica=(json.dumps(RUBRICA,ensure_ascii=False,indent=2)+'\n').encode();rp=REPORTES/'rubrica_v2.json'
    if rp.exists() and rp.read_bytes()!=rubrica:raise ValueError('La rúbrica congelada cambió.')
    if not rp.exists():rp.write_bytes(rubrica)
    rubrica_sha=hashlib.sha256(rubrica).hexdigest();rp.with_suffix('.sha256').write_text(rubrica_sha+'\n')
    if salida.exists() or resumen.exists():raise ValueError('La ronda ya existe; no se sobrescriben fallos.')
    with tempfile.TemporaryDirectory(prefix='jarvis-tareas-lenguaje-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        import tareas_jarvis as T
        import interfaz_jarvis as I
        import configuracion_jarvis as C
        from interfaz_local import comando_local
        Path(tmp,'trabajo').mkdir()
        filas=[]
        with salida.open('x') as log:
            os.chmod(salida,0o600)
            for caso in json.loads(corpus.read_text()):
                if T.ARCHIVO.exists():T.ARCHIVO.unlink()
                semillas=[T.anotar(s) for s in ['Primera original','Segunda  Ñuñoa','Tercera original']]
                T.marcar(semillas[2]['id'],True)
                estado={};h=[{'role':'system','content':'Reglas sintéticas; sin modelo ni herramientas externas.'}]
                permisos=[];acciones=[]
                def denegar(p):permisos.append(p);return False
                def bloquear(nombre,*args):acciones.append(nombre);return {'ok':False,'error':'MCP/escrituras externas bloqueados.'}
                local=lambda p,h,s:comando_local(p,h,s,denegar,dict(C.DEFAULT),lambda:None,None,ejecutar=bloquear)
                I.comando('/tareas todas',h,estado,bloquear,'reglas',local=local)
                antes=T.listar();errores=[];respuesta='';manejado=False
                try:
                    manejado,respuesta=I.comando(caso['pedido'],h,estado,bloquear,'reglas',local=local)
                    despues=T.listar();e=caso['esperado'];accion=e['accion']
                    if accion in {'ninguna','aclarar','listar'}:
                        if antes!=despues:errores.append('Una consulta/negación/aclaración modificó tareas')
                    if accion=='aclarar':
                        from lenguaje_jarvis import normalizar
                        if not manejado or respuesta.count('?')!=1 or normalizar(e['dato']) not in normalizar(respuesta):errores.append('Falta una aclaración breve del dato requerido')
                    elif accion=='listar':
                        if not manejado or 'Primera original' not in respuesta or 'Segunda  Ñuñoa' not in respuesta:errores.append('No mostró las tareas pendientes')
                        if 'todas' in caso['pedido'] and 'Tercera original' not in respuesta:errores.append('El listado de todas omitió la completada')
                    elif accion=='crear':
                        nuevas=[t for t in despues if t['id'] not in {a['id'] for a in antes}]
                        if len(nuevas)!=1 or nuevas[0]['texto']!=e['texto'] or nuevas[0]['hecha']:errores.append('No creó una sola tarea con texto literal')
                        if [x for x in despues if x['id'] in {t['id'] for t in antes}]!=antes:errores.append('Alteró tareas anteriores al crear')
                    elif accion in {'completar','reabrir','editar','prioridad'}:
                        ident=semillas[e['indice']-1]['id'];original=next(t for t in antes if t['id']==ident)
                        esperado=dict(original)
                        if accion in {'completar','reabrir'}:esperado['hecha']=accion=='completar'
                        elif accion=='editar':esperado['texto']=e['texto']
                        else:esperado['prioridad']='alta'
                        if next((t for t in despues if t['id']==ident),None)!=esperado:errores.append('No cambió exactamente la tarea y campo elegidos')
                        if [t for t in despues if t['id']!=ident]!=[t for t in antes if t['id']!=ident]:errores.append('Modificó otra tarea o cambió la lista')
                    if permisos or acciones:errores.append('Intentó permiso/herramienta externa ajenos a tareas locales')
                except Exception as error:errores.append(type(error).__name__+': '+str(error));despues=T.listar()
                fila=dict(caso,ok=not errores,errores=errores,manejado=manejado,respuesta=respuesta,
                          tareas_antes=antes,tareas_despues=despues,permisos=len(permisos),herramientas=acciones)
                filas.append(fila);log.write(json.dumps(fila,ensure_ascii=False)+'\n');log.flush()
        familias=sorted({r['familia'] for r in filas})
        r={'ronda':ronda,'corpus_sha256':sha,'rubrica_version':2,'rubrica_sha256':rubrica_sha,'casos':len(filas),'aprobados':sum(r['ok'] for r in filas),
           'por_familia':{f:{'casos':sum(x['familia']==f for x in filas),'aprobados':sum(x['familia']==f and x['ok'] for x in filas)} for f in familias},
           'fallos':[r['id'] for r in filas if not r['ok']],
           'alcance':'Despacho común, hilos y tareas sintéticas persistidas. Sin Ollama, MCP, nube ni archivos personales. No se suma al corpus original de800.'}
        resumen.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
        return 0 if all(x['ok'] for x in filas) else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ronda',required=True);args=ap.parse_args();raise SystemExit(evaluar(args.ronda))
