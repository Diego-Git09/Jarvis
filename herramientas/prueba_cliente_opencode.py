"""Contrato de texto y proceso aislado. Nunca consulta un modelo real."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import cliente_opencode as C


def eventos(texto='Respuesta genérica.'):
    return '\n'.join(json.dumps(d) for d in (
        {'type':'step_start'}, {'type':'text','part':{'text':texto}},
        {'type':'step_finish','part':{'reason':'stop'}}))


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.addCleanup(patch.stopall)
        self.root=Path(self.tmp.name)
        self.exe=self.root/'bin/opencode';self.exe.parent.mkdir()
        self.exe.write_bytes(b'CLIENTE_FICTICIO');self.exe.chmod(0o700)
        self.recibo=self.root/'instalacion_verificada.json'
        self.recibo.write_text(json.dumps({'binario':'bin/opencode','sha256':hashlib.sha256(self.exe.read_bytes()).hexdigest()}))
        patch.object(C,'INSTALACION',self.root).start();patch.object(C,'RECIBO',self.recibo).start()
        self.cuerpo={'model':C.MODELO,'messages':[{'role':'user','content':'Explica qué es una variable en Python.'}]}

    def test_configuracion_sin_herramientas_ni_otros_proveedores(self):
        c=C.configuracion()
        self.assertEqual(c['permission'],{'*':'deny'})
        self.assertEqual(c['agent']['jarvis_texto']['permission'],{'*':'deny'})
        self.assertEqual(c['enabled_providers'],['opencode'])
        self.assertEqual(c['agent']['jarvis_texto']['steps'],1)
        self.assertEqual(c['mcp'],{});self.assertEqual(c['plugin'],[])
        self.assertEqual(c['instructions'],[]);self.assertEqual(c['share'],'disabled')
        self.assertEqual(c['small_model'],c['model'])

    def test_ejecutable_modificado_no_se_usa(self):
        self.assertEqual(C.binario(),self.exe)
        self.exe.write_bytes(b'MODIFICADO');self.assertIsNone(C.binario())

    def test_recibo_no_permite_escapar_de_la_instalacion(self):
        for ruta in ('../fuera','/usr/bin/python3'):
            self.recibo.write_text(json.dumps({'binario':ruta,'sha256':'falso'}))
            self.assertIsNone(C.binario())

    def test_aislamiento_no_monta_archivos_del_usuario_ni_pone_clave_en_argumentos(self):
        trabajo=self.root/'aislamiento';trabajo.mkdir()
        with patch.object(C.shutil,'which',return_value='/usr/bin/bwrap'):
            args,env=C.preparar_aislamiento(trabajo,'CLAVE_FICTICIA_PRIVADA')
        self.assertIn('--unshare-all',args);self.assertIn('--share-net',args)
        self.assertNotIn('CLAVE_FICTICIA_PRIVADA',' '.join(args))
        self.assertNotIn('HOME',env);self.assertNotIn('CODEX_HOME',env)
        self.assertNotIn('OPENAI_API_KEY',env)
        self.assertEqual(env['OPENCODE_API_KEY'],'CLAVE_FICTICIA_PRIVADA')
        self.assertEqual(env['XDG_CONFIG_HOME'],'/work/config')
        self.assertNotIn('/home',args)

    def test_solo_texto_con_final_confirmado(self):
        self.assertEqual(C.interpretar_eventos(eventos()),'Respuesta genérica.')
        with self.assertRaises(ConnectionError):C.interpretar_eventos('')
        with self.assertRaises(ConnectionError):C.interpretar_eventos(json.dumps({'type':'text','part':{'text':'Parcial'}}))

    def test_herramientas_incluso_fallidas_descartan_respuesta(self):
        for e in ({'type':'tool_use','part':{'state':{'status':'error'}}},
                  {'type':'text','part':{'type':'tool','text':'No confiar'}},
                  {'type':'permission'}):
            with self.subTest(e=e),self.assertRaises(ConnectionError):
                C.interpretar_eventos(eventos()+'\n'+json.dumps(e))

    def test_error_no_revela_el_mensaje_remoto(self):
        with self.assertRaises(ConnectionError) as e:
            C.interpretar_eventos(json.dumps({'type':'error','error':'CLAVE_FICTICIA_NO_MOSTRAR'}))
        self.assertNotIn('CLAVE_FICTICIA',str(e.exception))

    def test_rechazo_gratuito_se_distingue_sin_copiar_respuesta_remota(self):
        cuerpo=json.dumps({'error':{'type':'FreeTierError','message':'CLAVE_FICTICIA_NO_MOSTRAR'}})
        evento={'type':'error','error':{'name':'APIError','data':{'statusCode':403,'responseBody':cuerpo}}}
        with self.assertRaisesRegex(ConnectionError,'HTTP 403, FreeTierError') as e:
            C.interpretar_eventos(json.dumps(evento))
        self.assertNotIn('CLAVE_FICTICIA',str(e.exception))

    def test_errores_http_conservan_codigo_sin_exponer_detalles(self):
        for codigo in (401,403,429,500,503):
            evento={'type':'error','error':{'data':{'statusCode':codigo,'message':'CLAVE_FICTICIA_NO_MOSTRAR'}}}
            with self.subTest(codigo=codigo),self.assertRaises(ConnectionError) as e:
                C.interpretar_eventos(json.dumps(evento))
            self.assertIn('HTTP '+str(codigo),str(e.exception))
            self.assertNotIn('CLAVE_FICTICIA',str(e.exception))

    def test_no_se_lanza_con_adjuntos_historial_o_secretos(self):
        falsos=[dict(self.cuerpo,messages=[{'role':'user','content':'Explica /home/ficticio/dato.py'}]),
                dict(self.cuerpo,messages=[{'role':'user','content':'Explica token=CLAVE_FICTICIA'}]),
                dict(self.cuerpo,messages=self.cuerpo['messages']+[{'role':'assistant','content':'historial'}]),
                dict(self.cuerpo,messages=[dict(self.cuerpo['messages'][0],images=['ficticia'])]),
                dict(self.cuerpo,model='modelo-no-permitido'),dict(self.cuerpo,tools=[{'name':'leer'}])]
        with patch.object(C.subprocess,'Popen') as proceso:
            for cuerpo in falsos:
                with self.subTest(cuerpo=cuerpo),self.assertRaises(ValueError):C.consultar(cuerpo,'CLAVE_FICTICIA')
        proceso.assert_not_called()

    def test_proceso_recibe_pregunta_por_entrada_y_solo_devuelve_texto(self):
        codigo='import sys; p=sys.stdin.read(); print('+repr(eventos())+')'
        preparar=Mock(return_value=([sys.executable,'-c',codigo],{'PATH':'/usr/bin:/bin'}))
        registrados=[];retirados=[]
        with patch.object(C,'preparar_aislamiento',preparar):
            r=C.consultar(self.cuerpo,'CLAVE_FICTICIA',registrar=registrados.append,retirar=retirados.append)
        self.assertEqual(r['choices'][0]['message']['content'],'Respuesta genérica.')
        self.assertEqual(registrados,retirados)

    def test_plazo_agotado_termina_solo_su_proceso(self):
        preparar=Mock(return_value=([sys.executable,'-c','import time;time.sleep(3)'],{'PATH':'/usr/bin:/bin'}))
        handles=[]
        with patch.object(C,'preparar_aislamiento',preparar),patch.object(C,'TIEMPO_MAXIMO',.05),self.assertRaisesRegex(ConnectionError,'agotó el tiempo'):
            C.consultar(self.cuerpo,'CLAVE_FICTICIA',registrar=handles.append)
        self.assertIsNotNone(handles[0].proceso.poll())


if __name__=='__main__':unittest.main()
