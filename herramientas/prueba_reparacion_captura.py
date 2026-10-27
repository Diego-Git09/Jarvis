"""La reparación solo archiva bloques sintéticos completos y se puede deshacer."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from reparar_captura_historica import PATRON,identificar_bloques,aplicar,restaurar


def bloque(inicio=1):
    fecha=datetime(2026,10,12,tzinfo=timezone.utc)
    filas=[]
    for indice,p in enumerate(PATRON.elements()):
        filas.append({'id':inicio+indice,'tipo':'conversacion','fuente':'Jarvis','proyecto':'sin_clasificar',
            'titulo':'Ejemplo sintético','creado':(fecha+timedelta(milliseconds=indice*100)).isoformat(),
            'contenido':'Usuario:\n'+p+'\n\nRespuesta final de Jarvis:\nResultado ficticio.'})
    return filas


class Pruebas(unittest.TestCase):
    def test_reconoce_solo_68_turnos_exactos(self):
        self.assertEqual(len(identificar_bloques(bloque())),1)
        self.assertEqual(identificar_bloques(bloque()[:-1]),[])

    def test_uso_humano_del_mismo_comando_no_es_una_prueba(self):
        filas=bloque()
        filas[0]['contenido']='Usuario:\nhola\n\nRespuesta final de Jarvis:\nHola.'
        self.assertEqual(identificar_bloques(filas),[])

    def test_archiva_y_restaura_sin_perder_chat_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);filas=bloque()
            real=dict(filas[0],id=100,creado='2026-10-12T01:00:00+00:00',contenido='Usuario:\nhola\n\nRespuesta final de Jarvis:\nHola.')
            with sqlite3.connect(base/'cerebro.db') as db:
                db.execute('CREATE TABLE memorias(id INTEGER PRIMARY KEY,tipo TEXT,fuente TEXT,proyecto TEXT,titulo TEXT,creado TEXT,contenido TEXT)')
                for fila in filas+[real]:db.execute('INSERT INTO memorias VALUES (?,?,?,?,?,?,?)',list(fila.values()))
            r=aplicar(base,base/'reporte.json')
            self.assertEqual(r['archivadas'],68)
            with sqlite3.connect(base/'cerebro.db') as db:
                self.assertEqual(db.execute('SELECT id FROM memorias').fetchall(),[(100,)])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM archivo_pruebas_jarvis').fetchone()[0],68)
            self.assertTrue(Path(r['backup']).is_file())
            self.assertEqual(restaurar(base)['restauradas'],68)
            with sqlite3.connect(base/'cerebro.db') as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM memorias').fetchone()[0],69)


if __name__=='__main__':unittest.main()
