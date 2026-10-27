"""El resumen vigente no finge configuración válida ni deja archivos truncados."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import configuracion_jarvis as C
import estado_ia as E
import estado_ia_texto as T

class Pruebas(unittest.TestCase):
 def entorno(self,root):
  r=root/'registros/reportes/ronda6_20261023';r.mkdir(parents=True)
  (r/'resumen_ronda6.json').write_text(json.dumps({'version':1,'validado':True,'pruebas':2645,'fallos':0,'presupuesto':{'muestras':51}}))
 def generar(self,r,aviso=''):
  with patch.object(E,'TRABAJO',r),patch.object(E,'RESUMEN',r/'estado.md'),patch.object(E,'REGISTROS',r/'registros'),patch.object(E,'leer_config',return_value=(dict(C.DEFAULT),aviso)),patch('externo_zen.estado',return_value={'encendido':False}):
   return E.generar()
 def test_ilegible_se_advierte_tambien_con_plantilla_ronda6(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.entorno(r);texto=self.generar(r,'ilegible')
   self.assertIn('Configuración guardada ilegible',texto)
   self.assertIn('valores predeterminados',texto)
 def test_resumen_no_sigue_enlace_a_otro_archivo(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);victima=r/'destino.txt';victima.write_text('NO_MODIFICAR')
   (r/'estado.md').symlink_to(victima)
   with self.assertRaises((OSError,ValueError)):self.generar(r)
   self.assertEqual(victima.read_text(),'NO_MODIFICAR')
 def test_fallo_de_replace_conserva_resumen_anterior(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);(r/'estado.md').write_text('ANTERIOR')
   with patch('herramientas_escritura.os.replace',side_effect=OSError('fallo sintético')),self.assertRaises(OSError):self.generar(r)
   self.assertEqual((r/'estado.md').read_text(),'ANTERIOR')
 def test_resumen_y_cambios_se_escriben_privados(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.generar(r)
   for nombre in ('estado.md','JARVIS_CAMBIOS_RECIENTES.md','JARVIS_INDICE_CONTEXTO.md'):
    self.assertEqual((r/nombre).stat().st_mode&0o777,0o600)
 def test_indice_no_lee_contexto_enlazado(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);p=r/'fuente.txt';p.write_text('## NO_INCLUIR_DATOS_ENLAZADOS')
   (r/'CONTEXTO_COMPLETO_JARVIS.md').symlink_to(p);self.generar(r)
   self.assertNotIn('NO_INCLUIR_DATOS_ENLAZADOS',(r/'JARVIS_INDICE_CONTEXTO.md').read_text())

if __name__=='__main__':unittest.main()
