"""Integración de payload, referencias pegadas y vencimiento de cachés."""
import io,json,unittest
from unittest.mock import patch
import cliente_ollama as O
import control_recursos as C
import externo_zen as Z
import jarvis_agente as J
from prueba_control_recursos import INFO

class Pruebas(unittest.TestCase):
 def setUp(self):self.addCleanup(patch.stopall)
 def test_diez_marcadores_de_pegados_no_cambian_preferencia(self):
  for marcador in ['[Adjunto: uno.txt]','[Adjunto: dos.pdf]','[Adjunto: Tanda]','[Adjunto: archivo.py]','[Adjunto: datos.sql]','[Adjunto: fuente.md]','[Adjunto: notas.txt]','[Adjunto: tabla.csv]','[Adjunto: documento.docx]','[Adjunto: antes.txt]']:
   with self.subTest(marcador=marcador),patch.object(Z,'estado',return_value={'encendido':False}),patch.object(Z,'clave',side_effect=AssertionError('Sin claves')):
    e={};Z.elegir('Explica un byte.\n'+marcador+' usa el externo','compleja',e,fallo=True)
    self.assertNotIn('_preferencia_externa',e)
 def auxiliar(self,p):
  previo=dict(J.TIEMPO_MODELO.__dict__);J.TIEMPO_MODELO.__dict__.clear()
  self.addCleanup(lambda:(J.TIEMPO_MODELO.__dict__.clear(),J.TIEMPO_MODELO.__dict__.update(previo)))
  J.TIEMPO_MODELO.modelo='qwen3:8b';J.TIEMPO_MODELO.analisis_deepseek='SENAL_R6'
  with patch.object(J,'herramientas_para_turno',return_value=[]),patch.object(O,'solicitar',return_value={'message':{'role':'assistant','content':'OK'},'prompt_eval_count':20,'eval_count':1}) as enviar:
   J.enviar_a_ollama([{'role':'system','content':'Responde en español.'},{'role':'user','content':p}])
  mensajes=enviar.call_args.args[1]['messages']
  auxiliares=[m for m in mensajes if 'SENAL_R6' in m.get('content','')]
  self.assertEqual(len(auxiliares),1);self.assertEqual(auxiliares[0]['role'],'user')
  self.assertEqual(mensajes[-1]['content'],p,'El auxiliar no debe modificar la pregunta original')
  contenido=auxiliares[0]['content']
  self.assertIn(']\nSENAL_R6',contenido);self.assertNotIn(']\\nSENAL_R6',contenido)
 def test_ttl_de_sensores_vence_y_copia_no_contamina(self):
  reloj=[10.]
  with patch('cache_recursos.time.monotonic',side_effect=lambda:reloj[0]),patch.object(C.Path,'read_text',return_value='MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n') as leer:
   a=C.ram();a['total']=0;self.assertGreater(C.ram()['total'],0);self.assertEqual(leer.call_count,1)
   reloj[0]+=5;C.ram();self.assertEqual(leer.call_count,2)
 def test_digest_nuevo_remoto_no_reutiliza_acreditacion_local(self):
  O.invalidar_metadatos();fase=[1]
  def abrir(req,**kw):
   if req.full_url.endswith('tags'):d={'models':[{'name':'modelo:8b','digest':str(fase[0])}]}
   else:d=INFO if fase[0]==1 else {'remote_host':'https://externo.invalid','model_info':{}}
   return io.BytesIO(json.dumps(d).encode())
  with patch.object(O,'ABRIR',side_effect=abrir):
   O.solicitar('/api/tags');O.acreditar_pesos_locales('modelo:8b')
   fase[0]=2;O.solicitar('/api/tags')
   with self.assertRaisesRegex(O.ErrorOllama,'pesos locales'):O.acreditar_pesos_locales('modelo:8b')

for i,p in enumerate(['Explica una variable','Dime qué es una API','Explica Docker','Define un byte','Explica una función','Compara dos números','Explica SQL','Describe una clase','Dime qué es Kotlin','Explica un algoritmo'],1):setattr(Pruebas,f'test_auxiliar_{i:02}',lambda self,p=p:self.auxiliar(p))
if __name__=='__main__':unittest.main()
