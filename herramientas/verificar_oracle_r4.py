"""Solo contenedor efímero propio, sin red, puertos ni volúmenes del usuario."""
import argparse,json,os,secrets,subprocess,time,uuid
from pathlib import Path

DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda4_20261021/oracle_real.json'
def ejecutar(*args,entrada=None,timeout=20,env=None):
    return subprocess.run(args,input=entrada,text=True,capture_output=True,timeout=timeout,env=env)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ronda',default='2',choices=['2']);a=ap.parse_args()
    destino=DESTINO.with_name('oracle_real_'+a.ronda+'.json')
    if destino.exists():raise ValueError('No sobrescribir un intento anterior')
    nombre='jarvis-r4-prueba-'+uuid.uuid4().hex[:10];creado=False
    resultado={'real':True,'red':'ninguna','puertos_publicados':False,'limite_ram_gib':5,'estado':'no verificado'}
    try:
        memoria={l.split(':')[0]:int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith(('MemTotal:','MemAvailable:'))}
        if memoria['MemTotal']-memoria['MemAvailable']+5*1024**3>memoria['MemTotal']*.8:raise RuntimeError('La reserva superaría el 80 % de RAM; no se crea el contenedor')
        imagen='container-registry.oracle.com/database/enterprise:19.3.0.0'
        e=dict(os.environ,ORACLE_PWD='Prueba'+secrets.token_hex(10))
        r=ejecutar('docker','run','--detach','--name',nombre,'--network','none','--memory','5g','--cpus','1','--shm-size','1g','-e','ORACLE_PWD','-e','ORACLE_SID=ORCLCDB','-e','ORACLE_PDB=ORCLPDB1',imagen,env=e)
        if r.returncode:raise RuntimeError('Docker no pudo iniciar el contenedor de prueba; no se guardó su salida de entorno')
        creado=True;inicio=time.monotonic();fin=inicio+900
        while time.monotonic()<fin:
            estado=ejecutar('docker','inspect','--format','{{.State.Running}} {{.State.ExitCode}}',nombre)
            if estado.returncode or not estado.stdout.startswith('true'):raise RuntimeError('El contenedor de prueba terminó antes de aceptar SQL; estado '+estado.stdout.strip())
            r=ejecutar('docker','exec',nombre,'bash','-c','printf "set heading off feedback off pagesize 0\nselect 241+1 from dual;\nexit;\n" | "$ORACLE_HOME/bin/sqlplus" -s "/ as sysdba"',timeout=30)
            if r.returncode==0 and '242' in r.stdout.split():
                resultado.update(estado='verificado',sql='SELECT 241+1 FROM dual;',resultado=242,segundos=round(time.monotonic()-inicio,2))
                break
            time.sleep(10)
        else:resultado['motivo']='La base efímera no quedó lista en 900 s; no se afirma conexión'
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:resultado['motivo']=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
    finally:
        if creado:
            if resultado['estado']!='verificado':
                logs=ejecutar('docker','logs','--tail','35',nombre)
                from conversaciones_jarvis import _redactar
                resultado['registro_saneado']=_redactar((logs.stdout+logs.stderr).replace(e['ORACLE_PWD'],'[CREDENCIAL TEMPORAL REDACTADA]'))[-8000:]
            r=ejecutar('docker','rm','--force','--volumes',nombre,timeout=30)
            comprobacion=ejecutar('docker','container','inspect',nombre)
            resultado['contenedor_retirado']=comprobacion.returncode!=0
        destino.write_text(json.dumps(resultado,ensure_ascii=False,indent=2)+'\n');destino.chmod(0o600)
        print(json.dumps({k:v for k,v in resultado.items() if k!='registro_saneado'},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
