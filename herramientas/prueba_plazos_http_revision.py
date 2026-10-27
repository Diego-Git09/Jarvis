"""Servidor que gotea bytes: el plazo local no se renueva con cada fragmento."""
import json,threading,time,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
import cliente_ollama as O
import salud_ollama as S

class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  self.send_response(200);self.end_headers()
  try:
   for b in b'{"version":"sintetica"}':
    self.wfile.write(bytes([b]));self.wfile.flush();time.sleep(.08)
  except (BrokenPipeError,ConnectionResetError):pass
 do_POST=do_GET

class Pruebas(unittest.TestCase):
 def setUp(self):
  self.server=ThreadingHTTPServer(('127.0.0.1',0),H)
  self.t=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.03},daemon=True);self.t.start()
  self.url='http://127.0.0.1:'+str(self.server.server_address[1])
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.t.join(timeout=1)
 def test_sondeo_no_espera_todo_el_goteo(self):
  inicio=time.monotonic();r=S.comprobar(self.url,timeout=.2)
  self.assertFalse(r['ok']);self.assertEqual(r['tipo'],'timeout')
  self.assertLess(time.monotonic()-inicio,.7)
 def test_cliente_respeta_plazo_de_cuerpo_y_no_reintenta(self):
  inicio=time.monotonic()
  with patch.object(O,'BASE',self.url),self.assertRaises(O.ErrorOllama) as fallo:
   O.solicitar('/api/version',timeout=.2)
  self.assertEqual(fallo.exception.tipo,'timeout');self.assertLess(time.monotonic()-inicio,.7)
 def test_streaming_no_espera_un_salto_de_linea_fuera_del_plazo(self):
  inicio=time.monotonic()
  with patch.object(O,'BASE',self.url),self.assertRaises(O.ErrorOllama) as fallo:
   with O.abrir_flujo_chat({},timeout=.2) as lineas:list(lineas)
  self.assertEqual(fallo.exception.tipo,'timeout');self.assertLess(time.monotonic()-inicio,.7)

if __name__=='__main__':unittest.main()
