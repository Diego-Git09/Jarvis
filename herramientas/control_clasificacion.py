"""Clasificación explícita con comprobación atómica; no cambia el contenido."""
import sqlite3
from contextlib import closing


def consultar(base, ident):
    if type(ident) is not int or ident < 1:
        raise ValueError('Identificador inválido')
    with closing(sqlite3.connect(base / 'cerebro.db', timeout=30)) as db, db:
        db.row_factory = sqlite3.Row
        r = db.execute('SELECT * FROM memorias WHERE id=?', (ident,)).fetchone()
    return {'memorias': [dict(r)] if r else []}


def clasificar(base, ident, proyecto, contenido_esperado, proyecto_esperado):
    if type(ident) is not int or ident < 1:
        raise ValueError('Identificador inválido')
    if not isinstance(proyecto, str) or not proyecto.strip() or len(proyecto) > 100:
        raise ValueError('Proyecto vacío o demasiado largo')
    if not isinstance(contenido_esperado, str) or not isinstance(proyecto_esperado, str):
        raise ValueError('Consulta primero el recuerdo')
    proyecto = nombre_proyecto(proyecto)
    with closing(sqlite3.connect(base / 'cerebro.db', timeout=30)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        r = db.execute('SELECT contenido,proyecto FROM memorias WHERE id=?', (ident,)).fetchone()
        if not r:
            return {'ok': False, 'error': 'El recuerdo ya no existe.'}
        if r != (contenido_esperado, proyecto_esperado):
            return {'ok': False, 'error': 'El recuerdo cambió. Vuelve a consultarlo antes de clasificarlo.'}
        db.execute('CREATE TABLE IF NOT EXISTS proyectos_registrados(nombre TEXT PRIMARY KEY COLLATE NOCASE)')
        nombres = [row[0] for row in db.execute('SELECT nombre FROM proyectos_registrados UNION SELECT proyecto FROM memorias')]
        proyecto = next((n for n in nombres if n.casefold() == proyecto.casefold()), proyecto)
        db.execute('INSERT OR IGNORE INTO proyectos_registrados(nombre) VALUES(?)', (proyecto,))
        db.execute('UPDATE memorias SET proyecto=? WHERE id=?', (proyecto, ident))
    return {'estado': 'clasificada', 'id': ident, 'proyecto': proyecto,
            'nota': 'La búsqueda semántica se actualizará en el próximo ciclo automático.'}


def nombre_proyecto(nombre):
    if not isinstance(nombre, str) or not nombre.strip() or len(nombre.strip()) > 100 or any(ord(c) < 32 for c in nombre):
        raise ValueError('Nombre de proyecto inválido')
    return 'Jarvis' if nombre.strip().casefold() == 'jarvis' else nombre.strip()


def proyectos(base):
    with closing(sqlite3.connect(base / 'cerebro.db', timeout=30)) as db:
        rows = db.execute('SELECT proyecto,COUNT(*) FROM memorias GROUP BY proyecto').fetchall()
        registered = db.execute("SELECT nombre FROM proyectos_registrados").fetchall() if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proyectos_registrados'").fetchone() else []
    result = {name.casefold(): {'proyecto': name, 'total': 0} for (name,) in registered}
    for name, total in rows:
        item = result.setdefault(name.casefold(), {'proyecto': name, 'total': 0})
        item['total'] += total
    return {'proyectos': sorted(result.values(), key=lambda r: r['proyecto'].casefold())}


def crear_proyecto(base, nombre):
    nombre = nombre_proyecto(nombre)
    with closing(sqlite3.connect(base / 'cerebro.db', timeout=30)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS proyectos_registrados(nombre TEXT PRIMARY KEY COLLATE NOCASE)')
        existentes = [r[0] for r in db.execute('SELECT nombre FROM proyectos_registrados UNION SELECT proyecto FROM memorias')]
        actual = next((n for n in existentes if n.casefold() == nombre.casefold()), None)
        if actual is not None:
            return {'estado': 'ya_existe', 'proyecto': actual}
        db.execute('INSERT INTO proyectos_registrados(nombre) VALUES(?)', (nombre,))
    return {'estado': 'creado', 'proyecto': nombre}
