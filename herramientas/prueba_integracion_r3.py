import os, tempfile, atexit
if "JARVIS_DIR" not in os.environ:
    _aislamiento=tempfile.TemporaryDirectory(prefix="jarvis-focal-r3-")
    atexit.register(_aislamiento.cleanup)
    os.environ.update(JARVIS_DIR=_aislamiento.name,JARVIS_PRUEBAS="1")
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import interfaz_local as I
import configuracion_jarvis as C
import jarvis_agente as J
import externo_zen as Z
import vocabulario_privado as V

class Pruebas(unittest.TestCase):
    def test_estilo_no_cambia_sin_permiso_y_persiste_con_permiso(self):
        with tempfile.TemporaryDirectory() as t:
            ajustes=dict(C.DEFAULT);archivo=Path(t)/'config.json';guardar=C.guardar
            with patch.object(C,'guardar',side_effect=lambda d:guardar(d,archivo)):
                self.assertTrue(I.comando_local('/estilo tecnico',[],{},lambda _:False,ajustes,lambda:None,object())[0]);self.assertFalse(archivo.exists())
                I.comando_local('/estilo tecnico',[],{},lambda _:True,ajustes,lambda:None,object());self.assertEqual(C.leer(archivo)[0]['modo'],'tecnico')
    def test_estilo_tecnico_y_peticion_simple_afectan_prompt(self):
        with patch.dict(J.AJUSTES,modo='tecnico'):
            self.assertIn('Usa precisión técnica',J.prompt_para_turno('Explica un algoritmo'))
            self.assertIn('Responde con frases cortas',J.prompt_para_turno('Explica simple un algoritmo'))
    def test_guia_nueva_se_incorpora_sin_invadir_ejemplo_de_funcion(self):
        from guias_contexto_r3 import contexto
        self.assertIn('servicio',contexto('Dame una guia Spring Boot'))
        self.assertFalse(contexto('Crea una función Kotlin de dos Int. Solo texto.'))
    def test_ambiguo_se_detiene_antes_de_controlador(self):
        from interfaz_jarvis import comando
        h=[];e={}
        hecho,texto=comando('modifica itgo',h,e,lambda *a:self.fail('No ejecuta'),J.SISTEMA,local=lambda *a:self.fail('No prepara acciones'))
        self.assertTrue(hecho);self.assertIn('¿Es así?',texto);self.assertEqual(h[0]['content'],'modifica itgo')
    def test_fallo_local_subir_a_zen_no_repite_herramientas(self):
        h=[{'role':'user','content':'Escribe una función Python que sume dos números. Solo texto.'}];e={}
        modelo={'id':'deepseek-v4.1-flash-free'}
        def elegido(p,c,e,**kw):return (modelo,'fallo local') if kw.get('fallo') else (None,'primero local')
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('fallo simulado')),patch.object(J.O,'modelos',return_value=['qwen3:8b','jarvis-deepseek:8b']),patch.object(Z,'elegir',side_effect=elegido),patch.object(Z,'preguntar',return_value='Respondió: externo, deepseek-v4.1-flash-free\nEjemplo ficticio') as enviar:
            r=J.responder_con_respaldo(h,lambda *a:None,lambda *a:self.fail('Sin acciones'),e,mostrar=lambda _:None)
        self.assertIn('Respondió: externo',r);self.assertEqual(enviar.call_count,1)
    def test_fallo_de_herramienta_no_puede_subir(self):
        from seguridad_texto import privacidad_externa
        self.assertFalse(privacidad_externa('Escribe una función Python',herramientas=True)[0])
    def test_fallo_externo_solo_un_intento_local_sin_herramientas(self):
        h=[{'role':'user','content':'Escribe una función Python que sume dos números. Solo texto.'}];e={}
        def elegido(p,c,e,**kw):return ({'id':'deepseek-v4.1-flash-free'},'fallo') if kw.get('fallo') else (None,'local primero')
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('fallo local')),patch.object(J.O,'modelos',return_value=['qwen3:8b','jarvis-deepseek:8b']),patch.object(Z,'elegir',side_effect=elegido),patch.object(Z,'preguntar',side_effect=ConnectionError('HTTP 429')),patch.object(J.IA,'preguntar_ia',return_value={'ok':True,'respuesta':'Texto local comprobado como recibido'}) as local:
            r=J.responder_con_respaldo(h,lambda *a:None,lambda *a:self.fail('Sin permiso ni herramientas'),e,mostrar=lambda _:None)
        self.assertEqual(local.call_count,1);self.assertIn('HTTP 429',r);self.assertIn('Respuesta local',r)
    def test_config_zen_nunca_habilita_otro_proveedor(self):
        import politica_ia
        with patch.object(Z,'estado',return_value={'encendido':True}):self.assertFalse(politica_ia.permite_externa())
    def test_contexto_generico_extenso_puede_llegar_al_controlador_externo(self):
        from interfaz_jarvis import comando
        p='Explica '+('un concepto general y sus propiedades. '*500)
        with patch.object(Z,'elegir',return_value=({'id':'deepseek-v4.1-flash-free'},'contexto extenso')):
            ok,_=comando(p,[],{},lambda *a:self.fail('Sin acciones'),J.SISTEMA)
        self.assertFalse(ok)
    def test_lexico_corrupto_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as t,patch.object(V,'ARCHIVO',Path(t)/'vocab.json'):
            V.ARCHIVO.write_text('{ roto')
            with self.assertRaises(ValueError):V.cambiar('x','algo',lambda _:self.fail('No reemplazar'))
            self.assertEqual(V.ARCHIVO.read_text(),'{ roto')
    def test_hilo_de_prueba_no_puede_escribir_en_la_ruta_real(self):
        import hilo_conversacion as H
        with patch.object(H,'CARPETA',Path.home()/'Jarvis/datos/hilos'),self.assertRaisesRegex(ValueError,'directorio real'):
            H.guardar({})
    def test_medidor_difiere_importar_cliente_hasta_fijar_temporal(self):
        import subprocess,sys,os
        codigo='''import sys,os,tempfile
from pathlib import Path
import medir_ronda3_20261020 as M
with tempfile.TemporaryDirectory() as t:
 M.M.DESTINO=Path(t)
 sys.argv=['medidor','--ronda','aislamiento','--esperar-recursos']
 M.preparar_espera()
 assert 'cliente_ollama' not in sys.modules
 os.environ.update(JARVIS_DIR=t,JARVIS_PRUEBAS='1')
 M.M.ANTES_DE_CLIENTE()
 import entorno_jarvis,configuracion_jarvis
 assert entorno_jarvis.PROYECTO==Path(t)
 assert configuracion_jarvis.ARCHIVO==Path(t)/'datos/configuracion.json'
 print('OK')'''
        r=subprocess.run([sys.executable,'-B','-c',codigo],env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent)),capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout.strip(),'OK')

if __name__=='__main__':unittest.main()
