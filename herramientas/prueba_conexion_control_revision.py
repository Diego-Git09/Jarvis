"""Caída del servidor, cierre de ventanas y permiso: conservar el turno y no repetir."""
import io,queue,threading,unittest,urllib.error
from unittest.mock import patch,Mock
import cliente_ollama as O
import configuracion_jarvis as C
import jarvis_agente as J
from interfaz_grafica import Aplicacion

class Pruebas(unittest.TestCase):
 def test_rechazo_identifica_servidor_sin_culpar_modelo(self):
  e=O._error(urllib.error.URLError(ConnectionRefusedError(111,'sintético')))
  self.assertTrue(getattr(e,'servicio',False))
 def test_http_error_cierra_cuerpo_tambien_al_traducir(self):
  cuerpo=io.BytesIO(b'{"error":"sintetico"}')
  e=urllib.error.HTTPError('http://127.0.0.1:23456',503,'sintetico',{},cuerpo)
  O._error(e)
  self.assertTrue(cuerpo.closed)
 def test_no_prueba_otro_modelo_cuando_el_servidor_esta_caido(self):
  error=O._error(urllib.error.URLError(ConnectionRefusedError(111,'sintético')))
  h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':'Explica una API'}]
  with patch.object(J,'ejecutar_turno',side_effect=error) as motor,patch.object(O,'modelos',return_value=[C.MODELO_COTIDIANO,C.MODELO_PREDETERMINADO]) as modelos:
   texto=J.responder_con_respaldo(h,None,lambda _:False,{},mostrar=lambda _:None)
  motor.assert_called_once();modelos.assert_not_called()
  self.assertIn('servidor',texto.casefold());self.assertIn('reintenta',texto)
  self.assertEqual([m['content'] for m in h if m['role']=='user'],['Explica una API'])
 def test_autoinicio_activo_por_defecto_y_validado(self):
  self.assertIs(C.validar({}).get('autoinicio_ollama'),True)
  for valor in ('si',1,None,[]):
   with self.subTest(valor=valor),self.assertRaises(ValueError):C.validar({'autoinicio_ollama':valor})
 def test_permiso_pendiente_no_cuelga_tras_cerrar(self):
  app=Aplicacion.__new__(Aplicacion);app._cerrando=threading.Event();app.confirmaciones=queue.Queue()
  salida=[];h=threading.Thread(target=lambda:salida.append(app._pedir_permiso('Cambio sintético')),daemon=True)
  h.start();texto,hecho,r=app.confirmaciones.get(timeout=1)
  app._cerrando.set();h.join(timeout=.4)
  try:
   self.assertFalse(h.is_alive());self.assertEqual(salida,[False])
  finally:hecho.set();h.join(timeout=1)
 def test_permiso_real_sigue_respetando_resultado(self):
  app=Aplicacion.__new__(Aplicacion);app._cerrando=threading.Event();app.confirmaciones=queue.Queue()
  salida=[];h=threading.Thread(target=lambda:salida.append(app._pedir_permiso('Cambio sintético')),daemon=True)
  h.start();_,hecho,r=app.confirmaciones.get(timeout=1)
  r['ok']=True;hecho.set();h.join(timeout=1)
  self.assertEqual(salida,[True])

if __name__=='__main__':unittest.main()
