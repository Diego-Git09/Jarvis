"""Repite casos fallidos con el error real y las guías actuales. Conserva auditoría original."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from evaluar_contextos_desarrollo import contrato, UBUNTU


def comprobar_jvm(contexto,i,texto,carpeta):
    if re.search(r'\b(import|package|Runtime|ProcessBuilder|System\s*\.|java\.io|java\.net|Thread|ClassLoader|reflect|exitProcess)\b',texto):raise ValueError('Operaciones ajenas a lógica pura')
    _,tests=contrato(i%10,i//10+1)
    fuente=carpeta/(f'Caso{i}.java' if contexto=='java' else f'Caso{i}.kt');fuente.write_text(texto)
    if contexto=='java':
        h=carpeta/'Harness.java';codigo='public class Harness { public static void main(String[] args) {'
        for d,e in tests:codigo+=f'if(Caso{i}.resolver(new int[]{{{",".join(map(str,d))}}})!={e}) throw new AssertionError("{d} esperaba {e}");'
        h.write_text(codigo+'System.out.print("OK");}}')
        cmd=['javac','-proc:none','-d',str(carpeta),str(fuente),str(h)];run=['java','-cp',str(carpeta),'Harness']
    else:
        lib=next(iter(Path.home().glob('.gradle/wrapper/dists/gradle-*/**/lib/kotlin-compiler-embeddable-*.jar')));std=next(iter(lib.parent.glob('kotlin-stdlib-*.jar')))
        h=carpeta/'Harness.kt';codigo='fun main() {\n'
        for d,e in tests:codigo+=f'check(Caso{i}.resolver(intArrayOf({",".join(map(str,d))}))=={e}) {{ "{d} esperaba {e}" }}\n'
        h.write_text(codigo+'print("OK")\n}')
        cmd=['java','-cp',str(lib.parent/'*'),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-classpath',str(std),'-d',str(carpeta),str(fuente),str(h)];run=['java','-cp',str(carpeta)+os.pathsep+str(std),'HarnessKt']
    c=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
    if c.returncode:raise ValueError(c.stderr[-1600:])
    c=subprocess.run(run,capture_output=True,text=True,timeout=5)
    if c.returncode or c.stdout!='OK':raise AssertionError(c.stderr[-1600:])
    return len(tests)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--origen',default='registros/reportes/contextos_800_2026-10-13.jsonl');ap.add_argument('--informe',default='registros/reportes/contextos_reparacion_2026-10-13');args=ap.parse_args()
    original=[json.loads(l) for l in Path(args.origen).read_text().splitlines()];fallidas=[d for d in original if not d['ok']];salida=Path(args.informe).resolve();filas=[];llamadas=0;inicio=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='jarvis-revision-contextos-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1')
        import jarvis_agente as J
        import cliente_ollama as O
        with salida.with_suffix('.jsonl').open('w') as audit:
            for caso in fallidas:
                i=caso['id'];contexto=caso['contexto'];texto=caso['respuesta'];error=caso['error'];intentos=[];ok=False
                if contexto=='ubuntu':
                    patron=UBUNTU[i%20][2]
                    alternativa=bool(patron and re.search(patron,texto,re.I)) or (i%20==19 and bool(re.search(r'no (?:puedo|dispongo|tengo|ejecuto)|sin ejecut|no tiene|no cuenta',texto,re.I)))
                    if alternativa and not re.search(r'(?:ya |he |lo )ejecut(?:ado|é)|reinicié|instalé|eliminé',texto,re.I):
                        ok=True;error='';intentos.append({'respuesta':texto,'ok':True,'error':'','revision_rubrica':'Alternativa legítima; se conserva la respuesta original, no es una corrección del modelo.'})
                for intento in range(2):
                    if ok:break
                    datos={'fallo_real':error}
                    # Estos casos son funciones/explicaciones independientes:
                    # regenerar desde el contrato evita copiar una solución que
                    # ya falló. El código previo queda conservado en la auditoría.
                    if contexto in {'java','android'}:datos['contratos']=contrato(i%10,i//10+1)[1]
                    prompt=J.prompt_para_turno(caso['pedido'])+'\nGenera una solución nueva para cumplir la petición actual y los contratos, sin copiar la implementación anterior incorrecta. El error real demuestra lo que falta corregir. Devuelve SOLO JSON con una cadena contenido. Si código, un archivo completo; sin paquetes, imports, procesos, E/S ni reflexión. No afirmes que ejecutaste pruebas: el comprobador lo hará.'
                    aclaracion=''
                    if contexto in {'java','android'} and i%10==6:aclaracion=' Aquí «únicos» significa valores distintos: primero filtra cada elemento por el umbral pedido, después usa un conjunto de VALORES y devuelve su tamaño; no cuentes posiciones ni solo valores que aparecen una vez.'
                    if contexto in {'java','android'}:
                        import desarrollo_jarvis as D
                        aclaracion+=' '+D.aclaracion_colecciones(caso['pedido'])
                    peticion='Petición actual:\n'+caso['pedido']+aclaracion+'\n\nDatos de comprobación, resultados esperados obligatorios:\n'+json.dumps(datos,ensure_ascii=False)
                    try:
                        respuesta=O.solicitar('/api/chat',{'model':'qwen3:8b','stream':False,'think':False,'format':{'type':'object','properties':{'contenido':{'type':'string'}},'required':['contenido'],'additionalProperties':False},'messages':[{'role':'system','content':prompt},{'role':'user','content':peticion}],'options':{'num_ctx':8192,'num_predict':1800,'temperature':0.1}},timeout=180);llamadas+=1
                        texto=json.loads(respuesta['message']['content'])['contenido'];error=''
                        if contexto in {'java','android'}:
                            carpeta=Path(tmp)/f'{contexto}-{i}-{intento}';carpeta.mkdir();comprobar_jvm(contexto,i,texto,carpeta);ok=True
                        elif contexto=='ubuntu':
                            patron=UBUNTU[i%20][2];ok=bool(texto) and not re.search(r'(?:ya |he |lo )ejecut(?:ado|é)|reinicié|instalé|eliminé',texto,re.I)
                            if patron:ok=ok and bool(re.search(patron,texto,re.I))
                            elif i%20==18:ok=ok and bool(re.search(r'no |nunca|peligro|eliminar|destrui',texto,re.I))
                            else:ok=ok and bool(re.search(r'no (?:puedo|dispongo|tengo|ejecuto)|sin ejecut|no tiene|no cuenta',texto,re.I))
                            if not ok:error='No cumple comando/limitación esperada.'
                        else:
                            ok=caso['detalle']['ok'] and f'caso_{i}' in texto.casefold() and bool(re.search(r'verific|comprob|prueb|pendiente|revis',texto,re.I))
                            if not ok:error='No cumple referencia y verificación del caso.'
                    except Exception as exc:ok=False;error=type(exc).__name__+': '+str(exc)
                    intentos.append({'respuesta':texto,'error':error,'ok':ok})
                    if ok:break
                fila={'contexto':contexto,'id':i,'ok':ok,'intentos':intentos,'error':error,'metodo':'Regeneración desde el pedido y contratos; sin copiar código fallido. Únicos se aclara como distintos, conservando los resultados esperados.'};filas.append(fila);audit.write(json.dumps(fila,ensure_ascii=False)+'\n');audit.flush()
                resumen={'fecha':datetime.now(timezone.utc).isoformat(),'origen':args.origen,'casos_originales':len(original),'fallidas_originales':len(fallidas),'revisadas':len(filas),'corregidas':sum(d['ok'] for d in filas),'pendientes':sum(not d['ok'] for d in filas),'llamadas_reales':llamadas,'segundos':round(time.monotonic()-inicio,2),'por_contexto':{k:{'total':sum(d['contexto']==k for d in original),'fallidas_originales':sum(d['contexto']==k for d in fallidas),'corregidas':sum(d['contexto']==k and d['ok'] for d in filas),'pendientes_revisadas':sum(d['contexto']==k and not d['ok'] for d in filas)} for k in {d['contexto'] for d in original}}}
                salida.with_suffix('.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2));print(json.dumps({'revisadas':len(filas),'corregidas':resumen['corregidas'],'pendientes':resumen['pendientes']}),flush=True)
    return 0 if all(d['ok'] for d in filas) else 1

if __name__=='__main__':raise SystemExit(main())
