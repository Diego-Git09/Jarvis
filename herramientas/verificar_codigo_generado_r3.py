"""Contratos locales de fragmentos ya revisados, sin servicios ni datos reales."""
import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

RAIZ=Path(__file__).resolve().parents[1]
DESTINO=RAIZ/'registros/reportes/ronda3_20261020'

def main():
    filas={r['id']:r for r in map(json.loads,(DESTINO/'seleccion_40_r8.jsonl').read_text().splitlines())}
    resultados=[]
    def guardar(n,lenguaje,codigo,detalle):
        resultados.append({'caso':n,'lenguaje':lenguaje,'sha256_fragmento':hashlib.sha256(codigo.encode()).hexdigest(),'ok':True,'detalle':detalle})
    for codigo in re.findall(r'```python\n(.*?)```',filas[25]['respuesta_original_jarvis'],re.S):
        arbol=ast.parse(codigo)
        assert len(arbol.body)==1 and isinstance(arbol.body[0],ast.FunctionDef)
        assert not any(isinstance(x,(ast.Import,ast.ImportFrom,ast.Attribute)) for x in ast.walk(arbol))
        env={'__builtins__':{'max':max}}
        exec(compile(arbol,'ejemplo_revisado','exec'),env)
        f=env['encontrar_maximo']
        for datos in ([1,7,2],[-7,-2,-3],[4]):assert f(datos)==max(datos)
        guardar(25,'Python',codigo,'Dos implementaciones comprobadas con listas sintéticas positivas, negativas y unitarias.')
    codigo=re.search(r'SELECT\s+.*?;',filas[26]['respuesta_original_jarvis'],re.S)[0]
    with sqlite3.connect(':memory:') as db:
        db.executescript('CREATE TABLE ventas(region TEXT,monto INTEGER); INSERT INTO ventas VALUES ("A",3),("A",5),("B",2);')
        assert sorted(db.execute(codigo).fetchall())==[('A',8),('B',2)]
    guardar(26,'SQL/SQLite',codigo,'Agrupa y suma los importes esperados; base efímera, sin Oracle.')
    codigo=re.search(r'```java\n(.*?)```',filas[27]['respuesta_original_jarvis'],re.S)[1]
    with tempfile.TemporaryDirectory(prefix='jarvis-java-r3-') as d:
        p=Path(d);(p/'Persona.java').write_text(codigo)
        (p/'Contrato.java').write_text('class Contrato { public static void main(String[] args) { Persona p=new Persona("A"); if(!p.getNombre().equals("A"))throw new AssertionError(); p.setNombre("B");if(!p.getNombre().equals("B"))throw new AssertionError();System.out.print("OK"); }}')
        c=subprocess.run(['javac','-proc:none','-d',d,str(p/'Persona.java'),str(p/'Contrato.java')],capture_output=True,text=True,timeout=30)
        assert c.returncode==0,c.stderr
        r=subprocess.run(['java','-cp',d,'Contrato'],capture_output=True,text=True,timeout=10)
        assert r.returncode==0 and r.stdout=='OK',r.stderr
    guardar(27,'Java',codigo,'Compilación real; constructor, lectura y cambio de nombre comprobados.')
    codigo=filas[28]['respuesta_original_jarvis'].split('\n\n',1)[1]
    librerias=list((Path.home()/'.gradle/wrapper/dists').glob('gradle-*/**/lib/kotlin-compiler-embeddable-*.jar'))
    assert librerias,'No hay compilador Kotlin local; no se descarga.'
    lib=librerias[0].parent
    stdlib=next(lib.glob('kotlin-stdlib-[0-9]*.jar'))
    with tempfile.TemporaryDirectory(prefix='jarvis-kotlin-r3-') as d:
        p=Path(d);src=p/'Contrato.kt';src.write_text(codigo+'\nfun main() { check(suma(3,5)==8); check(suma(-2,5)==3); print("OK") }\n')
        out=p/'out';out.mkdir()
        c=subprocess.run(['java','-cp',':'.join(map(str,lib.glob('*.jar'))),'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-classpath',str(stdlib),'-d',str(out),str(src)],capture_output=True,text=True,timeout=45)
        assert c.returncode==0,c.stderr
        r=subprocess.run(['java','-cp',str(out)+':'+str(stdlib),'ContratoKt'],capture_output=True,text=True,timeout=10)
        assert r.returncode==0 and r.stdout=='OK',r.stderr
    guardar(28,'Kotlin/JVM',codigo,'Compilador embebido ya instalado en Gradle; suma positiva y con negativo. No acredita Android/Room.')
    codigo=re.search(r'```python\n(.*?)```',filas[34]['respuesta_original_jarvis'],re.S)[1]
    arbol=ast.parse(codigo)
    assert all(isinstance(x,ast.For) for x in arbol.body)
    salida=io.StringIO()
    with contextlib.redirect_stdout(salida):exec(compile(arbol,'bucle_revisado','exec'),{'__builtins__':{'range':range,'print':print}})
    assert salida.getvalue()=='0\n1\n2\n'
    guardar(34,'Python',codigo,'Bucle corregido compila y produce 0, 1, 2; prueba posterior separada de la generación sin herramientas.')
    informe={'alcance':'Verificación posterior de ejemplos sintéticos revisados. No se ejecutó ningún programa de usuario ni se usaron servicios o bases reales.','fuente':'seleccion_40_r8.jsonl','casos':resultados}
    (DESTINO/'contratos_generados_r8.json').write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'fragmentos':len(resultados),'correctos':sum(x['ok'] for x in resultados)},ensure_ascii=False))

if __name__=='__main__':main()
