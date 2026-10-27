"""Comprobadores locales. SQL siempre usa SQLite en memoria, nunca una BD del usuario."""
import json
from pathlib import Path
import sqlite3
import sys
import time


def comprobar_sql(archivos, contratos=None):
    inicio = time.monotonic()
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA temp_store=MEMORY')
    db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,1_000_000)
    db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,100_000)
    db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN,1000)
    prohibidos = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}
    def autorizar(accion, a, b, _base, _origen):
        if accion in prohibidos or (accion == sqlite3.SQLITE_FUNCTION and (b or '').lower() in {'load_extension', 'writefile', 'readfile'}):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    db.set_authorizer(autorizar)
    db.set_progress_handler(lambda: int(time.monotonic() - inicio > 5), 1000)
    try:
        for archivo in archivos:
            db.executescript(Path(archivo).read_text(encoding='utf-8'))
        pruebas = 0
        if contratos:
            casos = json.loads(Path(contratos).read_text(encoding='utf-8'))
            if not isinstance(casos, list) or not 1 <= len(casos) <= 100:
                raise ValueError('El contrato SQL necesita entre 1 y 100 consultas con resultados esperados.')
            for caso in casos:
                if not isinstance(caso,dict) or set(caso) != {'consulta', 'esperado'} or not isinstance(caso['consulta'], str) or not isinstance(caso['esperado'],list):
                    raise ValueError('Cada contrato necesita consulta y esperado.')
                observado = [list(f) for f in db.execute(caso['consulta']).fetchmany(1001)]
                if observado != caso['esperado']:
                    raise AssertionError(f"Consulta: {caso['consulta']}\nEsperado: {caso['esperado']}\nObservado: {observado[:20]}")
                pruebas += 1
        return f'SQLite en memoria: {len(archivos)} archivo(s) ejecutado(s), {pruebas} contrato(s) comprobado(s). No verifica otros dialectos ni bases reales.'
    finally:
        db.close()


if __name__ == '__main__':
    try:
        print(comprobar_sql(json.loads(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None))
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
