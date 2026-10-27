"""Clientes independientes y caídas reales de procesos sintéticos locales."""
import json,os,select,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from salud_ollama import comprobar
from soporte_pruebas_servicio import ejecutable,puerto_libre,esperar

CLIENTE = """
import json,sys
from servicio_ollama import SesionOllama
s=SesionOllama(sys.argv[1],raiz=sys.argv[2],ejecutable=sys.argv[3],permitir_pruebas=True)
print(json.dumps(s.asegurar(timeout=5)),flush=True)
for linea in sys.stdin:
 if linea.strip()=='reiniciar':
  s._supervisor.kill();s._supervisor.wait(timeout=2)
  print(json.dumps(s.asegurar(timeout=5,forzar=True)),flush=True)
 elif linea.strip()=='cerrar':
  s.cerrar();print('cerrada',flush=True);break
s.cerrar()
"""

class Pruebas(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name)
  self.url='http://127.0.0.1:'+str(puerto_libre())
  self.bin=ejecutable(self.r);self.procesos=[]
 def tearDown(self):
  for p in self.procesos:
   if p.poll() is None:p.terminate()
   p.wait(timeout=3)
   for f in (p.stdin,p.stdout,p.stderr):
    if f:f.close()
  esperar(lambda:not comprobar(self.url,.1)['ok'],timeout=5)
  self.tmp.cleanup()
 def lanzar(self):
  env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent),JARVIS_PRUEBAS='1')
  p=subprocess.Popen([sys.executable,'-B','-c',CLIENTE,self.url,str(self.r/'control'),self.bin],
                     stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  self.procesos.append(p);return p
 def leer(self,p):
  self.assertTrue(select.select([p.stdout],[],[],7)[0],'El cliente no contestó dentro del plazo')
  raw=p.stdout.readline()
  if not raw:raise AssertionError('Cliente terminó: '+p.stderr.read()[:1000])
  return raw.strip()
 def listo(self,p):self.assertTrue(json.loads(self.leer(p))['ok'])
 def cerrar(self,p):
  p.stdin.write('cerrar\n');p.stdin.flush();self.assertEqual(self.leer(p),'cerrada');p.wait(timeout=3)
 def test_clientes_independientes_preservan_el_servidor_compartido(self):
  a=self.lanzar();self.listo(a);b=self.lanzar();self.listo(b)
  self.cerrar(a);time.sleep(.3);self.assertTrue(comprobar(self.url)['ok'])
  self.cerrar(b);self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_caida_del_primer_cliente_no_apaga_al_segundo(self):
  a=self.lanzar();self.listo(a);b=self.lanzar();self.listo(b)
  a.kill();a.wait(timeout=2);time.sleep(.3);self.assertTrue(comprobar(self.url)['ok'])
  self.cerrar(b);self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_caida_del_unico_cliente_no_deja_servidor_huerfano(self):
  a=self.lanzar();self.listo(a);a.kill();a.wait(timeout=2)
  self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_cinco_arranques_concurrentes_comparten_un_solo_control(self):
  procesos=[self.lanzar() for _ in range(5)]
  for p in procesos:self.listo(p)
  d=json.loads((self.r/'control/control.json').read_text());pid=d['ollama_pid']
  for p in procesos[:-1]:self.cerrar(p)
  self.assertTrue(comprobar(self.url)['ok'])
  self.assertEqual(json.loads((self.r/'control/control.json').read_text())['ollama_pid'],pid)
  self.cerrar(procesos[-1]);self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_supervisor_que_muere_termina_su_hijo_y_se_recupera(self):
  a=self.lanzar();self.listo(a)
  primero=json.loads((self.r/'control/control.json').read_text())['ollama_pid']
  a.stdin.write('reiniciar\n');a.stdin.flush();self.listo(a)
  segundo=json.loads((self.r/'control/control.json').read_text())['ollama_pid']
  self.assertNotEqual(primero,segundo);self.assertTrue(comprobar(self.url)['ok'])
  self.cerrar(a);self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_arranque_nuevo_durante_cierre_anterior(self):
  for i in range(8):
   with self.subTest(ciclo=i):
    a=self.lanzar();self.listo(a)
    a.stdin.write('cerrar\n');a.stdin.flush()
    b=self.lanzar();self.listo(b)
    self.assertEqual(self.leer(a),'cerrada');a.wait(timeout=3)
    self.assertTrue(comprobar(self.url)['ok'])
    self.cerrar(b);self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))

if __name__=='__main__':unittest.main()
