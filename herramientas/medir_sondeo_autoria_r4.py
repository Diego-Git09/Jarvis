"""Dos diálogos sintéticos nuevos para comprobar quién hizo una petición."""
import argparse,hashlib,json,sys
from pathlib import Path
import medir_banco_r4 as M

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--ronda',default='sondeo_autoria');args=ap.parse_args()
    grupos=[]
    for n,(a,b,op,resultado) in enumerate(((48,18,'diferencia',30),(12,5,'producto',60)),1):
        textos=[(f'Hablemos de un ejemplo ficticio de cuentas. El lunes hay {a} cajas y el martes {b}. Dime la suma, sin ejecutar nada.',str(a+b)),
                (f'Corrijo mi pedido: ahora quiero la {op} de {a} y {b}, solo explica.',str(resultado)),
                ('que operacion te pedi despues de corregirte',op)]
        grupos.append({'id':n,'turnos':[{'turno':i,'pregunta':p,'ancla':ancla,'categoria':'autoria'} for i,(p,ancla) in enumerate(textos,1)]})
    def congelar(destino):
        destino.mkdir(parents=True,exist_ok=True)
        p=destino/'corpus_sondeo_autoria.json';texto=json.dumps(grupos,ensure_ascii=False,indent=2)+'\n'
        if p.exists() and p.read_text()!=texto:raise ValueError('No sobrescribir corpus')
        if not p.exists():p.write_text(texto);p.chmod(0o600)
        return hashlib.sha256(texto.encode()).hexdigest()
    M.DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda4_continuacion_20261021'
    M.congelar=congelar;M.conversaciones=lambda:grupos
    sys.argv=[sys.argv[0],'--tipo','continuidad','--ronda',args.ronda]
    M.main()

if __name__=='__main__':main()
