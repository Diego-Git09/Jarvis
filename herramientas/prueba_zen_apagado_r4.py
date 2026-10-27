import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import externo_zen as Z
class Pruebas(unittest.TestCase):
    def test_apagado_cero_transporte_y_cero_registro(self):
        transporte=Mock();registro=Mock()
        with patch.object(Z,'estado',return_value={'encendido':False}),patch.object(Z,'anotar_envio',registro):
            with self.assertRaisesRegex(ValueError,'apagado'):Z.preguntar('Explica recursión en Python',{'id':'inexistente'},'prueba',transporte)
        transporte.assert_not_called();registro.assert_not_called()
    def test_sin_clave_incluso_catalogo_previo_cero_intentos(self):
        modelo=next(m for m in Z.modelos() if m['id']=='deepseek-v4.1-flash-free');transporte=Mock();registro=Mock()
        with patch.object(Z,'estado',return_value={'encendido':True,'revision':1,'modelos':{},'catalogo':[modelo['id']],'catalogo_fecha':time.time()}),patch.object(Z,'clave',return_value=''),patch.object(Z,'anotar_envio',registro):
            with self.assertRaisesRegex(ValueError,'Falta la clave'):Z.preguntar('Explica recursión en Python',modelo,'prueba',transporte)
        transporte.assert_not_called();registro.assert_not_called()
    def test_estado_no_pide_clave_ni_red(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(Z,'ARCHIVO',Path(tmp)/'estado'),patch.object(Z,'AUDITORIA',Path(tmp)/'auditoria'),patch.object(Z,'clave',return_value=''),patch.object(Z,'transporte',side_effect=AssertionError('Sin red')):
            hecho,t=Z.comando('/externo estado',lambda _:self.fail('Lectura'))
        self.assertTrue(hecho);self.assertIn('apagado',t);self.assertIn('falta una clave válida',t)
if __name__=='__main__':unittest.main()
