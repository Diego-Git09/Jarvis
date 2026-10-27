"""Pruebas aisladas: servidor MCP falso; nunca modifica recuerdos reales."""
import io
import json
import threading
import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
from control_clasificacion import clasificar, consultar, crear_proyecto, proyectos
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from cerebro_mcp import ClienteCerebro, ErrorCerebro, normalizar
import jarvis_agente as J


class Servidor(BaseHTTPRequestHandler):
    calls = []
    caducar = False
    sse = True

    def log_message(self, *args):
        pass

    def do_POST(self):
        dato = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.calls.append((dato, dict(self.headers)))
        metodo = dato['method']
        if metodo == 'notifications/initialized':
            self.send_response(202); self.end_headers(); return
        if metodo == 'initialize':
            result = {'protocolVersion': '2025-06-18'}
        else:
            if self.caducar:
                type(self).caducar = False
                self.send_response(404); self.end_headers(); return
            result = {'structuredContent': {'result': [{'id': 1, 'contenido': 'dato'}]}}
        payload = json.dumps({'jsonrpc': '2.0', 'id': dato['id'], 'result': result})
        body = ('event: message\ndata: '+payload+'\n\n').encode() if self.sse else payload.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream' if self.sse else 'application/json')
        if metodo == 'initialize': self.send_header('Mcp-Session-Id', 'prueba')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers();self.wfile.write(body)


class Pruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Servidor)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def setUp(self):
        Servidor.calls = [];Servidor.sse = True;Servidor.caducar = False
        self.cliente = ClienteCerebro(f'http://127.0.0.1:{self.server.server_port}/mcp')

    def test_sesion_y_sse(self):
        self.assertTrue(self.cliente.llamar('buscar_memoria', {'consulta': 'dato'})['ok'])
        self.cliente.llamar('buscar_memoria', {'consulta': 'dato'})
        self.assertEqual(sum(c[0]['method'] == 'initialize' for c in Servidor.calls), 1)
        headers = {k.lower(): v for k,v in Servidor.calls[-1][1].items()}
        self.assertEqual(headers['mcp-session-id'], 'prueba')
        self.assertEqual(headers['mcp-protocol-version'], '2025-06-18')

    def test_json_y_sesion_caducada(self):
        Servidor.sse = False
        self.cliente.llamar('buscar_memoria', {})
        Servidor.caducar = True
        self.assertTrue(self.cliente.llamar('buscar_memoria', {})['ok'])
        self.assertEqual(sum(c[0]['method'] == 'initialize' for c in Servidor.calls), 2)

    def test_no_repite_escritura_tras_error_red(self):
        self.cliente.iniciado = True
        with patch.object(self.cliente, '_enviar', side_effect=urllib.error.URLError('fallo')) as enviar:
            with self.assertRaises(ErrorCerebro): self.cliente.llamar('corregir_memoria', {})
        self.assertEqual(enviar.call_count, 1)

    def test_no_expone_guardado(self):
        with self.assertRaises(ErrorCerebro): self.cliente.llamar('guardar_memoria', {})
        self.assertFalse(Servidor.calls)

    def test_pruebas_no_abren_conexion_al_servidor_real(self):
        cliente=ClienteCerebro()
        with patch('cerebro_mcp.en_pruebas',return_value=True),patch.object(cliente,'abrir') as abrir:
            with self.assertRaises(ErrorCerebro):cliente.llamar('buscar_memoria',{'consulta':'fixture'})
            abrir.assert_not_called()

    def test_normalizacion_errores(self):
        self.assertFalse(normalizar({'structuredContent': {'estado': 'no_encontrada'}})['ok'])
        self.assertFalse(normalizar({'isError': True})['ok'])
        self.assertEqual(normalizar({'content': [{'type':'text','text':'[{"id":2}]'}]})['memorias'][0]['id'],2)

    def test_argumentos_invalidos_no_llaman(self):
        for args in [{'consulta':'x', 'limite':True}, {'consulta':'x','limite':6},
                     {'consulta':''}, {'consulta':'x','incluir_personal':'true'}]:
            with patch.object(J.CEREBRO,'llamar') as llamar:
                self.assertFalse(J.ejecutar_herramienta('buscar_memoria_semantica',args,lambda _:True,{})['ok'])
                llamar.assert_not_called()

    def test_modificar_exige_consulta(self):
        with patch.object(J.CEREBRO,'llamar') as llamar:
            self.assertFalse(J.ejecutar_herramienta('olvidar_memoria',{'id_memoria':1},lambda _:True,{})['ok'])
            llamar.assert_not_called()

    def test_confirmacion_y_contenido_exacto_sin_registro_privado(self):
        contenido = 'privado' * 400
        state = {};prompts=[]
        with patch.object(J.CEREBRO,'llamar',side_effect=[{'ok':True,'memorias':[{'id':1,'titulo':'t','contenido':contenido}]}, {'ok':True,'memorias':[{'id':1,'titulo':'t','contenido':contenido}]}, {'ok':True,'estado':'corregida'}]) as llamar, patch.object(J.L,'_registrar') as registro:
            r=J.ejecutar_herramienta('buscar_memoria',{'consulta':'x'},lambda _:True,state)
            self.assertTrue(r['recortado'])
            J.ejecutar_herramienta('corregir_memoria',{'id_memoria':1,'contenido_nuevo':'nuevo'},lambda t:prompts.append(t) or True,state)
            self.assertIn(contenido,prompts[0])
            self.assertEqual(llamar.call_args.args[1]['contenido_esperado'],contenido)
            self.assertNotIn(contenido,str(registro.call_args))

    def test_permiso_denegado_no_modifica(self):
        state={'_memorias':{1:{'contenido':'privado'}}}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[{'contenido':'privado'}]}) as llamar,patch.object(J.L,'_registrar'):
            self.assertFalse(J.ejecutar_herramienta('olvidar_memoria',{'id_memoria':1},lambda _:False,state)['ok'])
            llamar.assert_called_once_with('consultar_memoria',{'id_memoria':1})

    def test_cache_sobrevive_otro_turno(self):
        state={'_memorias':{1:{'contenido':'privado'}}}
        J.ejecutar_turno([],lambda _: {'role':'assistant','content':'fin'},lambda _:True,state)
        self.assertIn('_memorias',state)

    def test_estado_con_cantidad_de_memorias(self):
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':20,'consultado':'hoy'}):
            r=J.ejecutar_herramienta('consultar_estado_cerebro',{},lambda _:False,{})
            self.assertEqual(r['memorias'],20)
            self.assertTrue(J.resumen_resultado('consultar_estado_cerebro',r)[0])

    def test_fechas_horas_y_cambio_de_dia(self):
        self.assertEqual(J.fechas_para_modelo('2026-10-12T05:42:04.430284+00:00'),
                         '12 de octubre de 2026, 02:42:04 (Chile)')
        self.assertEqual(J.fechas_para_modelo('2026-10-12T04:43:08.858908+00:00'),
                         '12 de octubre de 2026, 01:43:08 (Chile)')
        self.assertTrue(J.fechas_para_modelo('2026-10-12T01:00:00Z').startswith('11 de octubre'))
        self.assertIsNone(J.fechas_para_modelo(None))

    def test_listar_pagina_sin_filtrar_por_proyecto(self):
        recuerdos=[{'id':i,'contenido':'dato'} for i in range(1,13)]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':recuerdos}) as llamar:
            r=J.ejecutar_herramienta('listar_memorias',{'desplazamiento':5},lambda _:False,{})
            self.assertEqual([m['id'] for m in r['memorias']],[6,7,8,9,10])
            self.assertEqual(r['siguiente_desplazamiento'],10)
            llamar.assert_called_once_with('listar_memorias',{})

    def test_proyecto_vacio_es_opcional(self):
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[]}) as llamar:
            self.assertTrue(J.ejecutar_herramienta('buscar_memoria',{'consulta':'x','proyecto':''},lambda _:False,{})['ok'])
            llamar.assert_called_once()

    def test_clasificar_numero_lista_entre_turnos(self):
        recuerdos=[{'id':100+i,'contenido':str(i),'proyecto':'sin_clasificar','titulo':str(i)} for i in range(1,6)]
        state={};permisos=[]
        with patch.object(J.CEREBRO,'llamar',side_effect=[{'ok':True,'memorias':recuerdos},
               {'ok':True,'memorias':[recuerdos[3]]},{'ok':True,'estado':'clasificada'}]) as llamar,patch.object(J.L,'_registrar'):
            J.ejecutar_herramienta('listar_memorias',{},lambda _:False,state)
            J.ejecutar_turno([],lambda _: {'role':'assistant','content':'fin'},lambda _:True,state)
            r=J.ejecutar_herramienta('clasificar_memoria',{'numero_recuerdo':4,'proyecto':'Jarvis'},lambda t:permisos.append(t) or True,state)
            self.assertTrue(r['ok'])
            self.assertEqual(llamar.call_args.args[1]['id_memoria'],104)
            self.assertEqual(llamar.call_args.args[1]['proyecto_esperado'],'sin_clasificar')
            self.assertIn('Proyecto destino: Jarvis',permisos[0])

    def test_recuerdo_cambiado_no_pide_permiso(self):
        state={'_memorias':{1:{'contenido':'antes','proyecto':'p'}}}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[{'contenido':'después','proyecto':'p'}]}) as llamar:
            permisos=[]
            r=J.ejecutar_herramienta('olvidar_memoria',{'id_memoria':1},lambda t:permisos.append(t) or True,state)
            self.assertFalse(r['ok']);self.assertFalse(permisos)
            self.assertEqual(llamar.call_count,1)

    def test_backend_clasifica_sin_cambiar_contenido_y_rechaza_desactualizado(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            with closing(sqlite3.connect(base/'cerebro.db')) as db, db:
                db.execute('CREATE TABLE memorias(id INTEGER PRIMARY KEY,proyecto TEXT,titulo TEXT,contenido TEXT,creado TEXT)')
                db.execute("INSERT INTO memorias VALUES(1,'sin_clasificar','t','original','fecha')")
            r=clasificar(base,1,'jarvis','original','sin_clasificar')
            self.assertEqual(r['estado'],'clasificada')
            row=consultar(base,1)['memorias'][0]
            self.assertEqual(row['proyecto'],'Jarvis');self.assertEqual(row['contenido'],'original')
            self.assertFalse(clasificar(base,1,'otro','original','sin_clasificar')['ok'])
            self.assertEqual(consultar(base,1)['memorias'][0],row)

    def test_clasificar_desde_busqueda_sin_listar(self):
        recuerdo={'id':18,'contenido':'qwen','proyecto':'sin_clasificar','titulo':'Qwen'}
        state={}
        with patch.object(J.CEREBRO,'llamar',side_effect=[{'ok':True,'memorias':[recuerdo]},
              {'ok':True,'memorias':[recuerdo]},{'ok':True,'estado':'clasificada'}]) as llamar,patch.object(J.L,'_registrar'):
            J.ejecutar_herramienta('buscar_memoria',{'consulta':'qwen'},lambda _:True,state)
            J.ejecutar_turno([],lambda _: {'role':'assistant','content':'sí'},lambda _:True,state)
            r=J.ejecutar_herramienta('clasificar_memoria',{'id_memoria':18,'proyecto':'Jarvis'},lambda _:True,state)
            self.assertTrue(r['ok'])
            self.assertEqual(llamar.call_args.args[1]['id_memoria'],18)

    def test_busqueda_tambien_tiene_numeros(self):
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[{'id':18,'contenido':'qwen'}]}):
            state={}
            r=J.ejecutar_herramienta('buscar_memoria',{'consulta':'qwen'},lambda _:True,state)
            self.assertEqual(r['memorias'][0]['numero_lista'],1)
            self.assertEqual(state['_lista_memorias'],{1:18})

    def test_crear_proyecto_exige_permiso(self):
        with patch.object(J.CEREBRO,'llamar') as llamar:
            self.assertFalse(J.ejecutar_herramienta('crear_proyecto',{'proyecto':'Jarvis'},lambda _:False,{})['ok'])
            llamar.assert_not_called()
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'estado':'creado','proyecto':'Jarvis'}) as llamar,patch.object(J.L,'_registrar'):
            self.assertTrue(J.ejecutar_herramienta('crear_proyecto',{'proyecto':'Jarvis'},lambda _:True,{})['ok'])
            llamar.assert_called_once_with('crear_proyecto',{'proyecto':'Jarvis'})

    def test_proyecto_vacio_listado_sin_rellenar_memorias(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            with closing(sqlite3.connect(base/'cerebro.db')) as db, db:
                db.execute('CREATE TABLE memorias(id INTEGER PRIMARY KEY,proyecto TEXT,titulo TEXT,contenido TEXT,creado TEXT)')
                db.execute("INSERT INTO memorias VALUES(1,'estudios','t','original','fecha')")
            self.assertEqual(crear_proyecto(base,'JARVIS')['estado'],'creado')
            self.assertEqual(crear_proyecto(base,'jarvis')['estado'],'ya_existe')
            self.assertEqual(proyectos(base)['proyectos'],[{'proyecto':'estudios','total':1},{'proyecto':'Jarvis','total':0}])
            self.assertEqual(consultar(base,1)['memorias'][0]['contenido'],'original')
            with closing(sqlite3.connect(base/'cerebro.db')) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM memorias').fetchone()[0],1)

    def test_clasificacion_ambigua_no_ejecuta(self):
        with patch.object(J.CEREBRO,'llamar') as llamar:
            self.assertFalse(J.ejecutar_herramienta('clasificar_memoria',{'numero_recuerdo':1,'id_memoria':18,'proyecto':'Jarvis'},lambda _:True,{})['ok'])
            self.assertFalse(J.ejecutar_herramienta('clasificar_memoria',{'proyecto':'Jarvis'},lambda _:True,{})['ok'])
            llamar.assert_not_called()

    def test_respuesta_vacia_informa_limite(self):
        r=J.ejecutar_turno([],lambda _: {'role':'assistant','content':''},lambda _:True,{})
        self.assertIn('No pude generar una respuesta',r)

    def test_anuncio_creacion_no_termina_sin_ejecutar(self):
        respuestas=iter([{'role':'assistant','content':'Voy a crearlo vacío.'},
            {'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_proyecto','arguments':{'proyecto':'Jarvis'}}}]},
            {'role':'assistant','content':'Creado.'}])
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'estado':'creado','proyecto':'Jarvis'}) as llamar,patch.object(J.L,'_registrar'):
            r=J.ejecutar_turno([{'role':'user','content':'Crea el proyecto Jarvis'}],lambda _:next(respuestas),lambda _:True,{})
            self.assertIn('creado',r.casefold())
            llamar.assert_called_once_with('crear_proyecto',{'proyecto':'Jarvis'})

    def test_resultado_recortado_sigue_json(self):
        self.assertTrue(json.loads(J._para_modelo({'ok':True,'texto':'a'*30000}))['recortado'])


if __name__ == '__main__':
    unittest.main()
