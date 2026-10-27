"""Arranque y cierre con procesos y HTTP sintéticos reales, sin el Ollama del usuario."""
import json,os,stat,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from servicio_ollama import SesionOllama,identidad,vivo,leer_json
from salud_ollama import comprobar
from soporte_pruebas_servicio import ejecutable,puerto_libre,esperar

class Pruebas(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.url='http://127.0.0.1:'+str(puerto_libre());self.sesiones=[]
 def tearDown(self):
  for s in self.sesiones:s.cerrar()
  for s in self.sesiones:
   p=getattr(s,'_supervisor',None)
   if p is not None:
    try:p.wait(timeout=6)
    except Exception:
     p.terminate();p.wait(timeout=2)
  self.tmp.cleanup()
 def sesion(self,**kw):
  s=SesionOllama(self.url,raiz=self.root/'control',ejecutable=kw.pop('ejecutable',None) or ejecutable(self.root),permitir_pruebas=True,**kw)
  self.sesiones.append(s);return s
 def test_apagado_inicia_y_ultimo_cierre_detiene_su_proceso(self):
  s=self.sesion();r=s.asegurar(timeout=4)
  self.assertTrue(r['ok'],r);self.assertEqual(r['gestion'],'iniciado_por_jarvis')
  self.assertTrue(comprobar(self.url)['ok'])
  s.cerrar()
  self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_segunda_sesion_conserva_servidor_hasta_ultimo_cierre(self):
  a=self.sesion();self.assertTrue(a.asegurar(4)['ok'])
  b=self.sesion();self.assertTrue(b.asegurar(4)['ok'])
  a.cerrar();time.sleep(.4);self.assertTrue(comprobar(self.url)['ok'])
  b.cerrar();self.assertTrue(esperar(lambda:not comprobar(self.url,.1)['ok']))
 def test_preexistente_no_se_toca_al_cerrar(self):
  original=self.sesion();self.assertTrue(original.asegurar(4)['ok'])
  otra=SesionOllama(self.url,raiz=self.root/'otra',ejecutable='/no-existe',permitir_pruebas=True)
  self.sesiones.append(otra)
  r=otra.asegurar(2);self.assertTrue(r['ok']);self.assertEqual(r['gestion'],'preexistente')
  otra.cerrar();time.sleep(.3);self.assertTrue(comprobar(self.url)['ok'])
 def test_no_hereda_secretos_ni_habilita_nube(self):
  s=self.sesion()
  with patch.dict(os.environ,{'SECRET_LAB':'SENTINELA_FICTICIA'}):r=s.asegurar(4)
  self.assertTrue(r['ok'],r)
  d=json.loads((s.raiz/'hogar/arranque.json').read_text())
  self.assertFalse(d['secretos_presentes']);self.assertEqual(d['cloud'],'1');self.assertEqual(d['host'],'127.0.0.1')
 def test_ejecutable_ausente_da_error_sin_instalar(self):
  s=self.sesion(ejecutable='/no-existe')
  r=s.asegurar(1);self.assertFalse(r['ok']);self.assertEqual(r['tipo'],'no_instalado')
  self.assertFalse(list(s.raiz.glob('cliente-*.json')))
 def test_proceso_que_falla_no_se_confunde_con_listo(self):
  s=self.sesion(ejecutable=ejecutable(self.root,fallar=True))
  r=s.asegurar(2);self.assertFalse(r['ok']);self.assertNotEqual(r['tipo'],'disponible')
 def test_cierre_mientras_arranca_es_acotado(self):
  s=self.sesion(ejecutable=ejecutable(self.root,demora=2))
  resultados=[];h=threading.Thread(target=lambda:resultados.append(s.asegurar(4)))
  h.start();time.sleep(.2);inicio=time.monotonic();s.cerrar();h.join(timeout=2)
  self.assertFalse(h.is_alive());self.assertLess(time.monotonic()-inicio,1)
  self.assertFalse(resultados[0]['ok'])
 def test_no_arranca_sobre_timeout_o_otro_error_http(self):
  for tipo in ('timeout','http','respuesta','conexion'):
   s=self.sesion()
   with self.subTest(tipo=tipo),patch('servicio_ollama.comprobar',return_value={'ok':False,'tipo':tipo,'error':'sintético'}),patch('servicio_ollama.subprocess.Popen') as iniciar:
    self.assertFalse(s.asegurar(1)['ok']);iniciar.assert_not_called()
 def test_no_se_activa_silenciosamente_en_pruebas(self):
  s=SesionOllama(self.url,raiz=self.root/'deshabilitado');self.sesiones.append(s)
  with patch('servicio_ollama.subprocess.Popen') as iniciar:
   self.assertEqual(s.asegurar()['tipo'],'prueba');iniciar.assert_not_called()
 def test_sesion_cerrada_no_reinicia(self):
  s=self.sesion();s.cerrar()
  with patch('servicio_ollama.subprocess.Popen') as iniciar:
   self.assertEqual(s.asegurar()['tipo'],'cerrada');iniciar.assert_not_called()
 def test_identidad_no_acepta_pid_reutilizado(self):
  self.assertTrue(vivo({'pid':os.getpid(),'nacimiento':identidad(os.getpid())}))
  self.assertFalse(vivo({'pid':os.getpid(),'nacimiento':'equivocado'}))
 def test_control_privado_y_sin_enlaces(self):
  s=self.sesion();self.assertTrue(s.asegurar(4)['ok'])
  self.assertEqual(stat.S_IMODE(s.raiz.stat().st_mode),0o700)
  for p in s.raiz.glob('*.json'):self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o600)
  otro=self.root/'enlace';otro.symlink_to(s.raiz,target_is_directory=True)
  with self.assertRaises(ValueError):
   SesionOllama(self.url,raiz=otro,permitir_pruebas=True)._asegurar(1)
 def test_fifo_no_bloquea_lectura_de_control(self):
  f=self.root/'fifo';os.mkfifo(f,0o600)
  with self.assertRaises(ValueError):leer_json(f)
 def test_limite_y_permisos_del_control(self):
  f=self.root/'meta.json';f.write_text('{}')
  with self.assertRaises(ValueError):leer_json(f)
  f.chmod(0o600);self.assertEqual(leer_json(f),{})
  f.write_text('x'*20000)
  with self.assertRaises(ValueError):leer_json(f)

if __name__=='__main__':unittest.main()
