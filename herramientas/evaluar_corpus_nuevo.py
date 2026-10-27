"""Evalúa el corpus congelado: primer intento y correcciones se conservan separados."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

def comprobar(codigo,caso,carpeta):
    c=caso['contexto'];i=caso['id'];carpeta.mkdir(parents=True,exist_ok=True)
    if c=='python':
        # Los contratos sintéticos no autorizan lecturas/red del código generado.
        tree=ast.parse(codigo)
        for n in ast.walk(tree):
            if isinstance(n,(ast.Import,ast.ImportFrom)):
                nombres=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module or '']
                if any(x.split('.')[0] not in {'collections','math','datetime','re','itertools'} for x in nombres):raise ValueError('Importación fuera de la rúbrica pura')
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'open','eval','exec','compile','__import__','input'}:raise ValueError('Operación fuera de lógica pura')
        (carpeta/'logica.py').write_text(codigo)
        test='import unittest\nfrom logica import resolver,etiqueta\nclass Contrato(unittest.TestCase):\n'
        test+=f' def test_etiqueta(self):self.assertEqual(etiqueta(),{caso["etiqueta"]!r})\n'
        for k,(args,expected) in enumerate(caso['contratos']):
            if caso.get('contratos_repr'):expected=ast.literal_eval(caso['contratos_repr'][k])
            test+=f' def test_{k}(self):self.assertEqual(resolver(*{args!r}),{expected!r})\n'
        (carpeta/'test_logica.py').write_text(test)
        r=subprocess.run([os.sys.executable,'-B','-m','unittest','test_logica'],cwd=carpeta,capture_output=True,text=True,timeout=8)
        if r.returncode:raise AssertionError(r.stderr[-2000:])
    elif c=='sql':
        from validacion_codigo import comprobar_sql
        p=carpeta/'datos.sql';p.write_text(codigo);t=carpeta/'pruebas_sql.json';t.write_text(json.dumps(caso['contratos']))
        comprobar_sql([str(p)],str(t))
    elif c in {'java','android'}:
        if re.search(r'\b(import|package|Runtime|ProcessBuilder|System\s*\.|java\.io|java\.net|Thread|ClassLoader|reflect|exitProcess)\b',codigo):raise ValueError('Operación fuera de lógica JVM pura')
        p=carpeta/f'Nuevo{i}.{"java" if c=="java" else "kt"}';p.write_text(codigo)
        if c=='java':
            h=carpeta/'Harness.java';s='public class Harness { public static void main(String[] args) {'
            for d,e in caso['contratos']:s+=f'if(Nuevo{i}.resolver(new int[]{{{",".join(map(str,d))}}})!={e})throw new AssertionError("{d}: {e}");'
            s+='System.out.print("OK");}}';h.write_text(s);cmd=['javac','-proc:none','-d',str(carpeta),str(p),str(h)];run=['java','-cp',str(carpeta),'Harness']
        else:
            lib=next(iter(Path.home().glob('.gradle/wrapper/dists/gradle-*/**/lib/kotlin-compiler-embeddable-*.jar')),None)
            if not lib:raise ValueError('Compilador Kotlin no disponible')
            std=next(lib.parent.glob('kotlin-stdlib-*.jar'));h=carpeta/'Harness.kt';s='fun main() {\n'
            for d,e in caso['contratos']:s+=f'check(Nuevo{i}.resolver(intArrayOf({",".join(map(str,d))}))=={e}) {{ "{d}: {e}" }}\n'
            h.write_text(s+'print("OK")\n}');cmd=['java','-cp',str(lib.parent/'*'),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-classpath',str(std),'-d',str(carpeta),str(p),str(h)];run=['java','-cp',str(carpeta)+os.pathsep+str(std),'HarnessKt']
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
        if r.returncode:raise ValueError(r.stderr[-1500:])
        r=subprocess.run(run,capture_output=True,text=True,timeout=5)
        if r.returncode or r.stdout!='OK':raise AssertionError(r.stderr[-1500:])
    else:
        if not re.search(caso['patron'],codigo,0 if c=='entrenamiento' else re.I):raise AssertionError('No cumplió el criterio de comando/etiqueta fijado.')
        if caso.get('patron_adicional') and not re.search(caso['patron_adicional'],codigo):raise AssertionError('Falta indicar lo pendiente de verificar.')
        if re.search(caso['prohibido'],codigo):raise AssertionError('Afirma una ejecución no comprobada.')
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('--corpus',default='registros/reportes/ampliacion_20261014/corpus_1200_previo.json');p.add_argument('--contextos',default='python,sql,java,android,ubuntu,entrenamiento');p.add_argument('--ids');p.add_argument('--continuar',action='store_true');p.add_argument('--informe',default='registros/reportes/ampliacion_20261014/casos_nuevos');a=p.parse_args()
    corpus=Path(a.corpus).read_bytes();d=json.loads(corpus);sha=hashlib.sha256(corpus).hexdigest();dest=Path(a.informe);rows=[]
    if a.continuar and dest.with_suffix('.jsonl').exists():rows=[json.loads(l) for l in dest.with_suffix('.jsonl').read_text().splitlines() if l]
    vistos={(r['contexto'],r['id']) for r in rows};assert len(vistos)==len(rows)
    t0=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='jarvis-corpus-nuevo-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1');base=Path(tmp);(base/'trabajo').mkdir()
        import cliente_ollama as O
        import jarvis_agente as J
        import proyectos_codigo as P
        from conversaciones_jarvis import _redactar
        def guardar():
            resumen={'corpus_sha256':sha,'casos':len(rows),'primer_intento':sum(r['primer_ok'] for r in rows),'final_tras_correcciones':sum(r['final_ok'] for r in rows),'llamadas':sum(r.get('llamadas',0) for r in rows),'segundos_esta_ejecucion':round(time.monotonic()-t0,2),'contextos':{c:{'casos':sum(r['contexto']==c for r in rows),'primer_intento':sum(r['contexto']==c and r['primer_ok'] for r in rows),'final':sum(r['contexto']==c and r['final_ok'] for r in rows)} for c in a.contextos.split(',')}}
            dest.with_suffix('.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2));print(json.dumps(resumen['contextos']),flush=True)
        with dest.with_suffix('.jsonl').open('a' if a.continuar else 'w') as audit:
            for c in a.contextos.split(','):
                ids={int(i) for i in a.ids.split(',')} if a.ids else None
                casos=[x for x in d['casos'] if x['contexto']==c and (c,x['id']) not in vistos and (ids is None or x['id'] in ids)]
                lote=1 if c in {'python','sql'} else 5
                for off in range(0,len(casos),lote):
                    grupo=casos[off:off+lote];salidas={};llamadas=[]
                    if lote==1:
                        caso=grupo[0];carpeta=base/'trabajo'/f'{c}_{caso["id"]}';archivo='logica.py' if c=='python' else 'datos.sql'
                        # Cada caso independiente usa su propio registro sintético;
                        # no modifica el límite de 100 proyectos del programa.
                        P.ARCHIVO=base/'datos'/f'proyecto_{c}_{caso["id"]}.json'
                        assert P.ejecutar('iniciar_proyecto_codigo',{'nombre':carpeta.name,'ruta':str(carpeta),'objetivo':caso['pedido']},lambda _:True,{})['ok']
                        assert P.ejecutar('actualizar_plan_codigo',{'etapas_json':json.dumps([{'titulo':'Lógica con contratos','archivos':[archivo]}])},lambda _:True,{})['ok']
                        # Los contratos son fijos y se entregan al generador para comprobar el archivo.
                        if c=='python':
                            dummy='def resolver(*args):return None\ndef etiqueta():return ""\n';comprobar_error=None
                            try:comprobar(dummy,caso,carpeta)
                            except AssertionError:pass
                            (carpeta/'logica.py').unlink()
                        else:(carpeta/'pruebas_sql.json').write_text(json.dumps(caso['contratos']))
                        def enviar(ruta,payload,**kw):
                            r=O.solicitar(ruta,payload,**kw);llamadas.append({'respuesta':r.get('message',{}).get('content',''),'fin':r.get('done_reason'),'tokens':r.get('eval_count')});return r
                        try:respuesta=P.desarrollar(caso['pedido'],{},lambda _:True,enviar,'qwen3:8b')
                        except Exception as e:respuesta=type(e).__name__+': '+str(e)
                        primeros={}
                        for n,r in enumerate(llamadas):
                            try:salidas.setdefault(caso['id'],[]).append(json.loads(r['respuesta'])['contenido'])
                            except (ValueError,KeyError,TypeError):salidas.setdefault(caso['id'],[]).append('')
                    else:
                        formato={'type':'object','properties':{'respuestas':{'type':'array','items':{'type':'object','properties':{'id':{'type':'integer'},'contenido':{'type':'string'}},'required':['id','contenido'],'additionalProperties':False}}},'required':['respuestas'],'additionalProperties':False}
                        for intento in range(2):
                            pendientes=[x for x in grupo if intento==0 or not salidas.get(x['id'],[]) or not salidas[x['id']][-1]['ok']]
                            if not pendientes:break
                            prompt=J.prompt_para_turno(pendientes[0]['pedido'])+'\nCada caso es independiente. JSON respuestas con id y contenido completo por caso. Sin herramientas. No combines clases ni tareas.'
                            pedidos=[{'id':x['id'],'pedido':x['pedido']+(('\nError anterior: '+salidas[x['id']][-1]['error']) if intento and salidas.get(x['id']) else '')} for x in pendientes]
                            texto_pedidos='Peticiones actuales del usuario; cada una es independiente:\n\n'+'\n\n'.join(f'ID {x["id"]}:\n{x["pedido"]}' for x in pedidos)
                            formato['properties']['respuestas'].update(minItems=len(pedidos),maxItems=len(pedidos))
                            formato['properties']['respuestas']['items']['properties']['id']['enum']=[x['id'] for x in pedidos]
                            try:
                                r=O.solicitar('/api/chat',{'model':'qwen3:8b','stream':False,'think':False,'format':formato,'messages':[{'role':'system','content':prompt},{'role':'user','content':texto_pedidos}],'options':{'num_ctx':8192,'num_predict':3500,'temperature':0.1}},timeout=180)
                                llamadas.append({'respuesta':r['message']['content'],'fin':r.get('done_reason'),'tokens':r.get('eval_count')});rs={x['id']:x['contenido'] for x in json.loads(r['message']['content'])['respuestas']}
                            except Exception as e:rs={};llamadas.append({'error':type(e).__name__})
                            for x in pendientes:
                                texto=rs.get(x['id'],'');error=''
                                try:ok=comprobar(texto,x,base/'validacion'/f'{c}_{x["id"]}_{intento}')
                                except Exception as e:ok=False;error=type(e).__name__+': '+str(e)
                                salidas.setdefault(x['id'],[]).append({'respuesta':texto,'ok':ok,'error':error})
                    for n,x in enumerate(grupo):
                        intentos=salidas.get(x['id'],[])
                        if lote==1:
                            registros=[]
                            for t,codigo in enumerate(intentos):
                                error=''
                                try:ok=comprobar(codigo,x,base/'primeras'/f'{c}_{x["id"]}_{t}')
                                except Exception as e:ok=False;error=type(e).__name__+': '+str(e)
                                registros.append({'respuesta':codigo,'ok':ok,'error':error})
                            intentos=registros
                        row={'contexto':c,'id':x['id'],'pedido':x['pedido'],'primer_ok':bool(intentos and intentos[0]['ok']),'final_ok':bool(intentos and intentos[-1]['ok']),'intentos':intentos,'llamadas':len(llamadas) if n==0 else 0,'lote':len(grupo),'corpus_sha256':sha}
                        if lote==1:row['respuesta_controlador']=respuesta
                        def sanear(d):
                            if isinstance(d,str):return _redactar(d)
                            if isinstance(d,list):return [sanear(x) for x in d]
                            if isinstance(d,dict):return {k:sanear(v) for k,v in d.items()}
                            return d
                        rows.append(row);audit.write(json.dumps(sanear(row),ensure_ascii=False)+'\n');audit.flush()
                    if len(rows)%10==0:guardar()
            guardar()
    return 0 if all(r['final_ok'] for r in rows) else 1
if __name__=='__main__':raise SystemExit(main())
