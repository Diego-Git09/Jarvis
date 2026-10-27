"""Conversaciones reales largas con decisiones tempranas y reapertura de proceso.

Solo usa un proyecto temporal sintético. Herramientas y nube están bloqueadas;
las respuestas proceden de Ollama, salvo los accesos del controlador registrados.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

RAIZ=Path(__file__).resolve().parents[1]
INFORMES=RAIZ/'registros/reportes/mejora_6h_20261014'
RUBRICA={'version':2,'retencion':'Cada literal oro debe aparecer exacto en la respuesta.',
    'fase_002':'Debe dar un paso concreto de Android (New Project/Empty Activity); no otro menú.',
    'fases_003_004':'Debe conservar el paso e indicar carpeta y Gradle o mostrar la guía inicial concreta.',
    'bucle':'No volver a preguntar qué opción elegir, si quiere comenzar o si quiere ayuda para configurar.',
    'respuesta':'No vacía; no error local ni denegación del arnés presentada como respuesta terminada.'}


def evaluar_respuesta(c,texto):
    fallos=[]
    if any(x not in texto for x in c['literales_oro']):fallos.append('Decisión temprana ausente o alterada')
    if not texto.strip() or texto.startswith(('No pude','Me detuve','Herramientas deshabilitadas')):fallos.append('Respuesta local incompleta')
    fase=int(c['id'].rsplit('-',1)[1])
    if fase in {2,3,4}:
        guia=bool(re.search(r'New Project|Empty Activity',texto))
        if fase==2 and not guia:fallos.append('No avanzó al primer paso concreto de Android')
        if fase in {3,4} and not (guia or 'carpeta' in texto.casefold() and 'gradle' in texto.casefold()):fallos.append('No continuó con el paso o los datos técnicos pendientes')
        if re.search(r'(?i)¿(?:qué opción|quieres (?:que te ayude|continuar|que empecemos|que comencemos)|confirmas.*(?:empecemos|comencemos))',texto):fallos.append('Reconfirmación general o menú repetido')
    return fallos


def corpus():
    resultado=[]
    temas=['por qué usar datos sintéticos','distinguir tránsito de compra','qué significa MVVM',
           'cómo separar pantalla y datos','qué revisar en un formulario','una prueba de validación',
           'para qué sirve Room','qué mostrar en el resumen diario','manejar datos faltantes',
           'explicar una API REST','qué es un estado de carga','qué revisar en una lista vacía']
    for corrida,nombre,paquete,presupuesto in [(1,'LAPIZ_ROSADO_A17','cl.ejemplo.lapizrosado',271),(2,'NUBE_AZUL_B23','cl.ejemplo.nubeazul',632)]:
        turnos=[]
        for i in range(112):
            p=f'Sobre el caso de la tienda, explica {temas[i%len(temas)]} en una frase breve, sin herramientas ni acciones.'
            oro=[]
            if i==0:p='Ayúdame con el caso sintético de la tienda adjunto en Kotlin Android Studio. Explica brevemente y ofrece cuatro opciones: iniciar proyecto, funcionalidades, carpetas, pantalla. Sin crear ni ejecutar archivos.'
            elif i==1:p=f'Decidimos para el caso de la tienda: nombre literal "{nombre}", paquete "{paquete}", presupuesto {presupuesto} y 4 accesos. Conserva estas decisiones, sin escribir archivos. Confirma brevemente.'
            elif i==2:p='SI te confirmo empecemos'
            elif i==3:p='empecemos con el 1'
            elif i==4:p='empecemos a hacer el caso'
            elif i==30:p='Otro tema: explícame cómo cocinar arroz en una frase breve; no uses el documento.'
            elif i in {31,32,33,34}:p='Sobre el arroz, explica por qué conviene medir el agua. Una frase, sin herramientas.'
            elif i==35:p='Vuelve al caso de la tienda; explica brevemente el siguiente paso, sin ejecutar nada.'
            elif i in {20,55,56,80,111}:
                p='Como dijimos al principio del caso de la tienda, dime el nombre literal elegido, el paquete, el presupuesto y la cantidad de accesos. No inventes valores ni uses herramientas. Cuatro datos breves.'
                oro=[nombre,paquete,str(presupuesto),'4']
            turnos.append({'id':f'R{corrida}-{i:03d}','pedido':p,'literales_oro':oro,'reinicio_antes':i==56})
        resultado.append({'corrida':corrida,'turnos':turnos})
    return resultado


def congelar():
    INFORMES.mkdir(parents=True,exist_ok=True)
    p=INFORMES/'corpus_resistencia_real.json';raw=(json.dumps(corpus(),ensure_ascii=False,indent=2)+'\n').encode()
    if p.exists() and p.read_bytes()!=raw:raise ValueError('El corpus real congelado cambió')
    p.write_bytes(raw);(INFORMES/'corpus_resistencia_real.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n')
    r=(json.dumps(RUBRICA,ensure_ascii=False,indent=2)+'\n').encode();rp=INFORMES/'rubrica_resistencia_v2.json'
    if rp.exists() and rp.read_bytes()!=r:raise ValueError('La rúbrica V2 congelada cambió')
    rp.write_bytes(r);rp.with_suffix('.sha256').write_text(hashlib.sha256(r).hexdigest()+'\n')
    return p


def trabajador(a):
    os.environ.update(JARVIS_DIR=a.proyecto,JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1')
    import jarvis_agente as J
    import contexto_jarvis as C
    import tandas_documentales as T
    import hilo_conversacion as H
    from medir_rendimiento_jarvis import recursos
    base=Path(a.proyecto);base.joinpath('trabajo').mkdir(exist_ok=True)
    J.AJUSTES.update(num_ctx=8192,num_predict=256,timeout_modelo=120)
    J.OPCIONES.update(num_ctx=8192,num_predict=256,temperature=0)
    casos=json.loads(Path(a.corpus).read_text())[a.corrida-1]['turnos']
    h=[{'role':'system','content':J.SISTEMA}];estado={}
    if a.inicio:
        H.recuperar(estado)
    else:
        archivo=base/'trabajo/caso_sintetico.txt'
        archivo.write_text('Caso sintético Tienda Ficticia: 4 accesos; contar tránsito y compradores con datos sintéticos. Aplicación Kotlin Android Studio, Jetpack Compose, MVVM, Material 3, API REST Spring Boot y Room. No contiene datos reales, versiones obligatorias ni credenciales.')
        tanda=T.indexar(T.crear([archivo])['id'],semantico=False)
        estado['_tanda_documentos']=tanda['id']
    salida=Path(a.salida)
    with salida.open('a',encoding='utf8') as f:
        os.chmod(salida,0o600)
        for c in casos[a.inicio:a.fin]:
            p=c['pedido'];h[0]['content']=J.prompt_para_turno(p,estado);permisos=[];acciones=[];llamadas=[]
            def denegar(t):permisos.append(t);return False
            def bloquear(n,args,*_):acciones.append(n);return {'ok':False,'error':'Herramientas deshabilitadas en evaluación sintética; ninguna acción ejecutada.'}
            real=J.O.solicitar
            def auditar(ruta,cuerpo=None,**kw):
                r=real(ruta,cuerpo,**kw)
                if ruta=='/api/chat':llamadas.append({'tokens_entrada':r.get('prompt_eval_count'),'tokens_salida':r.get('eval_count'),'fin':r.get('done_reason')})
                return r
            inicio=time.monotonic();antes=recursos()
            with patch.object(J.IA.P,'opciones',return_value={'configurado':False,'automatico':False,'timeout_local':35,'preferido':''}),patch.object(J.IA,'preguntar_externa',side_effect=AssertionError('Nube bloqueada')),patch.object(J,'ejecutar_herramienta',side_effect=bloquear),patch.object(J.O,'solicitar',side_effect=auditar):
                local=lambda texto,hist,st:J.comando_local(texto,hist,st,denegar,J.AJUSTES,lambda:None,None,ejecutar=bloquear)
                manejado,texto=J.comando(p,h,estado,bloquear,J.SISTEMA,local=local)
                if not manejado:
                    h.append({'role':'user','content':p})
                    texto=J.responder_con_respaldo(h,J.enviar_a_ollama,denegar,estado,mostrar=lambda _:None)
            fallos=evaluar_respuesta(c,texto)
            fila=dict(c,respuesta=texto,ok=not fallos,fallos=fallos,segundos=round(time.monotonic()-inicio,3),
                      llamadas_ollama=llamadas,controlador_sin_inferencia=not llamadas,permisos_solicitados=len(permisos),
                      herramientas_propuestas=acciones,escrituras_ejecutadas=0,nube=0,recursos_antes=antes,recursos_despues=recursos(),
                      estadisticas=dict(J.ESTADISTICAS),hilo_id=estado.get('_id_hilo'),tanda=estado.get('_tanda_documentos'),
                      contexto=C.estado_contexto(h))
            f.write(json.dumps(fila,ensure_ascii=False)+'\n');f.flush()
            print(json.dumps({'id':c['id'],'ok':fila['ok'],'segundos':fila['segundos'],'llamadas':len(llamadas)}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--corrida',type=int,choices=[1,2],required=True);p.add_argument('--ronda',default='primero');p.add_argument('--trabajador',action='store_true');p.add_argument('--proyecto');p.add_argument('--corpus');p.add_argument('--salida');p.add_argument('--inicio',type=int,default=0);p.add_argument('--fin',type=int,default=112);a=p.parse_args()
    if a.trabajador:return trabajador(a)
    c=congelar();destino=INFORMES/f'resistencia_real_{a.corrida}_{a.ronda}.jsonl'
    if destino.exists():raise ValueError('La ronda ya existe; no se sobrescriben respuestas originales.')
    with tempfile.TemporaryDirectory(prefix='jarvis-real-6h-') as tmp:
        for inicio,fin in [(0,56),(56,112)]:
            subprocess.run([sys.executable,'-B',__file__,'--trabajador','--corrida',str(a.corrida),'--proyecto',tmp,'--corpus',str(c),'--salida',str(destino),'--inicio',str(inicio),'--fin',str(fin)],check=True)
    filas=[json.loads(x) for x in destino.read_text().splitlines()]
    r={'corrida':a.corrida,'ronda':a.ronda,'turnos':len(filas),'llamadas_reales_ollama':sum(len(x['llamadas_ollama']) for x in filas),
       'turnos_con_inferencia':sum(bool(x['llamadas_ollama']) for x in filas),'correctos':sum(x['ok'] for x in filas),
       'consultas_decisiones':sum(bool(x['literales_oro']) for x in filas),'decisiones_correctas':sum(x['ok'] for x in filas if x['literales_oro']),
       'fallos':[x['id'] for x in filas if not x['ok']], 'reinicio_real_proceso_antes_de_turno':56,
       'modelo':'qwen3:8b','contexto':8192,'limite_respuesta':256,'corpus_sha256':hashlib.sha256(c.read_bytes()).hexdigest(),
       'alcance':'Ollama real, datos sintéticos, dos procesos consecutivos. No es prueba de escrituras o interfaz gráfica. Los inicios Android del controlador no se cuentan como inferencia.'}
    destino.with_suffix('.resumen.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))

if __name__=='__main__':main()
