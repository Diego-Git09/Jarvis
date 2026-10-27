"""No atribuir a Jarvis un servidor que ganó el puerto durante el arranque."""
import json,os,select,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from servicio_ollama import SesionOllama
from salud_ollama import comprobar
from soporte_pruebas_servicio import ejecutable,puerto_libre,esperar

class Pruebas(unittest.TestCase):
 def test_otro_servidor_gana_el_puerto_y_no_se_apaga_al_cerrar(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);url='http://127.0.0.1:'+str(puerto_libre())
   lento=root/'lento';lento.mkdir();rapido=root/'rapido';rapido.mkdir()
   lento_bin=ejecutable(lento,demora=1)
   rapido_bin=ejecutable(rapido)
   s=SesionOllama(url,raiz=root/'control',ejecutable=lento_bin,permitir_pruebas=True)
   resultado=[];h=threading.Thread(target=lambda:resultado.append(s.asegurar(timeout=4)));h.start()
   from servicio_ollama import leer_json
   self.assertTrue(esperar(lambda:bool((leer_json(s.raiz/'control.json') or {}).get('ollama_pid')),timeout=2))
   env=dict(os.environ,OLLAMA_HOST=url,HOME=str(root/'otro_hogar'))
   otro=subprocess.Popen([rapido_bin,'serve'],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
   try:
    self.assertTrue(esperar(lambda:comprobar(url,.1)['ok'],timeout=2))
    h.join(timeout=5);self.assertFalse(h.is_alive());self.assertTrue(resultado[0]['ok'],resultado)
    self.assertEqual(resultado[0]['gestion'],'preexistente')
    s.cerrar();time.sleep(.3);self.assertTrue(comprobar(url)['ok'])
   finally:
    s.cerrar()
    if otro.poll() is None:otro.terminate()
    otro.wait(timeout=3)
    p=getattr(s,'_supervisor',None)
    if p is not None:p.wait(timeout=5)
 def test_error_en_metadata_no_se_repite_como_texto_del_usuario(self):
  from unittest.mock import patch
  for codigo in ([],{},None,False,7,'dato-privado-ficticio',{'dato':'ejemplo'},['ejemplo'],'desconocido',''):
   with self.subTest(codigo=codigo),tempfile.TemporaryDirectory() as t:
    s=SesionOllama('http://127.0.0.1:23456',raiz=Path(t)/'control',permitir_pruebas=True)
    with patch.object(s,'_preparar',return_value={'gestion':'iniciado_por_jarvis'}),patch('servicio_ollama.leer_json',return_value={'estado':'error','error_codigo':codigo}):
     r=s.asegurar(timeout=.5)
    self.assertFalse(r['ok']);self.assertNotIn('dato-privado-ficticio',str(r));s.cerrar()

if __name__=='__main__':unittest.main()
