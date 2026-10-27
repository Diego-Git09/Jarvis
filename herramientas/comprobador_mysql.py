"""MySQL temporal con usuario limitado; no conecta ni modifica bases existentes."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import time

def comprobar(archivos,contratos=None):
    servidor=shutil.which('mysqld');cliente=shutil.which('mysql')
    if not servidor or not cliente:raise ValueError('Falta el servidor/cliente MySQL; no se comprobó el dialecto.')
    fuentes=[]
    for nombre in archivos:
        p=Path(nombre)
        if p.is_symlink() or p.stat().st_size>100000:raise ValueError('SQL demasiado grande o enlazado.')
        t=p.read_text()
        if re.search(r'(?i)\b(?:OUTFILE|DUMPFILE|LOAD_FILE|INSTALL\s+PLUGIN|LOAD\s+DATA|CREATE\s+FUNCTION|mysql\s*\.)',t):raise ValueError('SQL con acceso a archivos/administración; no se ejecutó.')
        fuentes.append(t)
    with tempfile.TemporaryDirectory(prefix='jarvis-mysql-') as tmp:
        base=Path(tmp);datos=base/'data';datos.mkdir();socket=str(base/'mysql.sock');log=str(base/'mysql.log')
        init=subprocess.run([servidor,'--no-defaults','--initialize-insecure','--datadir='+str(datos),'--log-error='+log],capture_output=True,timeout=45)
        if init.returncode:raise ValueError('No se pudo inicializar MySQL temporal (sin tocar el servicio existente).')
        proceso=subprocess.Popen([servidor,'--no-defaults','--datadir='+str(datos),'--socket='+socket,'--skip-networking','--mysqlx=0','--pid-file='+str(base/'mysql.pid'),'--log-error='+log,'--innodb-buffer-pool-size=64M'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        def sql(texto,usuario='jarvis_eval',database=True):
            cmd=[cliente,'--no-defaults','--protocol=SOCKET','--socket='+socket,'--user='+usuario,'--batch','--raw','--skip-column-names','--connect-timeout=3']
            if database:cmd+=['--database=jarvis_prueba']
            r=subprocess.run(cmd,input=texto,capture_output=True,text=True,timeout=12)
            if r.returncode:raise ValueError('Consulta MySQL rechazada: '+r.stderr[-900:])
            return r.stdout
        try:
            fin=time.monotonic()+20
            while not Path(socket).exists():
                if proceso.poll() is not None or time.monotonic()>fin:raise ValueError('MySQL temporal no llegó a estar disponible.')
                time.sleep(.1)
            sql("CREATE DATABASE jarvis_prueba; CREATE USER 'jarvis_eval'@'localhost'; GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,DROP,ALTER,INDEX,CREATE VIEW,SHOW VIEW ON jarvis_prueba.* TO 'jarvis_eval'@'localhost';",'root',False)
            sql('\n'.join(fuentes));numero=0
            if contratos:
                reglas=json.loads(Path(contratos).read_text())
                if not isinstance(reglas,list) or len(reglas)>100:raise ValueError('Contratos MySQL inválidos.')
                for regla in reglas:
                    salida=sql(regla['consulta']);filas=[]
                    for linea in salida.splitlines():
                        filas.append([None if x=='NULL' else int(x) if re.fullmatch(r'-?\d+',x) else float(x) if re.fullmatch(r'-?\d+\.\d+',x) else x for x in linea.split('\t')])
                    if filas!=regla['esperado']:raise AssertionError(f'Contrato MySQL: esperado {regla["esperado"]}, observado {filas}')
                    numero+=1
            return f'MySQL temporal: {len(archivos)} archivo(s), {numero} contratos funcionales. Sin bases existentes ni privilegio FILE.'
        finally:
            proceso.terminate()
            try:proceso.wait(timeout=8)
            except subprocess.TimeoutExpired:proceso.kill();proceso.wait(timeout=3)

if __name__=='__main__':
    import sys
    try:print(comprobar(json.loads(sys.argv[1]),sys.argv[2] if len(sys.argv)>2 else None))
    except Exception as e:print(type(e).__name__+': '+str(e),file=sys.stderr);raise SystemExit(1)
