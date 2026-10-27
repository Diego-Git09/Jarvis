"""Orden real de Diego contra HTTP MCP temporal; ningún recuerdo real.

Se prueba el transporte sin sustituir ClienteCerebro ni el despacho que usan
la terminal y la GUI. El almacenamiento y los cortes de red son sintéticos.
"""
import copy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from cerebro_mcp import ClienteCerebro,ErrorCerebro
import hilo_conversacion as H
import interfaz_jarvis as I
import memoria_explicita as M

PEDIDO='''Guarda un único recuerdo en Segundo Cerebro, proyecto existente **Jarvis**.

**Título:** Integración DeepSeek + Qwen + MCP — 15/10/2026

**Contenido:**

Se integró DeepSeek R1 8B como auxiliar automático de Qwen3:8b en Jarvis mediante Ollama local.

Archivos nuevos: `enrutador_modelos.py`, `auxiliar_deepseek.py`, `coordinador_deepseek.py`, `control_deepseek.py` y `resumen_estado_mcp.py`.

Se actualizó `jarvis_agente.py` para incorporar el análisis auxiliar, separar los mensajes y limpiar el contexto temporal. DeepSeek se habilita con `JARVIS_DEEPSEEK=1`.

Se corrigió el exceso de contexto MCP reduciendo la respuesta de estado de 3510 a 689 caracteres. Segundo Cerebro volvió a funcionar correctamente.

Se desactivó el respaldo automático de Gemini mediante `guardar_opciones(False, timeout_local=35)`.

Pruebas: Qwen respondió consultas complejas en aproximadamente 27–28 segundos; MCP respondió correctamente; se revisaron las protecciones de escritura.

Estado: integración funcional, con pruebas adicionales de seguridad y rendimiento pendientes.

Solicita autorización antes de guardar y confirma el ID creado.'''


class Servidor(BaseHTTPRequestHandler):
    def log_message(self,*args):pass

    def do_POST(self):
        d=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.llamadas.append(copy.deepcopy(d))
        metodo=d['method']
        if metodo=='notifications/initialized':
            self.send_response(202);self.end_headers();return
        if metodo=='initialize':r={'protocolVersion':'2025-06-18'}
        else:
            n=d['params']['name'];a=d['params']['arguments']
            if n=='listar_proyectos':valor={'proyectos':[{'proyecto':'Jarvis'}]}
            elif n=='listar_memorias':
                valor=copy.deepcopy(self.server.filas[a['desplazamiento']:a['desplazamiento']+a['limite']])
                for m in valor:m['contenido']=m['contenido'][:1600]
            elif n=='consultar_memoria':
                valor={'memorias':[copy.deepcopy(x) for x in self.server.filas if x['id']==a['id_memoria']]}
                if self.server.lectura_erronea and valor['memorias']:valor['memorias'][0]['contenido']='Respuesta truncada sintética'
            elif n=='guardar_memoria':
                ident=max([x['id'] for x in self.server.filas],default=0)+1
                self.server.filas.append(dict(a,id=ident,tipo='recuerdo'))
                if self.server.cortar:
                    self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
                if self.server.texto_resultado:
                    r={'content':[{'type':'text','text':json.dumps(f'Memoria guardada. ID: {ident}')}]}
                else:r={'structuredContent':{'result':f'Memoria guardada. ID: {ident}'}}
            else:raise AssertionError('Herramienta inesperada: '+n)
            if n!='guardar_memoria':r={'structuredContent':{'result':valor}}
        raw=json.dumps({'jsonrpc':'2.0','id':d['id'],'result':r},ensure_ascii=False)
        body=('event: message\ndata: '+raw+'\n\n').encode() if self.server.sse else raw.encode()
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream' if self.server.sse else 'application/json')
        if metodo=='initialize':self.send_header('Mcp-Session-Id','recuerdo-sintetico')
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)


class Pruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Servidor);cls.server.daemon_threads=True
        cls.hilo=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.hilo.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.hilo.join(2)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name);self.addCleanup(patch.stopall)
        patch.object(M,'CARPETA',self.raiz/'recibos').start();patch.object(H,'CARPETA',self.raiz/'hilos').start()
        self.server.llamadas=[];self.server.filas=[];self.server.sse=True
        self.server.cortar=False;self.server.lectura_erronea=False;self.server.texto_resultado=False
        self.cliente=self.nuevo_cliente();self.dato=M.interpretar(PEDIDO)

    def nuevo_cliente(self):return ClienteCerebro(f'http://127.0.0.1:{self.server.server_port}/mcp',timeout=2)

    def envios(self):return [x for x in self.server.llamadas if x.get('params',{}).get('name')=='guardar_memoria']

    def test_transcripcion_completa_y_nuevo_usan_ruta_directa_con_permiso(self):
        h=[{'role':'system','content':'Reglas '*10000},{'role':'user','content':'Anterior'}]
        estado={'_memorias':{99:'Referencia antigua'}};vistos=[]
        def confirmar(t):
            self.assertFalse(self.envios());vistos.append(t);return True
        local=lambda p,h,e:M.comando(p,self.cliente,confirmar,e)
        ok,texto=I.comando('/nuevo '+PEDIDO,h,estado,lambda *_:self.fail('No modelo ni herramientas'),h[0]['content'],local)
        self.assertTrue(ok);self.assertIn('ID creado: 1',texto);self.assertEqual(len(vistos),1)
        self.assertEqual(self.envios()[0]['params']['arguments'],self.dato)
        self.assertNotIn('Solicita autorización',self.server.filas[0]['contenido'])
        self.assertNotIn('_memorias',estado);self.assertNotIn('Anterior',str(h))
        self.assertEqual(self.server.llamadas[-1]['params']['name'],'consultar_memoria')

    def test_denegacion_no_guarda_ni_deja_recibo_incierto(self):
        t=M.guardar(self.cliente,self.dato,lambda _:False)
        self.assertIn('No autorizaste',t);self.assertFalse(self.envios());self.assertFalse(self.server.filas)
        self.assertEqual(list(M.CARPETA.glob('*.json')),[])

    def test_json_y_texto_mcp_sin_structured_content(self):
        self.server.sse=False;self.server.texto_resultado=True
        self.assertIn('ID creado: 1',M.guardar(self.cliente,self.dato,lambda _:True))
        self.assertEqual(len(self.envios()),1)

    def test_corte_despues_de_insertar_y_nuevo_cliente_no_duplican(self):
        self.server.cortar=True
        with self.assertRaises(ErrorCerebro):M.guardar(self.cliente,self.dato,lambda _:True)
        self.assertEqual(len(self.server.filas),1);self.assertEqual(len(list(M.CARPETA.glob('*.json'))),1)
        self.server.cortar=False
        t=M.guardar(self.nuevo_cliente(),self.dato,lambda _:self.fail('La lectura debe resolver el guardado'))
        self.assertIn('ID: 1',t);self.assertEqual(len(self.envios()),1);self.assertEqual(list(M.CARPETA.glob('*.json')),[])

    def test_lectura_incompleta_nunca_anuncia_guardado_comprobado(self):
        self.server.lectura_erronea=True
        with self.assertRaisesRegex(ErrorCerebro,'No pude comprobar'):M.guardar(self.cliente,self.dato,lambda _:True)
        with self.assertRaises(ErrorCerebro):M.guardar(self.nuevo_cliente(),self.dato,lambda _:self.fail('No repetir'))
        self.assertEqual(len(self.envios()),1);self.assertEqual(len(list(M.CARPETA.glob('*.json'))),1)

    def test_dos_paginas_y_contenido_largo_se_consultan_por_id(self):
        self.dato=dict(self.dato,contenido=('TEXTO_LITERAL_73\n'*300).strip())
        self.server.filas=[dict(self.dato,id=1,tipo='recuerdo')]+[
            dict(self.dato,id=100+i,titulo=f'Conversación {i}',tipo='conversacion') for i in range(120)]
        t=M.guardar(self.cliente,self.dato,lambda _:self.fail('Ya existe'))
        self.assertIn('ID: 1',t);self.assertFalse(self.envios())
        paginas=[x['params']['arguments']['desplazamiento'] for x in self.server.llamadas if x.get('params',{}).get('name')=='listar_memorias']
        self.assertEqual(paginas,[0,100]);self.assertEqual(self.server.llamadas[-1]['params']['name'],'consultar_memoria')

    def test_recibo_previo_a_envio_requiere_permiso_y_marca_persistida(self):
        def no_se_pudo_marcar():raise OSError('Disco sintético no disponible')
        with self.assertRaises(OSError):M.guardar(self.cliente,self.dato,lambda _:True,no_se_pudo_marcar)
        self.assertFalse(self.envios());self.assertFalse(self.server.filas)


if __name__=='__main__':unittest.main()
