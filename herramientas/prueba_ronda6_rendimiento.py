"""Cachés y reintentos con transporte y sensores simulados; sin cargas de modelos."""
import io,json,socket,unittest,urllib.error
from unittest.mock import patch,Mock
import cliente_ollama as O
import control_recursos as C
import recursos_ollama as R
import presupuesto_contexto as P
from prueba_control_recursos import INFO,foto

class Pruebas(unittest.TestCase):
 def setUp(self):
  self.addCleanup(patch.stopall)
  if hasattr(O,'invalidar_metadatos'):O.invalidar_metadatos()
 def sin_reintentar_timeout(self,i):
  with patch.object(O,'ABRIR',side_effect=socket.timeout('plazo simulado '+str(i))) as abrir,self.assertRaises(O.ErrorOllama):
   try:O.solicitar('/api/chat',{},timeout=.1)
   finally:self.assertEqual(abrir.call_count,1)
 def test_429_json_y_respuesta_vacia_no_reintentan(self):
  for fallo in [urllib.error.HTTPError('http://127.0.0.1/',429,'limitado',{},io.BytesIO(b'{}')),ValueError('JSON'),O.ErrorOllama('sin respuesta',tipo='vacia',reintentable=True)]:
   with self.subTest(tipo=type(fallo).__name__),patch.object(O,'ABRIR',side_effect=fallo) as abrir,self.assertRaises(O.ErrorOllama):
    try:O.solicitar('/api/chat',{},timeout=.1)
    finally:self.assertEqual(abrir.call_count,1)
 def test_conexion_y_5xx_conservan_un_solo_reintento(self):
  for error in [ConnectionRefusedError(),urllib.error.HTTPError('http://127.0.0.1/',503,'ocupado',{},io.BytesIO(b'{}'))]:
   with self.subTest(tipo=type(error).__name__),patch.object(O,'ABRIR',side_effect=[error,io.BytesIO(b'{"message":{"content":"OK"}}')]) as abrir:
    self.assertEqual(O.solicitar('/api/chat',{},timeout=1)['message']['content'],'OK');self.assertEqual(abrir.call_count,2)
 def test_show_cacheado_y_digest_invalida(self):
  llamadas=[];digest=['uno']
  def abrir(req,**kw):
   ruta=req.full_url.rsplit('/',1)[-1];llamadas.append(ruta)
   d={'models':[{'name':'modelo:8b','digest':digest[0]}]} if ruta=='tags' else INFO
   return io.BytesIO(json.dumps(d).encode())
  with patch.object(O,'ABRIR',side_effect=abrir):
   O.solicitar('/api/tags')
   for _ in range(3):O.acreditar_pesos_locales('modelo:8b')
   self.assertEqual(llamadas.count('show'),1)
   digest[0]='dos';O.solicitar('/api/tags');O.acreditar_pesos_locales('modelo:8b')
   self.assertEqual(llamadas.count('show'),2)
 def test_cache_devuelve_copias_no_mutables_del_original(self):
  def abrir(req,**kw):return io.BytesIO(json.dumps({'models':[{'name':'modelo:8b','digest':'uno'}]} if req.full_url.endswith('tags') else INFO).encode())
  with patch.object(O,'ABRIR',side_effect=abrir) as red:
   O.solicitar('/api/tags');d=O.acreditar_pesos_locales('modelo:8b');d['model_info'].clear()
   self.assertTrue(O.acreditar_pesos_locales('modelo:8b')['model_info']);self.assertEqual(red.call_count,2)
 def test_ram_y_gpu_con_ttl(self):
  with patch.object(C.Path,'read_text',return_value='MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n') as leer:
   C.ram();C.ram();self.assertEqual(leer.call_count,1)
  with patch.object(R.subprocess,'run',return_value=Mock(returncode=0,stdout='8192, 0, 8192, 0')) as correr:
   R.gpu();R.gpu();self.assertEqual(correr.call_count,1)
 def test_termica_y_procesos_con_ttl(self):
  def ejecutar(cmd,**kw):return Mock(returncode=0,stdout='{}' if cmd[0]=='sensors' else '8192, 0, 8192, 0, 40, 115, 10' if len(cmd)>1 else '')
  with patch.object(C.subprocess,'run',side_effect=ejecutar) as correr,patch.object(C.Path,'glob',return_value=[]):
   C.termica();C.termica();self.assertEqual(correr.call_count,2)
   correr.reset_mock();C.procesos();C.procesos();self.assertEqual(correr.call_count,2)
 def test_steam_inactivo_no_bloquea_pero_carga_real_si(self):
  for nombre in ['steam','lutris','wine','wine64','wineserver','steam_app1','steam_app2','Steam','Lutris','wine-juego']:
   f=foto();f['juegos']=[nombre];f['gpu']['gpu'][0]['uso_porcentaje']=2
   with self.subTest(nombre=nombre):
    self.assertTrue(C.evaluar(f,C.estimar(INFO,{},5200000000))['permitido'])
    f['gpu']['gpu'][0]['uso_porcentaje']=95
    self.assertFalse(C.evaluar(f,C.estimar(INFO,{},5200000000))['permitido'])
 def test_calibracion_p90_con_margen_no_mediana(self):
  e={}
  for real in [1000,1000,1000,1000,1800]:
   c={'entrada_tokens_estimados':1000};P.calibrar(e,'modelo',c,real)
  self.assertGreaterEqual(c['entrada_calibrada_tokens'],1800)
  self.assertEqual(P.BYTES_POR_TOKEN,2.5,'El coeficiente global solo se propone, no se cambia sin revisión')
 def test_referencia_auxiliar_contiene_salto_real(self):
  import ast
  from pathlib import Path
  literales=[n.value for n in ast.walk(ast.parse(Path(O.__file__).with_name('jarvis_agente.py').read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'Puede contener errores.]' in n.value]
  self.assertTrue(literales);self.assertTrue(all(']\\n' not in s and ']\n' in s for s in literales))

for i in range(10):setattr(Pruebas,f'test_timeout_{i:02}',lambda self,i=i:self.sin_reintentar_timeout(i))
if __name__=='__main__':unittest.main()
