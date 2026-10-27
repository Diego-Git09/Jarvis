"""Cambio local de modelos: simulación de sensores, PS y confirmación de descarga."""
import unittest
from unittest.mock import Mock,patch
import control_recursos as R
import cliente_ollama as O
import enrutador_modelos as M
from prueba_control_recursos import INFO,foto
class Pruebas(unittest.TestCase):
 def admision(self,anterior,nuevo,*,ajeno=False,sensores=True,desaparece=True):
  c=Mock();c.ErrorOllama=O.ErrorOllama;c.acreditar_pesos_locales.return_value=INFO
  cargados=[{'name':anterior,'size':6200000000,'size_vram':6200000000,'context_length':8192}];eventos=[]
  descargado=[False]
  def solicitar(ruta,cuerpo=None,**kw):
   eventos.append((ruta,cuerpo))
   if ruta=='/api/tags':return {'models':[{'name':nuevo,'size':5200000000}]}
   if ruta=='/api/ps':return {'models':[] if descargado[0] and desaparece else cargados}
   if ruta=='/api/generate':
    self.assertEqual(cuerpo['model'],anterior);self.assertEqual(cuerpo['keep_alive'],0);descargado[0]=True;return {'done':True}
   self.fail('API inesperada '+ruta)
  c.solicitar.side_effect=solicitar
  def leer():
   f=foto(7900 if descargado[0] and desaparece else 1500)
   if ajeno:f['pesados']=[{'nombre':'render_ajeno','mib':3000}]
   if not sensores:f['gpu']={'ok':False}
   return f
  with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(R,'instantanea',side_effect=leer),patch.object(R,'_VACIANDO_HASTA',0),patch.object(R,'_REGISTRO',{}):
   try:r=R.comprobar(c,{'model':nuevo,'options':{'num_ctx':8192}},plazo_fin=R.time.monotonic()+.1)
   except O.ErrorOllama as error:r=error
  return r,eventos
 def test_qwen_se_descarga_antes_de_deepseek(self):
  r,e=self.admision('qwen3:8b','jarvis-deepseek:8b');self.assertIsInstance(r,dict);self.assertTrue(r['permitido']);self.assertTrue(any(x[0]=='/api/generate' for x in e));self.assertEqual(e[-1][0],'/api/ps')
 def test_deepseek_se_descarga_antes_de_qwen(self):
  r,e=self.admision('jarvis-deepseek:8b','qwen3:8b');self.assertIsInstance(r,dict);self.assertTrue(r['permitido'])
 def test_ajeno_no_descarga_nada_y_ofrece_opciones(self):
  r,e=self.admision('qwen3:8b','jarvis-deepseek:8b',ajeno=True);self.assertIsInstance(r,O.ErrorOllama);self.assertFalse(any(x[0]=='/api/generate' for x in e));self.assertIn('/gpu cpu',str(r))
 def test_sin_sensores_no_supone_que_toda_la_vram_es_suya(self):
  _,e=self.admision('qwen3:8b','jarvis-deepseek:8b',sensores=False);self.assertFalse(any(x[0]=='/api/generate' for x in e))
 def test_modelo_ajeno_no_se_descarga_por_nombre_parecido(self):
  r,e=self.admision('qwen3:8b-ajeno','jarvis-deepseek:8b');self.assertIsInstance(r,O.ErrorOllama);self.assertFalse(any(x[0]=='/api/generate' for x in e))
 def test_descarga_no_confirmada_no_acredita_memoria(self):
  r,e=self.admision('qwen3:8b','jarvis-deepseek:8b',desaparece=False);self.assertIsInstance(r,O.ErrorOllama)
 def test_coste_de_recarga_no_cambia_un_analisis_complejo(self):
  d=M.seleccionar_respuesta('analiza las ventajas de microservicios',['qwen3:8b','jarvis-deepseek:8b'],'qwen3:8b',residentes=['qwen3:8b'])
  self.assertEqual(d['modelo'],'jarvis-deepseek:8b')
 def test_reutiliza_residente_para_explicacion_que_alcanza(self):
  d=M.seleccionar_respuesta('que es una variable',['qwen3:8b','jarvis-deepseek:8b'],'qwen3:8b',residentes=['jarvis-deepseek:8b'])
  self.assertEqual(d['modelo'],'jarvis-deepseek:8b');self.assertIn('recarga',d['motivo'])
if __name__=='__main__':unittest.main()
