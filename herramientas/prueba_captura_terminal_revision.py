"""El fallo de sincronización no cierra la terminal ni oculta la respuesta."""
from contextlib import ExitStack, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jarvis_agente as J


class Pruebas(unittest.TestCase):
    def ejecutar(self, respuestas, cola, comando=(True, 'Respuesta sintética completa'), guardada=True):
        salida = io.StringIO()
        with tempfile.TemporaryDirectory() as temporal, ExitStack() as pila:
            pila.enter_context(patch.object(J.L, 'RAIZ', Path(temporal)))
            pila.enter_context(patch.object(J, '_configurar_entrada'))
            pila.enter_context(patch.object(J, 'leer_pregunta', side_effect=respuestas))
            pila.enter_context(patch.object(J, 'AJUSTES', dict(J.AJUSTES, seleccion_modelo='manual')))
            pila.enter_context(patch.object(J.threading, 'Thread'))
            pila.enter_context(patch.object(J.CONVERSACIONES, 'guardar_pendientes', side_effect=cola))
            pila.enter_context(patch.object(J.CONVERSACIONES, 'iniciar', return_value='captura-sintetica'))
            finalizar = pila.enter_context(patch.object(J.CONVERSACIONES, 'finalizar', return_value=guardada))
            pila.enter_context(patch.object(J.CONVERSACIONES, 'sigue_pendiente', return_value=False))
            pila.enter_context(patch.object(J, 'comando', return_value=comando))
            pila.enter_context(patch.object(J, 'prompt_para_turno', return_value='Contexto sintético'))
            pila.enter_context(patch.object(J, 'responder_con_respaldo', return_value='Respuesta sintética del modelo'))
            with redirect_stdout(salida):
                J._principal()
        return salida.getvalue(), finalizar

    def test_fallo_inicial_permite_llegar_a_la_entrada(self):
        texto, finalizar = self.ejecutar(['salir'], [ConnectionError('MCP sintético caído')])
        self.assertIn('/sincronizar', texto)
        finalizar.assert_not_called()

    def test_fallo_tras_comando_conserva_y_muestra_su_respuesta(self):
        texto, finalizar = self.ejecutar(['/ayuda', 'salir'], [{'pendientes': 0}, ConnectionError('MCP sintético caído')])
        self.assertIn('Respuesta sintética completa', texto)
        self.assertIn('/sincronizar', texto)
        finalizar.assert_called_once()
        self.assertEqual(finalizar.call_args.args[1], 'Respuesta sintética completa')

    def test_fallo_tras_modelo_no_finaliza_como_fallida_ni_oculta_texto(self):
        texto, finalizar = self.ejecutar(['Compara dos algoritmos', 'salir'], [{'pendientes': 0}, OSError('Fallo sintético')], comando=(False, ''))
        self.assertIn('Respuesta sintética del modelo', texto)
        finalizar.assert_called_once()
        self.assertEqual(finalizar.call_args.args[1:], ('Respuesta sintética del modelo', 'completa'))

    def test_guardado_no_confirmado_no_se_anuncia_como_guardado(self):
        texto, _ = self.ejecutar(['/ayuda', 'salir'], [{'pendientes': 0}], guardada=False)
        self.assertIn('Respuesta sintética completa', texto)
        self.assertIn('No pude confirmar el guardado local', texto)
        self.assertNotIn('respuesta está guardada localmente', texto)


if __name__ == '__main__':
    unittest.main()
