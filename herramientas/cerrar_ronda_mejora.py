"""Cierre explícito de una ronda: batería completa, estado local y publicación opcional.

No se llama desde pruebas aisladas ni publica por el simple hecho de importar.
--publicar expresa autorización para actualizar únicamente el resumen fijo.
"""
import argparse
import subprocess
import sys
import time


def cerrar(publicar=False):
    from entorno_jarvis import PROYECTO,REGISTROS,en_pruebas
    if en_pruebas():raise ValueError('El cierre real no se ejecuta dentro de pruebas aisladas.')
    carpeta=REGISTROS/'reportes/rondas';carpeta.mkdir(parents=True,exist_ok=True)
    informe=carpeta/f'pruebas_control_{time.time_ns()}.txt'
    with informe.open('w') as salida:
        r=subprocess.run([sys.executable,'-u',str(PROYECTO/'herramientas/ejecutar_pruebas.py')],
                         cwd=PROYECTO,stdout=salida,stderr=subprocess.STDOUT)
    import estado_ia
    texto=estado_ia.generar()
    print('Batería completa:',informe)
    print('Estado local actualizado:',estado_ia.RESUMEN,f'({len(texto.split())} palabras)')
    if r.returncode:
        print('Hay fallos. El estado los refleja; no publiqué un cierre correcto.');return r.returncode
    if publicar:
        from cerebro_mcp import ClienteCerebro
        try:
            resultado=estado_ia.publicar(ClienteCerebro(timeout=15))
            print('Resumen fijo actualizado y leído después del cambio. ID:',resultado[0]['id'])
        except (OSError,ValueError) as e:
            print('No se confirmó la publicación. La cola conserva el intento:',str(e));return 1
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publicar',action='store_true',help='Autoriza actualizar el único resumen fijo de Jarvis en Segundo Cerebro después de la batería correcta.')
    args=p.parse_args();return cerrar(args.publicar)


if __name__=='__main__':raise SystemExit(main())
