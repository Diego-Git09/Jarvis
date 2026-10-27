"""Cerrar durante una petición cancela su resultado y sus respaldos."""
import io
import unittest
import urllib.error
from unittest.mock import Mock, patch

import cliente_ollama as O
import jarvis_agente as J
import externo_zen as Z


class CuerpoQueCierra(io.BytesIO):
    def read1(self, n=-1):
        O.cerrar_servicio()
        return super().read1(n)


class Pruebas(unittest.TestCase):
    def setUp(self):
        p = patch.multiple(O, _SERVICIO=None, _SERVICIO_GENERACION=0, _CIERRE_SOLICITADO=False)
        p.start()
        self.addCleanup(p.stop)

    def test_cierre_durante_fallo_de_conexion_es_cancelacion(self):
        def abrir(*args, **kwargs):
            O.cerrar_servicio()
            raise ConnectionResetError('Cierre sintético')
        with patch.object(O, 'ABRIR', side_effect=abrir) as red, self.assertRaises(O.ErrorOllama) as error:
            O.solicitar('/api/version')
        self.assertEqual(error.exception.tipo, 'cancelada')
        red.assert_called_once()

    def test_respuesta_que_llega_despues_del_cierre_se_descarta(self):
        with patch.object(O, 'ABRIR', return_value=CuerpoQueCierra(b'{"version":"sintetica"}')), self.assertRaises(O.ErrorOllama) as error:
            O.solicitar('/api/version')
        self.assertEqual(error.exception.tipo, 'cancelada')

    def test_cierre_durante_http_de_error_libera_la_respuesta(self):
        cuerpo = io.BytesIO(b'{"error":"sintetico"}')
        def abrir(*args, **kwargs):
            O.cerrar_servicio()
            raise urllib.error.HTTPError('http://127.0.0.1:23456', 503, 'sintetico', {}, cuerpo)
        with patch.object(O, 'ABRIR', side_effect=abrir), self.assertRaises(O.ErrorOllama) as error:
            O.solicitar('/api/version')
        self.assertEqual(error.exception.tipo, 'cancelada')
        self.assertTrue(cuerpo.closed)

    def test_streaming_no_entrega_lineas_si_la_sesion_se_cerro(self):
        with patch.object(O, 'ABRIR', return_value=io.BytesIO(b'{"done":true}\n')), self.assertRaises(O.ErrorOllama) as error:
            with O.abrir_flujo_chat({}) as lineas:
                O.cerrar_servicio()
                next(lineas)
                self.fail('Se entregó una línea después de cerrar')
        self.assertEqual(error.exception.tipo, 'cancelada')

    def test_turno_nuevo_tras_cerrar_no_inicia_modelo_ni_externo(self):
        O.cerrar_servicio()
        with patch.object(J, 'ejecutar_turno') as local, patch.object(Z, 'elegir') as externo, self.assertRaises(O.ErrorOllama) as error:
            J.responder_con_respaldo([{'role': 'user', 'content': 'Compara dos algoritmos'}], None, lambda _: False, {})
        self.assertEqual(error.exception.tipo, 'cancelada')
        local.assert_not_called()
        externo.assert_not_called()

    def test_cierre_mientras_se_prepara_el_servidor_es_cancelacion(self):
        servicio = Mock()
        def asegurar(**kwargs):
            O.cerrar_servicio()
            return {'ok': False, 'tipo': 'cerrada', 'error': 'Cierre sintético'}
        servicio.asegurar.side_effect = asegurar
        with patch.object(O, '_SERVICIO', servicio), patch.object(O, 'ABRIR') as red, self.assertRaises(O.ErrorOllama) as error:
            O.solicitar('/api/version')
        self.assertEqual(error.exception.tipo, 'cancelada')
        red.assert_not_called()

    def test_error_de_una_peticion_interrumpida_no_evalua_respaldo_externo(self):
        def ejecutar(*args, **kwargs):
            O.cerrar_servicio()
            raise O.ErrorOllama('Cierre sintético', tipo='conexion', servicio=True)
        historial = [{'role': 'system', 'content': J.SISTEMA},
                     {'role': 'user', 'content': 'Compara alternativas de ordenación de listas'}]
        estado = {}
        with patch.object(J, 'ejecutar_turno', side_effect=ejecutar), patch.object(O, 'modelos') as modelos, patch.object(Z, 'elegir', return_value=(None, 'desactivado')) as externo:
            J.responder_con_respaldo(historial, None, lambda _: False, estado, mostrar=lambda _: None)
        modelos.assert_not_called()
        externo.assert_not_called()
        self.assertEqual(estado['_estado_respuesta'], 'interrumpida')


if __name__ == '__main__':
    unittest.main()
