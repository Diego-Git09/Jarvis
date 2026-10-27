"""Tk y procesos HTTP sintéticos juntos, sin modelos ni Segundo Cerebro real."""
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from interfaz_grafica import Aplicacion, J
from servicio_ollama import SesionOllama
from salud_ollama import comprobar
from soporte_pruebas_servicio import ejecutable, puerto_libre, esperar
import configuracion_jarvis as CONFIG


@unittest.skipUnless(os.environ.get('JARVIS_UI_REAL') == '1', 'Requiere Tk real')
class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self.temporal.name)
        self.url = 'http://127.0.0.1:' + str(puerto_libre())
        self.sesiones = []

    def tearDown(self):
        for sesion in self.sesiones:
            sesion.cerrar()
        for sesion in self.sesiones:
            proceso = getattr(sesion, '_supervisor', None)
            if proceso is not None:
                try:
                    proceso.wait(timeout=6)
                except Exception:
                    proceso.terminate()
                    proceso.wait(timeout=2)
        self.temporal.cleanup()

    def sesion(self, nombre, fallar=False):
        sesion = SesionOllama(
            self.url, raiz=self.raiz / nombre,
            ejecutable=ejecutable(self.raiz, fallar=fallar), permitir_pruebas=True)
        self.sesiones.append(sesion)
        return sesion

    def abrir_y_cerrar(self, sesion, comprobar_chat):
        lista = threading.Event()
        root = tk.Tk()
        root.withdraw()
        root.attributes('-alpha', 0)
        app = None
        with ExitStack() as pila:
            pila.enter_context(patch.multiple(J.O, BASE=self.url, _SERVICIO=sesion,
                                             _SERVICIO_GENERACION=0, _CIERRE_SOLICITADO=False))
            pila.enter_context(patch('entorno_jarvis.en_pruebas', return_value=False))
            pila.enter_context(patch.object(J.O, 'leer', return_value=(dict(CONFIG.DEFAULT, ollama_url=self.url), '')))
            pila.enter_context(patch.object(J.CONVERSACIONES, 'guardar_pendientes', return_value={'pendientes': 0}))
            pila.enter_context(patch.object(Aplicacion, 'actualizar_estructura'))
            pila.enter_context(patch.object(Aplicacion, '_consultar_servicios', side_effect=lista.set))
            try:
                app = Aplicacion(root, Mock())
                fin = time.monotonic() + 8
                while not lista.is_set() and time.monotonic() < fin:
                    root.update()
                    time.sleep(.02)
                self.assertTrue(lista.is_set(), 'El inicio gráfico no terminó a tiempo')
                app._procesar_eventos()
                comprobar_chat(app.chat.get('1.0', 'end-1c'))
            finally:
                for trabajo in root.tk.call('after', 'info'):
                    root.after_cancel(trabajo)
                if app is not None:
                    app.cerrar()
                    app._hilo_cierre_conversaciones.join(2)
                else:
                    root.destroy()

    def test_ventana_inicia_servidor_apagado_y_su_cierre_lo_detiene(self):
        sesion = self.sesion('propio')
        def revisar(texto):
            self.assertTrue(comprobar(self.url)['ok'])
            self.assertIn('estaba apagado', texto)
            self.assertEqual(sesion.estado()['gestion'], 'iniciado_por_jarvis')
        self.abrir_y_cerrar(sesion, revisar)
        self.assertTrue(esperar(lambda: not comprobar(self.url, .1)['ok']))

    def test_ventana_conserva_servidor_preexistente(self):
        original = self.sesion('original')
        self.assertTrue(original.asegurar(4)['ok'])
        sesion = self.sesion('interfaz')
        def revisar(texto):
            self.assertIn('ya estaba encendido', texto)
            self.assertEqual(sesion.estado()['gestion'], 'preexistente')
        self.abrir_y_cerrar(sesion, revisar)
        self.assertTrue(comprobar(self.url)['ok'])

    def test_ventana_muestra_arranque_fallido_sin_afirmar_que_funciono(self):
        sesion = self.sesion('fallido', fallar=True)
        def revisar(texto):
            self.assertFalse(sesion.estado()['ok'])
            self.assertIn('terminó antes', texto)
            self.assertNotIn('Ollama disponible.', texto)
        self.abrir_y_cerrar(sesion, revisar)
        self.assertFalse(comprobar(self.url, .1)['ok'])


if __name__ == '__main__':
    unittest.main()
