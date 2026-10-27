"""Secuencia reanudable: no solapa modelos ni sobrescribe mediciones."""
import hashlib, json, subprocess, sys
from pathlib import Path

RAIZ=Path(__file__).resolve().parents[1]
DESTINO=RAIZ/'registros/reportes/ronda4_20261021'
PLAN=[('r6_corregida',40,['medir_repeticiones_r4.py','--ronda','r6_corregida','--esperar-recursos']),
      ('r7_corregida',40,['medir_repeticiones_r4.py','--ronda','r7_corregida','--esperar-recursos']),
      ('sesenta_inicial',60,['medir_banco_r4.py','--tipo','sesenta','--ronda','inicial']),
      ('continuidad_inicial',150,['medir_banco_r4.py','--tipo','continuidad','--ronda','inicial'])]

def main():
    for nombre,total,args in PLAN:
        destino=DESTINO/(nombre+'.jsonl')
        if destino.exists():
            filas=list(map(json.loads,destino.read_text().splitlines()))
            if len(filas)!=total:raise RuntimeError('Medición parcial conservada: revisar '+nombre+' antes de repetir con otro nombre')
            print(nombre+': ya completa; no se repite',flush=True);continue
        manifiesto={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (RAIZ/'herramientas').glob('*.py')}
        f=DESTINO/(nombre+'_fuentes.json');f.write_text(json.dumps(manifiesto,indent=2)+'\n');f.chmod(0o600)
        log=DESTINO/(nombre+'_progreso.txt')
        if log.exists():raise RuntimeError('No sobrescribir log previo')
        print('Iniciando '+nombre,flush=True)
        with log.open('x') as salida:
            log.chmod(0o600)
            r=subprocess.run([sys.executable,'-u','-B',str(RAIZ/'herramientas'/args[0]),*args[1:]],stdout=salida,stderr=subprocess.STDOUT,cwd=RAIZ,timeout=7200)
        if r.returncode:raise RuntimeError('La medición terminó con error: '+nombre)
        filas=list(map(json.loads,destino.read_text().splitlines()))
        if len(filas)!=total:raise RuntimeError('Conteo incompleto: '+nombre)
        print(nombre+': '+str(total)+' respuestas conservadas',flush=True)

if __name__=='__main__':main()
