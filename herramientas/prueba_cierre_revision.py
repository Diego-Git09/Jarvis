"""Solo un recibo final válido puede sustituir el estado histórico."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import configuracion_jarvis as C
import estado_ia_texto as E
from estado_ia_revision_texto import cierre,redactar

class Pruebas(unittest.TestCase):
 def dato(self):return {'version':1,'validado':True,'base_pruebas':2645,'pruebas':2800,'fallos':0}
 def test_sin_recibo_no_inventa_cierre(self):
  with tempfile.TemporaryDirectory() as t:self.assertIsNone(cierre(Path(t)))
 def test_recibo_invalido_no_afirma_terminado(self):
  for cambios in ({'validado':False},{'pruebas':0},{'fallos':1},{'pruebas':True},{'base_pruebas':999999},{'version':2}):
   with self.subTest(cambios=cambios),tempfile.TemporaryDirectory() as t:
    p=Path(t)/'revision_20261025';p.mkdir();(p/'cierre.json').write_text(json.dumps(dict(self.dato(),**cambios)))
    self.assertIsNone(cierre(Path(t)))
 def test_resumen_nuevo_es_compacto_y_no_afirma_publicacion(self):
  with patch('externo_zen.estado',return_value={'encendido':False}):
   texto=redactar(C.DEFAULT,'modelo','FECHA',self.dato())
  self.assertLessEqual(len(texto),6200);self.assertLessEqual(len(texto.split()),2000)
  self.assertIn('/ollama',texto);self.assertIn('externo apagado',texto);self.assertIn('2800/0',texto)
  self.assertIn('permiso separado',texto)
 def test_cierre_actual_tiene_prioridad(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);nuevo=r/'revision_20261025';nuevo.mkdir();(nuevo/'cierre.json').write_text(json.dumps(self.dato()))
   vieja=r/'ronda5_20261021';vieja.mkdir()
   with patch('externo_zen.estado',return_value={'encendido':False}):texto=E.redactar(C.DEFAULT,'modelo','FECHA','histórico','',raiz=vieja)
   self.assertIn('REVISION_2026-10-25.md',texto);self.assertIn('2800/0',texto)

if __name__=='__main__':unittest.main()
