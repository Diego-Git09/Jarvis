"""Archiva únicamente bloques completos de las pruebas que contaminaron la memoria.

No decide por el título ni por una palabra del usuario: exige los 68 turnos de
las cuatro pruebas de consola, con multiplicidades exactas, en menos de 20 s.
Las filas se conservan en una tabla de archivo y en una copia privada de SQLite.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3

COMANDOS_UNICOS = [
    '/anotar Comprar café','/anotar Comprar leche','/anotar Revisar informe','/archivos',
    '/ayuda archivos','/calcular 15% de 200','/cambios','/comparar tareas.md respaldo.md',
    '/config','/contexto','/continuar almuerzo','/copiar notas.txt copia.txt','/deshacer',
    '/duplicar tareas.md respaldo.md','/editar_tarea 1 Revisar informe completo',
    '/encontrar "*.md"','/exportar_tareas tareas.md','/guardar almuerzo','/guardar completa',
    '/hecho 1','/hecho uno y dos','/info tareas.md','/leer notas.txt','/modo breve',
    '/mover copia.txt final.txt','/nuevo','/prioridad 2 alta','/reabrir 1',
    '/reemplazar notas.txt "Comprar pan" "Comprar leche"','/sesiones','/timeout 30','/ultima_accion',
]
PATRON = Counter(COMANDOS_UNICOS)
PATRON.update({'/hora':30,'/tareas':4,'/tareas todas':2})


def pregunta(fila):
    texto=fila.get('contenido','')
    m=re.search(r'Usuario:\n(.*?)\n\nRespuesta',texto,re.S)
    return m[1].strip() if m else ''


def identificar_bloques(filas):
    candidatos=[];grupos=[];actual=[];anterior=None
    for fila in filas:
        fecha=datetime.fromisoformat(fila['creado'].replace('Z','+00:00'))
        if anterior is not None and (fecha-anterior).total_seconds()>15:
            grupos.append(actual);actual=[]
        actual.append(fila);anterior=fecha
    if actual:grupos.append(actual)
    for grupo in grupos:
        inicio=datetime.fromisoformat(grupo[0]['creado'].replace('Z','+00:00'))
        fin=datetime.fromisoformat(grupo[-1]['creado'].replace('Z','+00:00'))
        if (fin-inicio).total_seconds()<=20 and Counter(pregunta(r) for r in grupo)==PATRON:
            candidatos.append(grupo)
    return candidatos


def revisar(base):
    with sqlite3.connect((base/'cerebro.db').resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        filas=[dict(r) for r in db.execute("SELECT * FROM memorias WHERE tipo='conversacion' AND lower(fuente)='jarvis' ORDER BY julianday(creado),id")]
    bloques=identificar_bloques(filas)
    ids={r['id'] for g in bloques for r in g}
    return {'bloques':len(bloques),'pruebas':len(ids),'ids':sorted(ids),
            'chat_reales':[r for r in filas if r['id'] not in ids]}


def aplicar(base,reporte):
    previo=revisar(base)
    fecha=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    reporte.parent.mkdir(parents=True,exist_ok=True)
    backup=reporte.parent/f'cerebro_antes_archivo_{fecha}.sqlite'
    with sqlite3.connect(base/'cerebro.db',timeout=30) as db:
        with sqlite3.connect(backup) as copia:db.backup(copia)
        os.chmod(backup,0o600)
        db.row_factory=sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        filas=[dict(r) for r in db.execute("SELECT * FROM memorias WHERE tipo='conversacion' AND lower(fuente)='jarvis' ORDER BY julianday(creado),id")]
        ids={r['id'] for g in identificar_bloques(filas) for r in g}
        if ids!=set(previo['ids']):raise RuntimeError('La captura cambió durante la revisión; vuelve a ejecutar la revisión.')
        db.execute('CREATE TABLE IF NOT EXISTS archivo_pruebas_jarvis (id INTEGER PRIMARY KEY,fila_json TEXT NOT NULL,motivo TEXT NOT NULL,archivado TEXT NOT NULL)')
        for fila in filas:
            if fila['id'] not in ids:continue
            db.execute('INSERT INTO archivo_pruebas_jarvis VALUES (?,?,?,?)',
                       (fila['id'],json.dumps(fila,ensure_ascii=False),'Bloque completo de 68 turnos sintéticos de prueba_programa_completo.py',fecha))
            db.execute('DELETE FROM memorias WHERE id=? AND contenido=?',(fila['id'],fila['contenido']))
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='monitor_fuentes'").fetchone():
            db.execute("UPDATE monitor_fuentes SET mensajes=(SELECT COUNT(*) FROM memorias WHERE tipo='conversacion' AND lower(fuente)='jarvis'),pendientes=0 WHERE fuente='jarvis'")
        db.commit()
    resumen={'fecha':fecha,'bloques':previo['bloques'],'archivadas':len(ids),'ids':sorted(ids),'backup':str(backup),
             'tabla_archivo':'archivo_pruebas_jarvis','nota':'No se borró el contenido; se retiró de la memoria activa y sigue recuperable.'}
    reporte.write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.chmod(reporte,0o600)
    return resumen


def restaurar(base):
    with sqlite3.connect(base/'cerebro.db',timeout=30) as db:
        db.execute('BEGIN IMMEDIATE')
        filas=db.execute('SELECT id,fila_json FROM archivo_pruebas_jarvis').fetchall()
        for ident,texto in filas:
            dato=json.loads(texto)
            if db.execute('SELECT 1 FROM memorias WHERE id=?',(ident,)).fetchone():
                raise RuntimeError(f'El ID {ident} ya está ocupado; restaura desde el backup en una copia separada.')
            columnas=list(dato)
            db.execute('INSERT INTO memorias ('+','.join(columnas)+') VALUES ('+','.join('?' for _ in columnas)+')',list(dato.values()))
        db.execute('DELETE FROM archivo_pruebas_jarvis');db.commit()
    return {'restauradas':len(filas)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=Path.home()/'SegundoCerebro')
    p.add_argument('--aplicar',action='store_true');p.add_argument('--restaurar',action='store_true')
    p.add_argument('--reporte',type=Path,default=Path.home()/'Jarvis/registros/reportes/reparacion_captura_2026-10-12.json')
    a=p.parse_args()
    if a.aplicar and a.restaurar:p.error('Elige aplicar o restaurar, no ambas.')
    r=restaurar(a.base) if a.restaurar else aplicar(a.base,a.reporte) if a.aplicar else revisar(a.base)
    r.pop('chat_reales',None)
    print(json.dumps(r,ensure_ascii=False))


if __name__=='__main__':main()
