"""Una propuesta no debe mezclar filas truncadas/ilegibles ni aplicarse sola."""
import unittest
from metricas_presupuesto_r6 import propuesta

class Pruebas(unittest.TestCase):
 def test_excluye_truncados_fallos_y_tipos_incorrectos(self):
  buenas=[{'ok':True,'tokens_reales':100,'bytes_componentes':400} for _ in range(10)]
  malas=[{'ok':False,'tokens_reales':9999,'bytes_componentes':1},{'ok':True,'riesgo_truncado':True,'tokens_reales':9999,'bytes_componentes':1},{'ok':True,'tokens_reales':True,'bytes_componentes':400},{'ok':True,'tokens_reales':100,'bytes_componentes':0}]
  d=propuesta(buenas+malas)
  self.assertEqual(d['muestras'],10);self.assertAlmostEqual(d['bytes_por_token_propuesto'],3.636,places=3);self.assertFalse(d['coeficiente_aplicado'])
 def test_no_propone_con_muestras_insuficientes(self):
  self.assertEqual(propuesta([{'ok':True,'tokens_reales':10,'bytes_componentes':40}]*4)['estado'],'muestras insuficientes')
 def test_sonda_captura_sin_cambiar_la_respuesta_ni_saltar_el_controlador(self):
  import io
  from medir_presupuesto_r6 import CapturaRespuesta
  raw=b'{"message":{"content":""},"prompt_eval_count":123}'
  c={}
  with CapturaRespuesta(io.BytesIO(raw),c) as r:self.assertEqual(r.read(1000),raw)
  self.assertEqual(c['prompt_eval_count'],123);self.assertEqual(c['message']['content'],'')
if __name__=='__main__':unittest.main()
