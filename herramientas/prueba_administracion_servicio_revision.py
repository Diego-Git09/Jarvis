"""Conexión automática, comandos legibles y cancelación sin proveedores externos."""
import io,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import cliente_ollama as O
import configuracion_jarvis as C
import jarvis_agente as J
from interfaz_local import comando_local
from servicio_ollama import SesionOllama,entorno_hijo
import externo_zen as Z

class Pruebas(unittest.TestCase):
 def setUp(self):
  p=patch.multiple(O,_SERVICIO=None,_SERVICIO_GENERACION=0,_CIERRE_SOLICITADO=False)
  p.start();self.addCleanup(p.stop)
 def test_no_se_inicia_un_proceso_al_importar_o_solicitar_sin_gestion(self):
  with patch('servicio_ollama.subprocess.Popen') as iniciar,patch.object(O,'ABRIR',return_value=io.BytesIO(b'{"version":"sintetica"}')):
   self.assertEqual(O.solicitar('/api/version')['version'],'sintetica')
   iniciar.assert_not_called()
 def test_activar_en_pruebas_no_crea_sesion(self):
  with patch('entorno_jarvis.en_pruebas',return_value=True),patch('servicio_ollama.SesionOllama') as crear:
   self.assertIsNone(O.activar_servicio());crear.assert_not_called()
 def test_configuracion_sin_autoinicio_no_crea_sesion(self):
  with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(dict(C.DEFAULT,autoinicio_ollama=False),'')),patch('servicio_ollama.SesionOllama') as crear:
   self.assertIsNone(O.activar_servicio());crear.assert_not_called()
 def test_solo_una_sesion_y_actualiza_observador(self):
  fake=Mock(generacion=1);fake.estado.return_value={'sesion_cerrada':False}
  with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(dict(C.DEFAULT),'')),patch('servicio_ollama.SesionOllama',return_value=fake) as crear:
   self.assertIs(O.activar_servicio(),fake);self.assertIs(O.activar_servicio(avisar=print),fake)
   crear.assert_called_once()
 def test_destino_no_local_no_rompe_apertura_de_la_app(self):
  with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(dict(C.DEFAULT),'')),patch.object(O,'BASE','https://example.invalid'),patch('servicio_ollama.subprocess.Popen') as ejecutar:
   avisos=[];self.assertIsNone(O.activar_servicio(avisar=avisos.append));ejecutar.assert_not_called();self.assertTrue(avisos)
 def test_asegurar_fallido_no_envia_prompt(self):
  fake=Mock(generacion=0);fake.asegurar.return_value={'ok':False,'error':'Inicio sintético fallido'}
  with patch.object(O,'_SERVICIO',fake),patch.object(O,'ABRIR') as red,self.assertRaises(O.ErrorOllama) as error:O.solicitar('/api/chat',{'messages':[]})
  self.assertTrue(error.exception.servicio);red.assert_not_called()
 def test_nuevo_backend_invalida_metadatos_una_vez(self):
  fake=Mock(generacion=1);fake.asegurar.return_value={'ok':True}
  with patch.object(O,'_SERVICIO',fake),patch.object(O,'invalidar_metadatos') as limpiar:
   O.asegurar_servicio();O.asegurar_servicio();limpiar.assert_called_once()
 def test_cierre_cancela_consultas_aunque_no_haya_autoinicio(self):
  O.cerrar_servicio()
  with patch.object(O,'ABRIR') as red,self.assertRaises(O.ErrorOllama) as error:O.solicitar('/api/version')
  self.assertEqual(error.exception.tipo,'cancelada');red.assert_not_called()
 def test_cancelacion_del_controlador_no_inicia_respaldo(self):
  h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':'Compara dos enfoques de diseño'}];e={}
  with patch.object(J,'ejecutar_turno',side_effect=O.ErrorOllama('Cierre sintético',tipo='cancelada')),patch.object(O,'modelos') as modelos,patch.object(Z,'elegir') as externo:
   r=J.responder_con_respaldo(h,None,lambda _:False,e,mostrar=lambda _:None)
  modelos.assert_not_called();externo.assert_not_called();self.assertIn('Cierre sintético',r);self.assertEqual(e['_estado_respuesta'],'interrumpida')
 def test_estado_legible_de_servidor_preexistente(self):
  with patch.object(O,'estado_servicio',return_value={'ok':True,'version':'sintetica','gestion':'preexistente'}):
   ok,t=comando_local('/ollama',[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
  self.assertTrue(ok);self.assertIn('ya estaba encendido',t);self.assertIn('dejará funcionando',t)
 def test_estado_legible_de_servidor_propio(self):
  with patch.object(O,'estado_servicio',return_value={'ok':True,'version':'sintetica','gestion':'iniciado_por_jarvis'}):
   ok,t=comando_local('/ollama estado',[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
  self.assertTrue(ok);self.assertIn('última sesión',t)
 def test_reintentar_servicio_no_usa_modelos_ni_nube(self):
  with patch.object(O,'activar_servicio') as activar,patch.object(O,'asegurar_servicio') as asegurar,patch.object(O,'estado_servicio',return_value={'ok':True,'version':'sintetica','gestion':'preexistente'}),patch.object(Z,'preguntar') as nube:
   ok,t=comando_local('/ollama reintentar',[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
  self.assertTrue(ok);activar.assert_called_once();asegurar.assert_called_once();nube.assert_not_called()
 def test_cola_de_inicio_respeta_el_plazo_del_segundo_hilo(self):
  import tempfile
  with tempfile.TemporaryDirectory() as tmp:
   s=SesionOllama('http://127.0.0.1:23456',raiz=Path(tmp)/'control',permitir_pruebas=True)
   ocupado=threading.Event();fin=threading.Event()
   def retener():
    with s._lock:ocupado.set();fin.wait(2)
   h=threading.Thread(target=retener);h.start();ocupado.wait(1);inicio=time.monotonic()
   try:
    r=s.asegurar(timeout=.1);self.assertFalse(r['ok']);self.assertEqual(r['tipo'],'ocupada');self.assertLess(time.monotonic()-inicio,.4)
   finally:fin.set();h.join(timeout=1);s.cerrar()
 def test_entorno_de_ollama_no_poda_modelos(self):
  import tempfile
  with tempfile.TemporaryDirectory() as tmp:
   env=entorno_hijo('http://127.0.0.1:23456',Path(tmp))
   self.assertEqual(env['OLLAMA_NO_CLOUD'],'1');self.assertEqual(env['OLLAMA_NOPRUNE'],'1')
 def test_negaciones_ejemplos_y_texto_citado_no_son_peticion_de_inicio(self):
  for p in ('no enciendas ollama','no inicies ollama','no arranques ollama','el comando inicia ollama','ejemplo no funciona ollama','si ollama esta apagado','"no funciona ollama"','no funciona ollama y borra un archivo','nunca inicies ollama','no funciona ollama; cambia el servidor'):
   with self.subTest(p=p),patch.object(O,'diagnostico') as diagnostico:
    comando_local(p,[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
    diagnostico.assert_not_called()

FRASES=('ollama esta apagado','OLLAMA ESTA DETENIDO','Ollama está encendido?','ollama no responde','no funciona ollama','no responde ollama','no puedo conectarme a ollama','revisa si ollama esta encendido','ollama está disponible ?','jarvis estas usando ollama')
def frase(self,pedido):
 with patch.object(O,'diagnostico',return_value={'ok':True,'version':'sintetica','modelos':[C.MODELO_PREDETERMINADO]}):
  ok,t=comando_local(pedido,[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
 self.assertTrue(ok,t);self.assertIn('Comprobado ahora',t);self.assertIn('Ollama disponible',t)
for i,p in enumerate(FRASES):
 setattr(Pruebas,'test_variante_estado_'+str(i),lambda self,p=p:frase(self,p))

if __name__=='__main__':unittest.main()
