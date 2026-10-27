"""Selección por turno, persistencia y permisos; solo datos y transportes sintéticos."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import configuracion_jarvis as C
import coordinador_deepseek as COORD
import enrutador_modelos as R
import jarvis_agente as J
from interfaz_local import comando_local

QWEN = C.MODELO_COTIDIANO
DS = C.MODELO_PREDETERMINADO


class Reglas(unittest.TestCase):
    def test_cotidiana(self):
        self.assertEqual(R.seleccionar_respuesta('Hola, explícame qué es una variable', [QWEN, DS], DS)['modelo'], QWEN)

    def test_analisis(self):
        for texto in ('Analiza esta arquitectura', 'Depura este error difícil', 'Compara dos estrategias', 'Optimiza este algoritmo', 'Diagnostica un deadlock'):
            with self.subTest(texto=texto):
                self.assertEqual(R.seleccionar_respuesta(texto, [QWEN, DS], DS)['modelo'], DS)

    def test_accion_directa(self):
        self.assertEqual(R.seleccionar_respuesta('Lee demo.txt', [QWEN, DS], DS)['modelo'], QWEN)

    def test_falta_qwen(self):
        r = R.seleccionar_respuesta('Hola', [DS], DS)
        self.assertEqual(r['modelo'], DS)
        self.assertTrue(r['alternativa'])

    def test_falta_deepseek(self):
        self.assertEqual(R.seleccionar_respuesta('Analiza la arquitectura', [QWEN], DS)['modelo'], QWEN)

    def test_ninguno_instalado(self):
        with self.assertRaises(ConnectionError):
            R.seleccionar_respuesta('Hola', ['nomic-embed-text:latest'], DS)

    def test_modelo_inventado_en_pedido_no_se_ejecuta(self):
        r = R.seleccionar_respuesta('Responde usando desconocido:latest', ['desconocido:latest', QWEN, DS], DS)
        self.assertEqual(r['modelo'], QWEN)

    def test_texto_del_adjunto_no_decide_la_ruta(self):
        r=R.seleccionar_respuesta('Explícame esto\n[Adjunto: caso.txt]\nAnaliza la arquitectura', [QWEN,DS],DS)
        self.assertEqual(r['modelo'],QWEN)

    def test_continuacion_retiene_modelo(self):
        self.assertEqual(R.seleccionar_respuesta('continúa', [QWEN, DS], DS, anterior=DS, continuar=True)['modelo'], DS)

    def test_cambio_de_tema_no_retiene_modelo(self):
        self.assertEqual(R.seleccionar_respuesta('Hola', [QWEN, DS], DS, anterior=DS)['modelo'], QWEN)

    def test_analisis_nuevo_prevalece_sobre_continuacion(self):
        self.assertEqual(R.seleccionar_respuesta('Analiza eso', [QWEN, DS], DS, anterior=QWEN, continuar=True)['modelo'], DS)

    def test_anterior_no_instalado_no_se_reutiliza(self):
        self.assertEqual(R.seleccionar_respuesta('continúa', [QWEN], DS, anterior=DS, continuar=True)['modelo'], QWEN)


class Integracion(unittest.TestCase):
    def setUp(self):
        self.ajustes = patch.object(J, 'AJUSTES', dict(C.DEFAULT, seleccion_modelo='automatico'))
        self.ajustes.start();self.addCleanup(self.ajustes.stop)
        self.modelo = patch.object(J, 'MODELO', DS)
        self.modelo.start();self.addCleanup(self.modelo.stop)
        for nombre in ('modelo','ruta_modelo','analisis_deepseek'):
            previo=getattr(J.TIEMPO_MODELO,nombre,None)
            self.addCleanup(setattr,J.TIEMPO_MODELO,nombre,previo)
            setattr(J.TIEMPO_MODELO,nombre,None)
        self.modelos=patch.object(J.O,'modelos',return_value=[QWEN,DS])
        self.catalogo=self.modelos.start();self.addCleanup(self.modelos.stop)
        self.codigo=patch.object(J.CODIGO,'contexto',return_value='')
        self.codigo.start();self.addCleanup(self.codigo.stop)
        self.android=patch.object(J.SEGUIMIENTO,'iniciar_android',return_value=None)
        self.android.start();self.addCleanup(self.android.stop)
        self.auxiliar=patch.object(COORD,'preparar_analisis',return_value={'estado':'omitido','analisis':''})
        self.aux=self.auxiliar.start();self.addCleanup(self.auxiliar.stop)

    def historial(self,pregunta):
        return [{'role':'system','content':'Reglas previas.'},{'role':'user','content':pregunta}]

    def test_payload_cotidiano_y_prompt_corresponden_a_qwen(self):
        h=self.historial('Hola')
        with patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':'Hola'}}) as enviar:
            texto=J.ejecutar_turno(h,J.enviar_a_ollama,lambda _:False,{},mostrar=lambda _:None)
        self.assertEqual(texto,'Hola')
        cuerpo=enviar.call_args.args[1]
        self.assertEqual(cuerpo['model'],QWEN)
        self.assertNotIn('format',cuerpo)
        self.assertIn('modelo '+QWEN,h[0]['content'])
        self.assertEqual(J.ESTADISTICAS['modelo'],QWEN)
        self.assertEqual(J.ESTADISTICAS['seleccion_modelo'],'automatico')
        self.assertFalse(self.aux.call_args.kwargs['permitido'])

    def test_payload_analisis_usa_protocolo_deepseek(self):
        h=self.historial('Analiza dos estrategias')
        salida=json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'Análisis sintético.'})
        with patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':salida}}) as enviar:
            texto=J.ejecutar_turno(h,J.enviar_a_ollama,lambda _:False,{},mostrar=lambda _:None)
        self.assertEqual(texto,'Análisis sintético.')
        self.assertEqual(enviar.call_args.args[1]['model'],DS)
        self.assertIn('format',enviar.call_args.args[1])
        self.assertIn('modelo '+DS,h[0]['content'])

    def test_motor_de_chat_publico_respeta_seleccion(self):
        h=self.historial('Analiza dos estrategias')
        salida=json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'Análisis sintético.'})
        with patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':salida}}) as enviar, patch.object(J.IA.P,'opciones',return_value={'configurado':False,'automatico':False}), patch.object(J.IA,'preguntar_externa') as nube:
            texto=J.responder_con_respaldo(h,J.enviar_a_ollama,lambda _:False,{},mostrar=lambda _:None)
        self.assertEqual(texto,'Análisis sintético.')
        self.assertEqual(enviar.call_args.args[1]['model'],DS)
        nube.assert_not_called()

    def test_manual_no_consulta_catalogo_ni_cambia_modelo(self):
        J.AJUSTES['seleccion_modelo']='manual'
        with patch.object(J,'_ejecutar_turno',side_effect=lambda *a:J.modelo_del_turno()) as turno:
            self.assertEqual(J.ejecutar_turno(self.historial('Hola'),None,None,{},mostrar=lambda _:None),DS)
        self.catalogo.assert_not_called();turno.assert_called_once()

    def test_modelo_no_cambia_durante_herramientas(self):
        h=self.historial('Busca demo.txt')
        def ejecutar(*args):
            self.assertEqual(J.modelo_del_turno(),QWEN)
            J.MODELO=DS
            self.assertEqual(J.modelo_del_turno(),QWEN)
            return 'Terminado'
        with patch.object(J,'_ejecutar_turno',side_effect=ejecutar):
            J.ejecutar_turno(h,None,None,{},mostrar=lambda _:None)
        self.assertEqual(J.MODELO,DS)
        self.catalogo.assert_called_once()

    def test_limpieza_despues_de_error(self):
        J.TIEMPO_MODELO.modelo='modelo-exterior'
        J.TIEMPO_MODELO.analisis_deepseek='anterior'
        with patch.object(J,'_ejecutar_turno',side_effect=ConnectionError('sintético')):
            with self.assertRaises(ConnectionError):
                J.ejecutar_turno(self.historial('Hola'),None,None,{},mostrar=lambda _:None)
        self.assertEqual(J.modelo_del_turno(),'modelo-exterior')
        self.assertEqual(J.TIEMPO_MODELO.analisis_deepseek,'anterior')

    def test_catalogo_caido_no_infiere(self):
        self.catalogo.side_effect=ConnectionError('sin conexión')
        with patch.object(J,'_ejecutar_turno') as ejecutar:
            with self.assertRaises(ConnectionError):
                J.ejecutar_turno(self.historial('Hola'),None,None,{},mostrar=lambda _:None)
        ejecutar.assert_not_called()
        self.assertEqual(J.modelo_del_turno(),DS)

    def test_imagen_no_se_envia_a_modelo_sin_vision(self):
        h=self.historial('Analiza la imagen');h[-1]['images']=['imagen-sintetica']
        with patch.object(J,'_ejecutar_turno') as ejecutar:
            with self.assertRaisesRegex(ConnectionError,'modelo visual'):
                J.ejecutar_turno(h,None,None,{},mostrar=lambda _:None)
        ejecutar.assert_not_called()
        self.assertEqual(h[-1]['images'],['imagen-sintetica'])

    def test_modelo_visual_configurado_se_conserva(self):
        h=self.historial('Analiza la imagen');h[-1]['images']=['imagen-sintetica']
        with patch.object(J,'MODELO','llava:7b'), patch.object(J.O,'modelos',return_value=['llava:7b',QWEN,DS]), patch.object(J,'_ejecutar_turno',side_effect=lambda *a:J.modelo_del_turno()):
            self.assertEqual(J.ejecutar_turno(h,None,None,{},mostrar=lambda _:None),'llava:7b')

    def test_seleccion_no_se_propaga_a_otro_hilo(self):
        vistos=[]
        def ejecutar(*args):
            hilo=threading.Thread(target=lambda:vistos.append(J.modelo_del_turno()))
            hilo.start();hilo.join()
            self.assertEqual(J.modelo_del_turno(),QWEN)
            return 'Terminado'
        with patch.object(J,'_ejecutar_turno',side_effect=ejecutar):
            J.ejecutar_turno(self.historial('Hola'),None,None,{},mostrar=lambda _:None)
        self.assertEqual(vistos,[DS])

    def test_denegacion_no_hace_accion_ni_consulta_otro_modelo(self):
        h=self.historial('Analiza y crea no_crear.txt con texto sintético')
        respuesta=json.dumps({'accion':'crear_archivo','argumentos':{'ruta':'no_crear.txt','contenido':'SINTETICO'},'respuesta':''})
        permisos=[]
        with tempfile.TemporaryDirectory() as tmp, patch.object(J.E,'RAIZ',Path(tmp)), patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':respuesta}}) as enviar:
            texto=J.ejecutar_turno(h,J.enviar_a_ollama,lambda texto:permisos.append(texto) or False,{},mostrar=lambda _:None)
            self.assertFalse((Path(tmp)/'no_crear.txt').exists())
        self.assertEqual(len(permisos),1)
        enviar.assert_called_once()
        self.assertIn('El usuario no autorizó',texto)


class Configuracion(unittest.TestCase):
    def test_persistencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json'
            C.guardar(dict(C.DEFAULT,seleccion_modelo='automatico'),p)
            datos,aviso=C.leer(p)
            self.assertEqual(datos['seleccion_modelo'],'automatico');self.assertFalse(aviso)
            self.assertEqual(C.etiqueta_modelo(datos),C.ETIQUETA_AUTOMATICA)

    def test_config_vieja_se_mantiene_manual(self):
        self.assertEqual(C.validar({'modelo':QWEN})['seleccion_modelo'],'manual')

    def test_valor_invalido(self):
        with self.assertRaises(ValueError):C.validar({'seleccion_modelo':'inventado'})

    def test_comando_auto_guarda_sin_cambiar_otros_ajustes(self):
        ajustes=dict(C.DEFAULT,timeout_modelo=75)
        with patch('interfaz_local.O.modelos',return_value=[QWEN,DS]), patch('interfaz_local.C.guardar',side_effect=lambda d:C.validar(d)):
            hecho,texto=comando_local('/modelo automatico',[],{},lambda _:False,ajustes,lambda:None,None)
        self.assertTrue(hecho);self.assertIn('guardada',texto)
        self.assertEqual(ajustes['seleccion_modelo'],'automatico')
        self.assertEqual(ajustes['timeout_modelo'],75)

    def test_comando_manual_desactiva_auto(self):
        ajustes=dict(C.DEFAULT,seleccion_modelo='automatico')
        with patch('interfaz_local.O.modelos',return_value=[QWEN,DS]), patch('interfaz_local.C.guardar'):
            comando_local('/modelo '+QWEN,[],{},lambda _:False,ajustes,lambda:None,None)
        self.assertEqual(ajustes['seleccion_modelo'],'manual')
        self.assertEqual(ajustes['modelo'],QWEN)

    def test_sin_modelos_no_guarda_auto(self):
        with patch('interfaz_local.O.modelos',return_value=[]), patch('interfaz_local.C.guardar') as guardar:
            _,texto=comando_local('/modelo auto',[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
        self.assertIn('No están instalados',texto);guardar.assert_not_called()


if __name__=='__main__':unittest.main()
