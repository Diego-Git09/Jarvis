"""Sondeo separado, no se suma a las cuarenta peticiones."""
from pathlib import Path
import medir_seleccion_20261020 as M
M.DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda3_20261020/piloto_adicional'
M.CASOS=[M.CASOS[33],M.CASOS[37],
 ('explica que es RAM y luego explica que es CPU','media',r'1[.)].*|RAM'),
 ('usuario@equipo:~$ nvidia-smi\nNVIDIA-SMI\nMemoria GPU: 4096 MiB de 8192 MiB. Temperatura: 60 C.','media',r'4096|mitad|50')]
if __name__=='__main__':
    from medir_ronda3_20261020 import preparar_espera
    M.DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda3_20261020/piloto_adicional'
    preparar_espera();M.main()
