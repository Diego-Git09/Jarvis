"""Evaluación de Qwen con archivos temporales y permisos de prueba, nunca del usuario."""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reporte');parser.add_argument('--solo',help='Fragmento del nombre de caso; extra selecciona los nuevos escenarios');args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='jarvis-modelo-') as temporal:
        proyecto=Path(temporal)/'Jarvis';trabajo=proyecto/'trabajo';trabajo.mkdir(parents=True)
        os.environ['JARVIS_DIR']=str(proyecto)
        os.environ['JARVIS_PRUEBAS']='1'
        import jarvis_agente as J
        class CerebroPrueba:
            def llamar(self,n,a):
                if n in {'buscar_memoria','buscar_memoria_semantica','listar_memorias'}:return {'ok':True,'memorias':[]}
                return {'ok':False,'error':'Esta evaluación solo usa archivos temporales.'}
        J.CEREBRO=CerebroPrueba()
        (trabajo/'notas.txt').write_text('Comprar pan\nLlamar a Ana\n',encoding='utf-8')
        (trabajo/'origen.txt').write_text('contenido de origen\n',encoding='utf-8')
        (trabajo/'revision.txt').write_text('Uno\nDos\n',encoding='utf-8')
        (trabajo/'revision_original.txt').write_text('Uno\nDos\n',encoding='utf-8')
        casos=[
            ('leer','Lee el archivo notas.txt y dime sus dos tareas.',lambda:True,{'leer_archivo','leer_lineas'}),
            ('editar','Cambia en el archivo notas.txt la línea Comprar pan por Comprar leche. Escribe el cambio y compruébalo.',lambda:'Comprar leche' in (trabajo/'notas.txt').read_text(),{'aplicar_edicion'}),
            ('carpeta_copia','Crea la carpeta respaldo y copia el archivo notas.txt a respaldo/notas.txt. Haz ambas cosas.',lambda:(trabajo/'respaldo'/'notas.txt').is_file(),{'crear_carpeta','copiar_archivo'}),
            ('renombrar','Renombra el archivo origen.txt a final.txt.',lambda:(trabajo/'final.txt').is_file() and not (trabajo/'origen.txt').exists(),{'mover_archivo'}),
            ('deshacer','Deshaz el último movimiento del archivo final.txt. Consulta primero los cambios para saber cuál fue.',lambda:(trabajo/'origen.txt').is_file() and not (trabajo/'final.txt').exists(),{'revertir_cambio'}),
            ('no_sobrescribir','Copia el archivo notas.txt a origen.txt, pero no sobrescribas nada si el destino existe.',lambda:(trabajo/'origen.txt').read_text()=='contenido de origen\n',set()),
            ('extra_informacion','Consulta cuánto pesa el archivo revision.txt y su fecha de modificación real.',lambda:(trabajo/'revision.txt').read_text()=='Uno\nDos\n',{'informacion_archivo'}),
            ('extra_comparar','Compara los archivos revision.txt y revision_original.txt y dime si su contenido es igual.',lambda:(trabajo/'revision.txt').read_text()==(trabajo/'revision_original.txt').read_text(),{'comparar_archivos'}),
            ('extra_encontrar','Encuentra archivos por nombre: revision*.txt. Busca sus nombres sin leer el contenido.',lambda:True,{'encontrar_archivos'}),
            ('extra_editar_copiar','Cambia Dos por Tres en el archivo revision.txt. Escribe ese cambio y después copia el resultado actualizado a revision_final.txt. Completa ambas acciones.',lambda:(trabajo/'revision.txt').read_text()=='Uno\nTres\n' and (trabajo/'revision_final.txt').read_text()=='Uno\nTres\n',{'copiar_archivo'}),
            ('extra_vista_previa','Lee revision_original.txt y prepara una propuesta para cambiar Dos por Cuatro. Solo quiero ver la diferencia; no escribas ni apliques nada.',lambda:(trabajo/'revision_original.txt').read_text()=='Uno\nDos\n',{'proponer_edicion'}),
        ]
        if args.solo:casos=[c for c in casos if args.solo in c[0]]
        if not casos:print('No hay escenarios con ese nombre.');return 2
        resultados=[]
        for nombre,pedido,comprobar,requeridos in casos:
            h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':pedido}];permisos=[];inicio=time.monotonic()
            try:
                respuesta=J.ejecutar_turno(h,J.enviar_a_ollama,lambda t:permisos.append(t) or True,{},mostrar=lambda _:None)
                usadas={m.get('tool_name') for m in h if m.get('role')=='tool'}
                correcto=bool(comprobar()) and (bool(usadas&requeridos) if nombre=='leer' else bool(usadas&{'aplicar_edicion','reemplazar_texto'}) if nombre=='editar' else requeridos<=usadas)
                if nombre=='extra_vista_previa':correcto=correcto and not permisos and '-Dos' in respuesta and '+Cuatro' in respuesta and '-Uno' not in respuesta and 'Uno' in respuesta
                resultado={'caso':nombre,'ok':correcto,'segundos':round(time.monotonic()-inicio,2),'herramientas':sorted(usadas),'permisos':len(permisos),'respuesta':respuesta}
            except Exception as e:
                resultado={'caso':nombre,'ok':False,'segundos':round(time.monotonic()-inicio,2),'error':str(e),'respuesta':locals().get('respuesta',''),
                           'herramientas':[m.get('tool_name') for m in h if m.get('role')=='tool'],'permisos':len(permisos)}
            resultados.append(resultado)
            print(json.dumps(resultado,ensure_ascii=False),flush=True)
        if args.reporte:
            Path(args.reporte).write_text(json.dumps(resultados,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0 if all(r['ok'] for r in resultados) else 1


if __name__=='__main__':raise SystemExit(main())
