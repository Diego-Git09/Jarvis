import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import metricas_modelos as M
class Pruebas(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);p=patch.object(M,'ARCHIVO',Path(t.name)/'metricas.json');p.start();self.addCleanup(p.stop)
        self.e={};self.d={'clase':'compleja','regla':'analisis','modelo':'jarvis-deepseek:8b','motivo':'NO_GUARDAR_TEXTO'}
    def test_guarda_solo_conteos_y_tiempo_no_motivo(self):
        M.registrar(self.e,self.d,2);v=next(iter(M.leer()['grupos'].values()))
        self.assertEqual(v['segundos'],2);self.assertNotIn('NO_GUARDAR_TEXTO',M.ARCHIVO.read_text());self.assertEqual(M.ARCHIVO.stat().st_mode&0o777,0o600)
    def test_queja_solo_inmediata_una_vez(self):
        M.registrar(self.e,self.d,1);M.entrada('no entendí esto',self.e);M.entrada('está mal',self.e)
        self.assertEqual(next(iter(M.leer()['grupos'].values()))['quejas'],1)
    def test_turno_intermedio_corta_asociacion(self):
        M.registrar(self.e,self.d,1);M.entrada('otra pregunta',self.e);M.entrada('está mal',self.e)
        self.assertEqual(next(iter(M.leer()['grupos'].values()))['quejas'],0)
    def test_escalar_separado_de_queja_y_sin_texto(self):
        M.registrar(self.e,self.d,1);M.entrada('/escalar',self.e)
        v=next(iter(M.leer()['grupos'].values()));self.assertEqual(v['quejas'],0);self.assertEqual(v['escalados'],1)
    def test_propuesta_no_modifica_reglas(self):
        import enrutador_modelos
        p=Path(enrutador_modelos.__file__);antes=p.read_bytes()
        for i in range(5):M.registrar(self.e,self.d,1);M.entrada('está mal',self.e)
        self.assertIn('Propuesta:',M.presentar());self.assertEqual(p.read_bytes(),antes)
    def test_controlador_y_marcas_humanas_no_se_cuentan(self):
        M.registrar(self.e,dict(self.d,sin_inferencia=True),1);self.assertFalse(M.ARCHIVO.exists())
        M.registrar(self.e,self.d,1);M.entrada('mal falta un ejemplo',self.e)
        self.assertEqual(next(iter(M.leer()['grupos'].values()))['quejas'],0)
    def test_datos_corruptos_no_sobrescritos(self):
        M.ARCHIVO.write_text('dañado');M.registrar(self.e,self.d,1);self.assertEqual(M.ARCHIVO.read_text(),'dañado');self.assertIn('_metricas_error',self.e)
    def test_modelo_y_regla_arbitrarios_no_se_almacenan(self):
        M.registrar(self.e,{'modelo':'PRIVADO','regla':'PRIVADO','clase':'PRIVADO'},1)
        self.assertNotIn('PRIVADO',M.ARCHIVO.read_text())
if __name__=='__main__':unittest.main()
