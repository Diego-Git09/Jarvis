"""Pruebas aisladas de persistencia, privacidad y reintento de transcripciones de Jarvis."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sqlite3
import sys
import json

import conversaciones_jarvis as capturas
sys.path.insert(0, str(Path.home() / 'SegundoCerebro'))
import memoria_automatica as recolector


class ClienteFalso:
    timeout = 45

    def __init__(self, falla=False):
        self.falla = falla
        self.guardadas = []

    def guardar_conversacion(self, *args, **kwargs):
        if self.falla:
            raise ConnectionError('servidor de prueba no disponible')
        self.guardadas.append(args)
        return {'ok': True, 'tipo': 'conversacion'}


class PruebasCaptura(unittest.TestCase):
    def setUp(self):
        self.modo = patch.object(capturas, 'en_pruebas', return_value=False)
        self.modo.start(); self.addCleanup(self.modo.stop)
        self.tmp = tempfile.TemporaryDirectory(prefix='jarvis-captura-')
        self.cola = Path(self.tmp.name) / 'pendientes'
        self.patch_cola = patch.object(capturas, 'COLA', self.cola)
        self.patch_cola.start()
        self.addCleanup(self.patch_cola.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_turno_completo_se_envia_y_se_limpia(self):
        ident = capturas.iniciar('¿Qué recuerdas de este proyecto?')
        self.assertTrue(capturas.sigue_pendiente(ident))
        capturas.finalizar(ident, 'Tengo dos notas guardadas.')
        cliente = ClienteFalso()
        resultado = capturas.guardar_pendientes(cliente)
        self.assertEqual(resultado['guardadas'], 1)
        self.assertEqual(resultado['pendientes'], 0)
        self.assertIn('Respuesta final de Jarvis:\nTengo dos notas guardadas.', cliente.guardadas[0][2])
        self.assertFalse(capturas.sigue_pendiente(ident))
        self.assertEqual(cliente.guardadas[0][0],'CHAT JARVIS')

    def test_no_captura_ni_envia_memoria_en_pruebas(self):
        with patch.object(capturas,'en_pruebas',return_value=True):
            self.assertIsNone(capturas.iniciar('/hora'))
            cliente=ClienteFalso();r=capturas.guardar_pendientes(cliente)
            self.assertEqual(r['guardadas'],0);self.assertEqual(cliente.guardadas,[])

    def test_transcripcion_identifica_hora_con_segundos(self):
        ident = capturas.iniciar('Consulta con título diferenciable')
        capturas.finalizar(ident, 'Respuesta')
        fila = __import__('json').loads((self.cola / (ident + '.json')).read_text(encoding='utf-8'))
        titulo, _ = capturas._registro(fila)
        self.assertRegex(titulo, r'Conversación Jarvis · \d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}$')

    def test_interrupcion_conserva_pregunta_y_respuesta_parcial(self):
        ident = capturas.iniciar('¿Cómo quedó la sincronización?')
        capturas.finalizar(ident, 'El último ciclo alcanzó a…', 'interrumpida')
        cliente = ClienteFalso()
        capturas.guardar_pendientes(cliente)
        contenido = cliente.guardadas[0][2]
        self.assertIn('¿Cómo quedó la sincronización?', contenido)
        self.assertIn('conversación inconclusa', contenido)
        self.assertIn('El último ciclo alcanzó a…', contenido)

    def test_peticion_privada_no_crea_archivo(self):
        for frase in ['Jarvis, no guardes este turno; es privado.',
                      'No quiero que Jarvis guarde este mensaje.',
                      'No quiero que se registre esta conversación.']:
            with self.subTest(frase=frase):
                self.assertIsNone(capturas.iniciar(frase))
                self.assertTrue(recolector.opto_privacidad(frase))
        self.assertFalse(self.cola.exists())

    def test_error_mcp_deja_turno_en_cola_y_restituye_timeout(self):
        ident = capturas.iniciar('Consulta de prueba')
        capturas.finalizar(ident, 'Respuesta de prueba')
        cliente = ClienteFalso(falla=True)
        resultado = capturas.guardar_pendientes(cliente)
        self.assertEqual(resultado['pendientes'], 1)
        self.assertTrue(capturas.sigue_pendiente(ident))
        self.assertEqual(cliente.timeout, 45)

    def test_apagado_brusco_recupera_y_sincroniza_turno_en_espera(self):
        ident = capturas.iniciar('¿Qué alcanzaste a contestar?')
        ruta = self.cola / (ident + '.json')
        fila = json.loads(ruta.read_text(encoding='utf-8'))
        fila['pid'] = 2_147_483_647  # proceso inexistente
        ruta.write_text(json.dumps(fila), encoding='utf-8')
        cliente = ClienteFalso()
        resultado = capturas.guardar_pendientes(cliente)
        self.assertEqual(resultado['guardadas'], 1)
        self.assertIn('conversación inconclusa', cliente.guardadas[0][2])
        self.assertIn('no quedó una respuesta completa', cliente.guardadas[0][2])

    def test_redacta_credenciales_sinteticas(self):
        fuente = 'OPENAI_API_KEY=FAKE_KEY_SENTINEL Authorization: Bearer FAKE_BEARER_SENTINEL123'
        resultado = capturas._redactar(fuente)
        self.assertNotIn('FAKE_KEY_SENTINEL', resultado)
        self.assertNotIn('FAKE_BEARER_SENTINEL123', resultado)
        self.assertIn('[REDACTADO]', resultado)

    def test_respuesta_final_actualiza_el_mismo_turno_inconcluso(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
            CREATE TABLE memorias(id INTEGER PRIMARY KEY,proyecto TEXT,titulo TEXT,contenido TEXT,
                creado TEXT,tipo TEXT,fuente TEXT,clave_captura TEXT UNIQUE);
            CREATE TABLE captura_eventos(hash TEXT PRIMARY KEY,source TEXT,session TEXT,procesado TEXT);
            CREATE TABLE captura_recuerdos(hash TEXT PRIMARY KEY,memoria_id INTEGER,evento_hash TEXT);
        ''')
        anterior = 'a' * 64
        proyecto = 'Jarvis'
        titulo = 'Conversación Claude Desktop · 12-10-2026 17:00'
        parcial = ('Usuario:\npregunta sobre Jarvis\n\nRespuesta de Jarvis: no se registró texto.\n\n'
                   'Estado: conversación inconclusa; se conserva la solicitud original.')
        db.execute('INSERT INTO memorias VALUES (1,?,?,?,?,?,?,?)',
                   (proyecto,titulo,parcial,'2026-10-12T20:00:00+00:00','conversacion','claude_desktop',anterior))
        db.execute('INSERT INTO captura_eventos VALUES (?,?,?,?)',(anterior,'claude_desktop','sesion-prueba','ahora'))
        db.execute('INSERT INTO captura_recuerdos VALUES (?,?,?)',('b'*64,1,anterior))
        evento={'key':'c'*64,'source':'claude_desktop','session':'sesion-prueba','user_text':'pregunta sobre Jarvis',
                'context':'','workspace':'','created':'2026-10-12T20:00:00+00:00','completion':'completa',
                'assistant_text':'respuesta visible','text':'Usuario:\npregunta sobre Jarvis\n\nRespuesta final:\nrespuesta visible'}
        resultado=recolector.commit_conversation(db,evento)
        filas=db.execute('SELECT COUNT(*) FROM memorias').fetchone()[0]
        contenido=db.execute('SELECT contenido FROM memorias WHERE id=1').fetchone()[0]
        self.assertEqual(resultado,0)
        self.assertEqual(filas,1)
        self.assertIn('Respuesta final:\nrespuesta visible',contenido)


if __name__ == '__main__':
    unittest.main()
