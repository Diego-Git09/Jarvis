"""Evalúa diálogo real con Ollama y un Segundo Cerebro ficticio, sin guardar turnos."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time


class CerebroSimulado:
    def __init__(self):self.llamadas=[]
    def llamar(self,n,a):
        self.llamadas.append((n,dict(a)))
        nota={'id':901,'proyecto':'Jarvis','titulo':'Interfaz clara','contenido':'Diego pidió una interfaz oscura y adaptable.','creado':'2026-10-12T20:00:00+00:00','tipo':'recuerdo'}
        if n=='consultar_estado_cerebro':return {'ok':True,'consultado':'2026-10-12T21:00:00-03:00','fuentes':[{'fuente':'codex','estado':'ok','lectura_reciente':True,'pendientes':0}]}
        if n=='listar_proyectos':return {'ok':True,'proyectos':[{'proyecto':'Jarvis','recuerdos':1,'conversaciones':0,'total':1},{'proyecto':'CHAT JARVIS','recuerdos':0,'conversaciones':3,'total':3},{'proyecto':'sin_clasificar','recuerdos':0,'conversaciones':0,'total':0}]}
        if n=='consultar_ultimo_recuerdo':return {'ok':True,'estado':'encontrada','recuerdo':nota}
        if n=='consultar_memoria':return {'ok':True,'memorias':[nota]}
        if n in {'buscar_memoria','buscar_memoria_semantica','listar_memorias'}:return {'ok':True,'memorias':[nota]}
        return {'ok':False,'error':'Esta evaluación no realiza cambios en recuerdos.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reporte',type=Path,required=True);p.add_argument('--solo',default='');args=p.parse_args()
    os.environ['JARVIS_PRUEBAS']='1'
    with tempfile.TemporaryDirectory(prefix='jarvis-dialogo-') as tmp:
        os.environ['JARVIS_DIR']=tmp
        import jarvis_agente as J
        from interfaz_local import comando_local
        cerebro=CerebroSimulado();J.CEREBRO=cerebro
        casos=[
            ('acceso','Puedes ver mi segundo cerebro?',('puedo','cerebro')),
            ('acceso_cortesia','Hola Jarvis, puedes acceder a mi Segundo Cerebro directamente?',('puedo','cerebro')),
            ('acceso_alternativo','Tienes acceso a mi Segundo Cerebro?',('cerebro',)),
            ('ideas_literal','Jarvis dame ideas para mejorarte la idea es que chat este trabajando en ti durante una hora aplicandote mejoras y entrenamiento para que puedas funcionar de forma perfecta',('mejora','entrenamiento')),
            ('ideas_sinonimos','Dame sugerencias para perfeccionarte',('mejora',)),
            ('ideas_breve','Qué cosas puedo mejorar de ti',('reforzar',)),
            ('ultimo','Muéstrame el último recuerdo que guardó Segundo Cerebro y su proyecto',('interfaz','jarvis')),
            ('proyectos','Muéstrame mis proyectos de Segundo Cerebro',('chat jarvis','jarvis')),
            ('hola','Hola Jarvis',()),
            ('pregunta_nueva','Ayúdame a organizar mi semana de estudio con tres pasos',('paso',)),
            ('cacho','Tengo un cacho con la memoria. ¿Qué significa cacho en Chile?',('problema',)),
            ('tinca_permiso','Si digo me tinca mover ese recuerdo, ¿ya te autorizo a moverlo?',('no',)),
            ('al_tiro','Qué significa al tiro en Chile?',()),
            ('bacan','Qué significa bacán en Chile?',()),
            ('fome','Explícame la palabra fome como la usamos en Chile',()),
            ('cachai','Qué quiere decir cachai?',()),
            ('tarea_ambigua','Mueve eso al otro proyecto',()),
            ('capacidad_memoria','Qué herramientas tienes para consultar recuerdos y conversaciones?',('recuerdos',)),
            ('practica','Cómo puedo practicar contigo para que entiendas mejor mi español chileno?',()),
            ('no_confundir','Quiero ideas para mejorar tu interfaz; no te estoy corrigiendo una palabra',('interfaz',)),
        ]
        resultados=[]
        for nombre,pedido,esperadas in casos:
            if args.solo and args.solo not in nombre:continue
            estado={};h=[{'role':'system','content':J.prompt_para_turno(pedido,estado)}];permisos=[];inicio=time.monotonic();cerebro.llamadas=[]
            confirmar=lambda texto:permisos.append(texto) or False
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,confirmar,estado)
            local=lambda p,h,e:comando_local(p,h,e,confirmar,J.AJUSTES,lambda:None,cerebro,J.ESTADISTICAS,ejecutar)
            J.ESTADISTICAS.clear()
            try:
                manejado,texto=J.comando(pedido,h,estado,ejecutar,J.SISTEMA,local=local)
                if not manejado:
                    h.append({'role':'user','content':pedido})
                    texto=J.ejecutar_turno(h,J.enviar_a_ollama,confirmar,estado,mostrar=lambda _:None)
                normal=texto.casefold()
                falta=[x for x in esperadas if x not in normal]
                ajeno='/no_think' in normal or 'no puedo confirmar qué significa' in normal
                if nombre=='ultimo':
                    falta+=[] if 'consultar_ultimo_recuerdo' in [n for n,a in cerebro.llamadas] else ['consulta del último recuerdo']
                r={'caso':nombre,'ok':bool(texto.strip()) and not falta and not ajeno and not permisos,
                   'segundos':round(time.monotonic()-inicio,2),'ruta':'local' if manejado else 'modelo',
                   'palabras_faltantes':falta,'termino_ajeno':ajeno,'permisos':len(permisos),'respuesta':texto,'estadisticas':dict(J.ESTADISTICAS),
                   'consultas_memoria':[n for n,a in cerebro.llamadas]}
            except Exception as e:r={'caso':nombre,'ok':False,'error':str(e),'segundos':round(time.monotonic()-inicio,2)}
            resultados.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
            args.reporte.parent.mkdir(parents=True,exist_ok=True)
            args.reporte.write_text(json.dumps(resultados,ensure_ascii=False,indent=2)+'\n')
        return 0 if resultados and all(r['ok'] for r in resultados) else 1


if __name__=='__main__':raise SystemExit(main())
