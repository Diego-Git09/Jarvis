"""El estado debe distinguir R6 actual de informes anteriores, sin publicar."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import configuracion_jarvis as C
import estado_ia_texto as E

class Pruebas(unittest.TestCase):
 def test_ronda6_verificada_tiene_prioridad_sin_borrar_historia(self):
  with tempfile.TemporaryDirectory() as tmp:
   reportes=Path(tmp);r6=reportes/'ronda6_20261023';r6.mkdir();r5=reportes/'ronda5_20261021';r5.mkdir()
   (r6/'resumen_ronda6.json').write_text(json.dumps({'version':1,'validado':True,'pruebas':2627,'fallos':0,'presupuesto':{'muestras':52,'estado':'propuesta pendiente de revisión'},'comparacion':{'identicos':True}}))
   with patch('externo_zen.estado',return_value={'encendido':False}):
    t=E.redactar(C.DEFAULT,'modelo','FECHA','2627 pruebas, 0 fallos','',raiz=r5)
   self.assertIn('ronda6',t.lower());self.assertIn('cache',t.lower());self.assertIn('sin llamadas',t.lower())
   self.assertIn('sin commit',t.lower());self.assertLessEqual(len(t),6200)
 def test_sin_resumen_verificado_no_finge_cierre_ronda6(self):
  with tempfile.TemporaryDirectory() as tmp:
   r5=Path(tmp)/'ronda5_20261021';r5.mkdir()
   t=E.redactar(C.DEFAULT,'modelo','FECHA','sin batería','',raiz=r5)
   self.assertNotIn('Detalle vigente: documentacion/RONDA6_',t)
if __name__=='__main__':unittest.main()
