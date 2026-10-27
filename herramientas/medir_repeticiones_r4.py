"""Repite el banco original bajo aislamiento; no sobreescribe R5–R7."""
from pathlib import Path
import medir_seleccion_20261020 as M
from medir_ronda3_20261020 import preparar_espera

M.DESTINO=Path(__file__).resolve().parents[1]/'registros/reportes/ronda4_20261021'

if __name__=='__main__':
    preparar_espera();M.main()
