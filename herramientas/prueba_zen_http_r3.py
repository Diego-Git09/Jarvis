"""Proveedor simulado en loopback; ninguna llamada a Internet."""
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
import unittest
from unittest.mock import patch
import externo_zen as Z

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        self.server.identificacion=self.headers.get('User-Agent')
        self.server.metodo='GET'
        self.server.tamano_cuerpo=int(self.headers.get('Content-Length','0'))
        b=json.dumps({'data':[{'id':'modelo-ficticio'}]}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_POST(self):
        raw=self.rfile.read(int(self.headers['Content-Length']));d=json.loads(raw)
        self.server.recibido=d
        self.server.identificacion=self.headers.get('User-Agent')
        if d.get('model')=='error':self.send_response(429);self.end_headers();return
        if d.get('model')=='redirect':self.send_response(307);self.send_header('Location','https://otro.invalid/');self.end_headers();return
        if d.get('model') in {'cloudflare','denegado','error_largo','error_html'}:
            b=(json.dumps({'type':'https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/','detail':'CLAVE_FICTICIA reflejada por el servidor'}) if d['model']=='cloudflare' else 'CLAVE_FICTICIA '*4000 if d['model']=='error_largo' else '<html>CLAVE_FICTICIA</html>' if d['model']=='error_html' else json.dumps({'error':{'message':'CLAVE_FICTICIA saldo y pago supuestos'}})).encode()
            self.send_response(403);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
        b=json.dumps({'choices':[{'message':{'content':'Respuesta simulada'}}]}).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)

class Pruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.t=threading.Thread(target=cls.s.serve_forever,daemon=True);cls.t.start()
    @classmethod
    def tearDownClass(cls):cls.s.shutdown();cls.s.server_close();cls.t.join()
    def test_transporte_protocolo_con_servidor_local(self):
        with patch.object(Z,'ENDPOINT','http://127.0.0.1:'+str(self.s.server_port)):
            r=Z.transporte(Z.ENDPOINT,{'model':'simulado','messages':[{'role':'user','content':'Pregunta ficticia'}]},token='CLAVE_FICTICIA')
        self.assertIn('choices',r);self.assertNotIn('token',self.s.recibido)
        self.assertEqual(self.s.identificacion,'Jarvis/1.0')
    def test_catalogo_se_identifica_sin_enviar_conversacion(self):
        with patch.object(Z,'CATALOGO','http://127.0.0.1:'+str(self.s.server_port)):
            r=Z.transporte(Z.CATALOGO,token='CLAVE_FICTICIA')
        self.assertEqual(r,{'data':[{'id':'modelo-ficticio'}]})
        self.assertEqual(self.s.identificacion,'Jarvis/1.0')
        self.assertEqual(self.s.metodo,'GET');self.assertEqual(self.s.tamano_cuerpo,0)
    def test_403_cloudflare_explicado_sin_reflejar_cuerpo(self):
        with patch.object(Z,'ENDPOINT','http://127.0.0.1:'+str(self.s.server_port)),self.assertRaises(ConnectionError) as e:
            Z.transporte(Z.ENDPOINT,{'model':'cloudflare'},token='CLAVE_FICTICIA')
        t=str(e.exception)
        self.assertIn('HTTP 403',t);self.assertIn('Cloudflare',t);self.assertIn('1010',t)
        self.assertIn('no confirma',t);self.assertNotIn('CLAVE_FICTICIA',t)
    def test_403_desconocido_no_inventa_causa_ni_revela_datos(self):
        for modelo in ('denegado','error_largo','error_html'):
            with self.subTest(modelo=modelo),patch.object(Z,'ENDPOINT','http://127.0.0.1:'+str(self.s.server_port)),self.assertRaises(ConnectionError) as e:
                Z.transporte(Z.ENDPOINT,{'model':modelo},token='CLAVE_FICTICIA')
            self.assertEqual(str(e.exception),'Zen respondió HTTP 403.')
    def test_error_http_no_expone_el_cuerpo(self):
        with patch.object(Z,'ENDPOINT','http://127.0.0.1:'+str(self.s.server_port)),self.assertRaisesRegex(ConnectionError,'HTTP 429'):Z.transporte(Z.ENDPOINT,{'model':'error'},token='CLAVE_FICTICIA')
    def test_no_reenvia_clave_en_redireccion(self):
        with patch.object(Z,'ENDPOINT','http://127.0.0.1:'+str(self.s.server_port)),self.assertRaises(ConnectionError):Z.transporte(Z.ENDPOINT,{'model':'redirect'},token='CLAVE_FICTICIA')

if __name__=='__main__':unittest.main()
