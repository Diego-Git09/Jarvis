"""Un reintento tardío no puede revocar el cierre de la aplicación."""
import unittest
from unittest.mock import Mock, patch

import cliente_ollama as O
import configuracion_jarvis as C
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def setUp(self):
        p = patch.multiple(O, _SERVICIO=None, _SERVICIO_GENERACION=0, _CIERRE_SOLICITADO=False)
        p.start()
        self.addCleanup(p.stop)

    def test_reintento_por_comando_no_reabre_una_sesion_cerrada(self):
        O.cerrar_servicio()
        with patch('entorno_jarvis.en_pruebas', return_value=False), patch.object(O, 'leer', return_value=(dict(C.DEFAULT), '')), patch('servicio_ollama.SesionOllama') as crear, patch.object(O, 'estado_servicio'):
            ok, texto = comando_local('/ollama reintentar', [], {}, lambda _: False, dict(C.DEFAULT), lambda: None, None)
        self.assertTrue(ok)
        crear.assert_not_called()
        self.assertTrue(O.sesion_cerrada())
        self.assertIn('cerrando', texto)

    def test_cierre_durante_lectura_de_configuracion_impide_crear_sesion(self):
        def leer():
            O.cerrar_servicio()
            return dict(C.DEFAULT), ''
        with patch('entorno_jarvis.en_pruebas', return_value=False), patch.object(O, 'leer', side_effect=leer), patch('servicio_ollama.SesionOllama') as crear, self.assertRaises(O.ErrorOllama) as error:
            O.activar_servicio()
        self.assertEqual(error.exception.tipo, 'cancelada')
        crear.assert_not_called()
        self.assertTrue(O.sesion_cerrada())

    def test_solo_abrir_interfaz_nueva_puede_reiniciar_el_ciclo(self):
        O.cerrar_servicio()
        servicio = Mock()
        servicio.estado.return_value = {'sesion_cerrada': False}
        with patch('entorno_jarvis.en_pruebas', return_value=False), patch.object(O, 'leer', return_value=(dict(C.DEFAULT), '')), patch('servicio_ollama.SesionOllama', return_value=servicio):
            self.assertIs(O.activar_servicio(nueva_sesion=True), servicio)
        self.assertFalse(O.sesion_cerrada())

    def test_autoinicio_desactivado_no_revoca_un_cierre_anterior(self):
        O.cerrar_servicio()
        with patch('entorno_jarvis.en_pruebas', return_value=False), patch.object(O, 'leer', return_value=(dict(C.DEFAULT, autoinicio_ollama=False), '')), patch('servicio_ollama.SesionOllama') as crear:
            try:
                O.activar_servicio()
            except O.ErrorOllama as error:
                self.assertEqual(error.tipo, 'cancelada')
        crear.assert_not_called()
        self.assertTrue(O.sesion_cerrada())


if __name__ == '__main__':
    unittest.main()
