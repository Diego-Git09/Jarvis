"""Consultas de estado frente a ejemplos/negaciones; servidores solo simulados."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock,patch

BASE=Path(__file__).resolve().parents[1]
REPORTES=BASE/'registros/reportes/mejora_6h_20261014/estado_lenguaje'
POSITIVAS=['verifica si estás usando Ollama','revisa si Ollama responde','¿Funciona Ollama?',
           '¿estás conectado a Ollama?','qué modelo usas','cuál es tu modelo','dime qué modelo estás usando',
           '¿con qué modelo estás funcionando?','¿qué modelo tienes activo ahora?',
           'Jarvis, sigues usando Ollama?','¿me puedes decir qué IA estás usando?',
           '¿puedes comprobar si Ollama está disponible?','¿Ollama está respondiendo?',
           '¿estás funcionando con Qwen o con otro modelo?']
NEGATIVAS=['No verifiques si Ollama está funcionando','No consultes si Ollama funciona',
           'Nunca compruebes mi conexión con Ollama','porfis no revises si Ollama está conectado',
           'No ejecutes /diagnostico','No quiero que compruebes ahora si Ollama funciona',
           'no uses herramientas para comprobar si Ollama funciona','Jarvis, no hagas el diagnóstico de Ollama']
CONCEPTOS=['Explícame cómo funciona Ollama','¿Cómo funciona Ollama?',
           '¿Qué significa que Ollama esté funcionando?','Explícame qué es Ollama y para qué se usa',
           '¿Para qué se usa Ollama?','Hazme una guía conceptual de cómo funciona Ollama',
           '¿Cómo se utiliza Ollama en otro programa?','Explícame el ejemplo «Ollama está funcionando»']
CITADAS=['El tutorial dice «Ollama funciona»; explícame esa frase',
         'El documento dice “Jarvis usa Ollama”; quiero entenderlo',
         'El ejemplo contiene "estás conectado a Ollama"; no es una consulta de estado',
         'Si dijera «verifica si estás usando Ollama», ¿qué harías?',
         'La frase «Ollama está funcionando» tiene tres palabras importantes; explícala',
         'Traduce al inglés: “Ollama está funcionando”',
         'Cachai, el ejemplo dice «revisa si Ollama responde» po',
         'Tengo anotado «Ollama funciona»; no te estoy pidiendo comprobarlo']
CASOS=[{'id':f'E6-{i+1:03d}','familia':f,'pedido':p,'diagnostico_esperado':f=='positiva'}
       for i,(f,p) in enumerate([(f,p) for f,grupo in [('positiva',POSITIVAS),('negativa',NEGATIVAS),('concepto',CONCEPTOS),('citada',CITADAS)] for p in grupo])]


def evaluar(ronda):
    if not ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    REPORTES.mkdir(parents=True,exist_ok=True);cp=REPORTES/'corpus.json'
    raw=(json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n').encode()
    if cp.exists() and cp.read_bytes()!=raw:raise ValueError('El corpus congelado cambió.')
    if not cp.exists():cp.write_bytes(raw)
    sha=hashlib.sha256(raw).hexdigest();cp.with_suffix('.sha256').write_text(sha+'\n')
    p=REPORTES/(ronda+'.jsonl')
    if p.exists():raise ValueError('La ronda ya existe; no se sobrescriben fallos.')
    filas=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-estado-lenguaje-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        import configuracion_jarvis as C
        import interfaz_jarvis as I
        import interfaz_local as L
        Path(tmp,'trabajo').mkdir(exist_ok=True)
        with p.open('x') as log:
            os.chmod(p,0o600)
            for caso in CASOS:
                c=Mock();c.llamar.return_value={'ok':True,'consultado':'2030-01-01T00:00:00+00:00','fuentes':[]}
                diagnostico={'ok':True,'version':'VERSION_FICTICIA_41','modelos':[C.DEFAULT['modelo']]}
                acciones=[];permisos=[];estado={};h=[{'role':'system','content':'Datos sintéticos, sin modelo.'}]
                def denegar(t):permisos.append(t);return False
                def bloquear(n,*a):acciones.append(n);return {'ok':False,'error':'Herramientas bloqueadas en este arnés.'}
                local=lambda p,h,e:L.comando_local(p,h,e,denegar,dict(C.DEFAULT),lambda:None,c,ejecutar=bloquear)
                with patch.object(L.O,'diagnostico',return_value=diagnostico) as consultar:
                    manejado,texto=I.comando(caso['pedido'],h,estado,bloquear,'reglas',local=local)
                ok=consultar.call_count==1 and manejado and 'VERSION_FICTICIA_41' in texto if caso['diagnostico_esperado'] else consultar.call_count==0
                ok=ok and not acciones and not permisos
                fila=dict(caso,ok=ok,manejado=manejado,respuesta=texto,consultas_diagnostico=consultar.call_count,
                          consultas_mcp=[x.args[0] for x in c.llamar.call_args_list],herramientas=acciones,permisos=len(permisos))
                filas.append(fila);log.write(json.dumps(fila,ensure_ascii=False)+'\n')
    resumen={'ronda':ronda,'corpus_sha256':sha,'casos':len(filas),'aprobados':sum(x['ok'] for x in filas),
             'por_familia':{f:{'casos':sum(x['familia']==f for x in filas),'aprobados':sum(x['familia']==f and x['ok'] for x in filas)} for f in ['positiva','negativa','concepto','citada']},
             'fallos':[x['id'] for x in filas if not x['ok']],
             'alcance':'Despacho real con diagnóstico y MCP simulados; sin inferencia ni red real. No confundir una explicación conceptual o una cita con una consulta del equipo.'}
    p.with_suffix('.resumen.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n');print(json.dumps(resumen,ensure_ascii=False))
    return 0 if all(x['ok'] for x in filas) else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ronda',required=True);a=p.parse_args();raise SystemExit(evaluar(a.ronda))
