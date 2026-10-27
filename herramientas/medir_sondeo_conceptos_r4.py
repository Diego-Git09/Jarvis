"""Sondeo local pequeño: dos casos repetidos y ocho formulaciones nuevas.

No acredita generalización ni sustituye el banco original de60 peticiones.
Reutiliza exactamente su aislamiento y sus comprobaciones de recursos.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import medir_banco_r4 as M

CASOS=[
 ('repetido_incremental','quieroque me expliques que es una copia de seguridad incremental',r'incremental'),
 ('nueva_incremental','podrias explicarme una copia incremental y una diferencial con su diferencia principal',r'incremental.*diferencial|diferencial.*incremental'),
 ('nueva_incremental','explica que necesito para restaurar una copia incremental solo explica no ejecutes nada',r'completa|base'),
 ('nueva_incremental','necesito que me expliques una copia incremental despues de otra incremental',r'anterior|ultima|última'),
 ('nueva_incremental','quiero que me expliques una copia incremental si cambie dos veces el mismo archivo solo texto',r'cambio|modific'),
 ('repetido_unidades','que diferencia hay entre megabytes y megabits',r'8|ocho'),
 ('nueva_unidades','podrias explicarme si un megabit por si solo es una velocidad',r'cantidad|segundo|velocidad'),
 ('nueva_unidades','quiero que me expliques cuantos megabits son dos megabytes',r'16|dieciseis|dieciséis'),
 ('nueva_unidades','explicame como paso de 3 megabytes a megabits con la cuenta',r'24|veinticuatro'),
 ('nueva_unidades','explicame la diferencia entre un megabit y un megabit por segundo',r'cantidad|velocidad'),
]

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--ronda',default='sondeo_conceptos');args=ap.parse_args()
    casos=[{'id':n,'categoria':c,'pregunta':p,'ancla':a} for n,(c,p,a) in enumerate(CASOS,1)]
    def congelar(destino):
        destino.mkdir(parents=True,exist_ok=True)
        p=destino/'corpus_sondeo_conceptos.json'
        texto=json.dumps({'tipo':'Dos casos vistos y ocho formulaciones nuevas; revisión de Codex, no del usuario.','casos':casos},ensure_ascii=False,indent=2)+'\n'
        if p.exists() and p.read_text()!=texto:raise ValueError('No sobrescribir corpus anterior')
        if not p.exists():p.write_text(texto);p.chmod(0o600)
        return hashlib.sha256(texto.encode()).hexdigest()
    M.DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda4_continuacion_20261021'
    M.congelar=congelar;M.sesenta=lambda:casos
    sys.argv=[sys.argv[0],'--tipo','sesenta','--ronda',args.ronda]
    M.main()

if __name__=='__main__':main()
