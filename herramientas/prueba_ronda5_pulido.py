"""Presentación sin alterar literales, errores de red y estimación informativa."""
import unittest
from unittest.mock import patch
import formato_respuestas as F,seguridad_texto as S,clima_jarvis as C
import presupuesto_contexto as P


class Pruebas(unittest.TestCase):
    def test_prefijo_y_tercera_persona_fuera_del_codigo(self):
        r=F.presentar('explicame esto','Explico con estilo simple: El usuario no autorizó el cambio..')
        self.assertNotIn('Explico con estilo',r);self.assertNotIn('El usuario',r);self.assertNotIn('..',r)
    def test_literales_y_rutas_no_se_reescriben(self):
        for r in ('```python\nprint("Explico con estilo simple:")\n```','Ruta ../src/main.py','«El usuario no autorizó»'):
            self.assertEqual(F.presentar('explica',r),r)
        self.assertEqual(F.presentar('Repite exactamente y literal','Explico con estilo simple:'),'Explico con estilo simple:')
    def test_error_clima_timeout_esta_en_espanol_y_no_inventa_causa(self):
        with patch.object(C,'_json',side_effect=TimeoutError('The read operation timed out')):
            r=C.consultar_clima('Santiago')
        self.assertEqual(r['causa'],'red');t=C.presentar(r);self.assertNotIn('timed out',t);self.assertIn('conexión',t)
    def test_error_http_clima_es_del_servicio(self):
        with patch.object(C,'_json',side_effect=C.W.ErrorHTTP(503)):
            r=C.consultar_clima('Santiago')
        self.assertEqual(r['causa'],'servicio');self.assertIn('503',r['error'])
    def test_apex_no_redacta_un_script_como_conexion(self):
        for t in ('@apexins.sql SYSAUX SYSAUX TEMP /i/','@$ORACLE_HOME/apex/install/apexins.sql SYSAUX SYSAUX TEMP /i/','@carpeta/archivo.sql@revision'):
            self.assertEqual(S.redactar_credenciales(t),t)
        for t in ('sqlplus usuario/clave_ficticia@host_ficticio','sqlplus "usuario/clave_ficticia@host_ficticio"'):
            self.assertNotIn('clave_ficticia',S.redactar_credenciales(t))
    def test_calibracion_no_cambia_el_tope_de_admision(self):
        estado={};r={'entrada_tokens_estimados':3600};original=P.BYTES_POR_TOKEN
        for _ in range(5):P.calibrar(estado,'modelo',r,2300)
        self.assertEqual(P.BYTES_POR_TOKEN,original);self.assertAlmostEqual(r['entrada_calibrada_tokens'],2300,delta=1)
        self.assertEqual(r['entrada_tokens_estimados'],3600)
    def test_reglas_propuestas_caben_en_la_mitad(self):
        import prompt_jarvis as R
        self.assertLessEqual(len(R.COMPACTO.encode()),len(R.BASE.encode())/2)
        for p in ('permiso','no sobrescrib','datos','127.0.0.1:8767','no ejecut','actual'):
            self.assertIn(p,R.COMPACTO.lower())


if __name__=='__main__':unittest.main()
