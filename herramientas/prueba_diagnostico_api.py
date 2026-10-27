"""Errores remotos clasificados sin divulgar claves ni respuestas HTTP."""
import json
import unittest
from unittest.mock import patch
import internet_jarvis as W
import segunda_opinion as I


class Pruebas(unittest.TestCase):
    def error(self,codigo,mensaje='',detalles=None):return W.ErrorHTTP(codigo,json.dumps({'error':{'message':mensaje,'status':'RESOURCE_EXHAUSTED' if codigo==429 else 'PERMISSION_DENIED','details':detalles or []}}).encode())

    def test_cuota_cero_se_distingue_de_esperar(self):
        e=self.error(429,'Quota exceeded, limit: 0, private key SECRET')
        t=I.mensaje_error_api(e);self.assertIn('cuota 0',t);self.assertNotIn('SECRET',t);self.assertNotIn('SECRET',str(e))

    def test_reintento_por_minuto_y_limite_diario_no_se_confunden(self):
        e=self.error(429,detalles=[{'violations':[{'quotaId':'GenerateRequestsPerMinute-FreeTier'}]},{'retryDelay':'23.5s'}])
        self.assertIn('24 segundos',I.mensaje_error_api(e));self.assertEqual(e.diagnostico['nivel'],'gratuito')
        e=self.error(429,detalles=[{'violations':[{'quotaId':'GenerateRequestsPerDay-FreeTier'}]},{'retryDelay':'23s'}])
        self.assertIn('diario',I.mensaje_error_api(e))

    def test_403_restricciones_y_clave_bloqueada(self):
        e=self.error(403,detalles=[{'reason':'API_KEY_HTTP_REFERRER_BLOCKED','metadata':{'apiKey':'SECRET'}}])
        self.assertIn('navegador',I.mensaje_error_api(e));self.assertNotIn('SECRET',json.dumps(e.diagnostico))
        e=self.error(403,'Your API key was reported as leaked. SECRET')
        self.assertIn('bloqueó',I.mensaje_error_api(e));self.assertNotIn('SECRET',I.mensaje_error_api(e))

    def test_cuerpo_invalido_o_sin_detalles_no_inventa_causa(self):
        for datos in [b'<html>SECRET</html>',b'{"error":"SECRET"}',b'bad json']:
            e=W.ErrorHTTP(403,datos);self.assertFalse(e.diagnostico);self.assertNotIn('SECRET',I.mensaje_error_api(e))
            self.assertIn('No confirma',I.mensaje_error_api(e))

    def test_consulta_rechazada_es_un_solo_intento_sin_secretos(self):
        c={'proveedor':'OpenAI','modelo':'modelo-prueba','url':I.ENDPOINTS['OpenAI'],'clave':'SECRET','credencial':'ref'}
        e=self.error(429,detalles=[{'violations':[{'quotaValue':'0'}]}])
        with patch('politica_ia.permite_externa',return_value=True),patch.object(I,'configuracion',return_value=c),patch.object(W,'solicitar_publico',side_effect=e) as red,patch.object(I.P,'registrar_resultado') as guardar:
            r=I.preguntar_externa('Pregunta sintética',lambda _:True,perfil='OpenAI')
        self.assertFalse(r['ok']);self.assertEqual(red.call_count,1);self.assertNotIn('SECRET',json.dumps(r))
        self.assertTrue(r['diagnostico']['cuota_cero']);guardar.assert_called_once()

    def test_transporte_lee_error_acotado_y_cierra_conexion(self):
        class Respuesta:
            status=429
            def read(self,n):self.cantidad=n;return b'{"error":{"status":"RESOURCE_EXHAUSTED"}}'
            def getheader(self,n,d=''):return '5' if n=='Retry-After' else d
        respuesta=Respuesta()
        con=unittest.mock.Mock();con.getresponse.return_value=respuesta
        with patch.object(W,'direcciones_publicas',return_value=['8.8.8.8']),patch.object(W,'ConexionPublica',return_value=con),self.assertRaises(W.ErrorHTTP) as captura:
            W.solicitar_publico('https://example.com/api',b'{}',{'Authorization':'Bearer SECRET'})
        self.assertEqual(respuesta.cantidad,8192);con.close.assert_called_once();self.assertEqual(captura.exception.diagnostico['espera_segundos'],5)


if __name__=='__main__':unittest.main()
