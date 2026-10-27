"""Java CLI y APK Android mínimos, con datos ficticios y directorios de prueba privados."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

def main():
    informe={};dest=Path('/home/usuario/Jarvis/registros/reportes/ampliacion_20261014/proyectos_reales.json')
    with tempfile.TemporaryDirectory(prefix='jarvis-proyectos-reales-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1');base=Path(tmp);(base/'trabajo').mkdir()
        home_gradle=base/'gradle-home';home_gradle.mkdir()
        for nombre in ['.android','java-home']:(base/nombre).mkdir()
        os.environ.update(GRADLE_USER_HOME=str(home_gradle),ANDROID_USER_HOME=str(base/'.android'),ANDROID_PREFS_ROOT=str(base),JAVA_TOOL_OPTIONS='-Duser.home='+str(base/'java-home'))
        import proyectos_codigo as P
        import cliente_ollama as O
        def crear(nombre,objetivo,archivo):
            raiz=base/'trabajo'/nombre
            assert P.ejecutar('iniciar_proyecto_codigo',{'nombre':nombre,'ruta':str(raiz),'objetivo':objetivo},lambda _:True,{})['ok']
            assert P.ejecutar('actualizar_plan_codigo',{'etapas_json':json.dumps([{'titulo':'Programa funcional','archivos':[archivo]}])},lambda _:True,{})['ok']
            return raiz
        raiz=crear('JavaConsola','CLI Java con entrada numérica y salida comprobada','Main.java')
        t0=time.monotonic()
        try:
            texto=P.desarrollar('Genera Main.java, public class Main con main(String[] args). Lee args[0] como entero y muestra exactamente el doble. Sin paquetes, dependencias externas, red, archivos, procesos ni reflexión.',{},lambda _:True,O.solicitar,'qwen3:8b')
            codigo=(raiz/'Main.java').read_text()
            if re.search(r'Runtime|ProcessBuilder|java\.(?:io|nio|net)|reflect|getenv|getProperty',codigo):raise ValueError('Código fuera del programa CLI pedido')
            clases=base/'clases';clases.mkdir();r=subprocess.run(['javac','-proc:none','-d',str(clases),str(raiz/'Main.java')],capture_output=True,text=True,timeout=30)
            if r.returncode:raise ValueError(r.stderr[-1200:])
            salidas=[]
            for x in [0,3,-2,100]:
                r=subprocess.run(['java','-cp',str(clases),'Main',str(x)],capture_output=True,text=True,timeout=5)
                assert r.returncode==0 and r.stdout.strip()==str(x*2),(x,r.stdout);salidas.append({'entrada':x,'salida':r.stdout.strip()})
            informe['java']={'ok':True,'escrito':True,'compilado':True,'funcional':True,'contratos':salidas,'respuesta_controlador':texto,'segundos':round(time.monotonic()-t0,2)}
        except Exception as e:informe['java']={'ok':False,'error':type(e).__name__+': '+str(e)}
        dest.write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n')
        plantilla=Path('/home/usuario/AndroidStudioProjects/ProyectoEjemplo');originales={}
        t0=time.monotonic()
        try:
            if not plantilla.is_dir():raise ValueError('Plantilla local no disponible')
            archivo='app/src/main/java/com/jarvis/prueba/MainActivity.java';raiz=crear('AndroidMinimo','Pantalla Android mínima con contador de entradas ficticias',archivo)
            # Solo metadatos de versiones y wrapper; ninguna fuente/dato real se usa en la aplicación.
            for nombre in ['build.gradle.kts','settings.gradle.kts','gradle.properties','gradlew','gradle/libs.versions.toml','gradle/wrapper/gradle-wrapper.jar','gradle/wrapper/gradle-wrapper.properties','app/build.gradle.kts']:
                p=plantilla/nombre;originales[nombre]=hashlib.sha256(p.read_bytes()).hexdigest();f=raiz/nombre;f.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,f)
            gradle=(raiz/'app/build.gradle.kts').read_text().replace('com.duoc.retailcount','com.jarvis.prueba');(raiz/'app/build.gradle.kts').write_text(gradle)
            sdk=Path('/home/usuario/Android/Sdk')
            if not sdk.is_dir():raise ValueError('SDK local no disponible')
            (raiz/'local.properties').write_text('sdk.dir='+str(sdk)+'\n')
            manifiesto=raiz/'app/src/main/AndroidManifest.xml';manifiesto.parent.mkdir(parents=True,exist_ok=True)
            manifiesto.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="Jarvis prueba ficticia" android:theme="@android:style/Theme.Material.NoActionBar"><activity android:name=".MainActivity" android:exported="true"><intent-filter><action android:name="android.intent.action.MAIN"/><category android:name="android.intent.category.LAUNCHER"/></intent-filter></activity></application></manifest>')
            for nombre in ['caches','wrapper']:
                fuente=Path('/home/usuario/.gradle')/nombre
                if fuente.is_dir():shutil.copytree(fuente,home_gradle/nombre,ignore=shutil.ignore_patterns('*.lock','daemon','*.lck'),symlinks=False)
            # Gradle, preferencias Android y clave de firma de prueba quedan dentro del temporal.
            env=dict(os.environ)
            def enviar(ruta,payload,**kw):return O.solicitar(ruta,payload,**kw)
            texto=P.desarrollar('Genera '+archivo+'. Paquete com.jarvis.prueba, public class MainActivity extends android.app.Activity. Pantalla con TextView y Button en LinearLayout vertical. Empieza en 0; cada clic suma 1 y muestra Entradas: N. Usa solo clases android.app, android.os, android.widget y android.view; no recursos, red, datos reales, procesos ni reflexión. No compiles todavía; la compilación se comprobará aislada.',{},lambda _:True,enviar,'qwen3:8b')
            p=raiz/archivo
            if not p.is_file():raise ValueError(texto or 'No generó Activity')
            codigo=p.read_text()
            if re.search(r'Runtime|ProcessBuilder|java\.(?:io|nio|net)|reflect|getenv|getProperty',codigo):raise ValueError('Operaciones fuera de la pantalla pedida')
            r=subprocess.run(['/bin/sh',str(raiz/'gradlew'),'--offline','--no-daemon','--console=plain','--stacktrace','-Dorg.gradle.jvmargs=-Xmx1536m','-Dorg.gradle.workers.max=2',':app:assembleDebug'],cwd=raiz,env=env,capture_output=True,text=True,timeout=240)
            (dest.parent/'android_build.txt').write_text(r.stdout+'\n'+r.stderr)
            primer_ok=r.returncode==0;correcciones=0
            for intento in range(2):
                if not r.returncode:break
                (dest.parent/f'android_build_fallo_{intento}.txt').write_text(r.stdout+'\n'+r.stderr)
                errores='\n'.join(line for line in (r.stdout+'\n'+r.stderr).splitlines() if 'error:' in line or 'symbol:' in line or 'location:' in line)
                if not errores:break
                P.ejecutar('registrar_error_codigo',{'error':errores},lambda _:True,{})
                texto=P.desarrollar('Corrige '+archivo+' conservando la pantalla y el contador. NO hay layouts XML ni IDs R: construye TextView, Button y LinearLayout con new; setContentView(linearLayout). El contador empieza en 0 y cada clic suma 1. Paquete com.jarvis.prueba; Activity del SDK. Error del compilador: '+errores+'. No compiles todavía.',{},lambda _:True,enviar,'qwen3:8b')
                codigo=p.read_text()
                if re.search(r'Runtime|ProcessBuilder|java\.(?:io|nio|net)|reflect|getenv|getProperty',codigo):raise ValueError('Corrección fuera del programa pedido')
                r=subprocess.run(['/bin/sh',str(raiz/'gradlew'),'--offline','--no-daemon','--console=plain','-Dorg.gradle.jvmargs=-Xmx1536m','-Dorg.gradle.workers.max=2',':app:assembleDebug'],cwd=raiz,env=env,capture_output=True,text=True,timeout=240)
                correcciones+=1;(dest.parent/'android_build.txt').write_text(r.stdout+'\n'+r.stderr)
            apk=raiz/'app/build/outputs/apk/debug/app-debug.apk'
            if r.returncode or not apk.is_file():raise ValueError('Compilación Android no terminó; ver android_build.txt')
            with zipfile.ZipFile(apk) as z:
                assert 'AndroidManifest.xml' in z.namelist() and any(n.endswith('.dex') for n in z.namelist())
                actividad=any(b'Lcom/jarvis/prueba/MainActivity;' in z.read(n) for n in z.namelist() if n.endswith('.dex'))
                assert actividad
            assert all(hashlib.sha256((plantilla/n).read_bytes()).hexdigest()==h for n,h in originales.items())
            informe['android']={'ok':True,'primer_ok':primer_ok,'correcciones':correcciones,'escrito':True,'compilado':True,'apk_verificado':True,'activity_en_dex':True,'sha256_apk':hashlib.sha256(apk.read_bytes()).hexdigest(),'originales_sin_cambios':True,'instalado':False,'pantalla_en_dispositivo_probada':False,'segundos':round(time.monotonic()-t0,2)}
        except Exception as e:informe['android']={'ok':False,'error':type(e).__name__+': '+str(e),'originales_sin_cambios':all(hashlib.sha256((plantilla/n).read_bytes()).hexdigest()==h for n,h in originales.items())}
        dest.write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n');print(informe)
if __name__=='__main__':main()
