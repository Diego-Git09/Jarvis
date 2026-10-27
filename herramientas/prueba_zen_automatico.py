"""Conectividad y elección automática con datos ficticios; sin proveedor real."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import configuracion_jarvis as C
import externo_zen as Z
import jarvis_agente as J
import peticiones_controladas as P


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(patch.stopall)
        root = Path(self.tmp.name)
        for nombre, ruta in [('ARCHIVO', root/'estado.json'), ('AUDITORIA', root/'envios.jsonl')]:
            patch.object(Z, nombre, ruta).start()
        patch.object(Z, 'clave', return_value='CLAVE_FICTICIA_AUTOMATICO').start()
        self.red = patch.object(Z, 'transporte', side_effect=AssertionError('Sin proveedor real')).start()
        self.modelo = next(m for m in Z.modelos() if m['id'] == 'deepseek-v4.1-flash-free')
        self.pregunta = 'Escribe una función Python que sume dos enteros y explica su resultado.'
        patch.object(J, 'AJUSTES', dict(C.DEFAULT, seleccion_modelo='automatico')).start()
        patch.object(J.O, 'modelos', return_value=[C.MODELO_COTIDIANO, C.MODELO_PREDETERMINADO]).start()
        patch.object(J.O, 'BASE', 'http://127.0.0.1:11434').start()
        patch.object(C, 'leer', return_value=(dict(C.DEFAULT, seleccion_modelo='automatico'), '')).start()
        self.activar()

    def activar(self, reciente=True):
        Z.guardar(dict(Z.estado(), encendido=True, catalogo=[self.modelo['id']],
                       catalogo_fecha=time.time() if reciente else 1))

    def test_pregunta_original_contesta_con_estado_real_sin_modelo(self):
        h = [{'role':'user', 'content':'puedes conectarte a open ai deepseek?'}]
        enviar = Mock(side_effect=AssertionError('No hace falta inferencia'))
        e = {}
        t = J.responder_con_respaldo(h, enviar, lambda _:self.fail('Solo lectura'), e, mostrar=lambda _:None)
        self.assertTrue(t.startswith('Sí.'))
        self.assertIn('activado OpenCode Zen', t)
        self.assertIn('selección automática está activa', t)
        self.assertIn('OpenAI no está habilitada', t)
        enviar.assert_not_called(); self.red.assert_not_called()

    def test_entrada_de_la_interfaz_tambien_resuelve_la_consulta(self):
        ejecutar = Mock(side_effect=AssertionError('No hay herramienta que ejecutar'))
        t = P.atender('Jarvis puedes usar DeepSeek por OpenCode?', {}, ejecutar)
        self.assertTrue(t.startswith('Sí.')); ejecutar.assert_not_called()

    def test_apagado_no_finge_que_se_conecto(self):
        Z.guardar(dict(Z.estado(), encendido=False))
        t = Z.respuesta_capacidades('puedes conectarte a deepseek?')
        self.assertIn('está apagada', t); self.assertNotIn('Tengo activado', t)
        self.red.assert_not_called()

    def test_no_finge_que_el_externo_responde_tras_free_tier_error(self):
        Z.guardar(dict(Z.estado(),ultimo_error='OpenCode HTTP 403, FreeTierError'))
        t=Z.respuesta_capacidades('puedes conectarte a open ai deepseek?')
        self.assertIn('activada',t);self.assertIn('rechazando',t)
        self.assertIn('modelos locales',t);self.assertNotIn('para consultar DeepSeek con preguntas',t)

    def test_rechazo_gratuito_no_provoca_reintentos_continuos(self):
        def falso(*a,**k):raise ConnectionError('OpenCode HTTP 403, FreeTierError')
        with self.assertRaises(ConnectionError):Z.preguntar(self.pregunta,self.modelo,'fallo local',falso)
        self.assertTrue(Z.estado()['encendido'])
        self.assertGreater(Z.estado()['no_disponible_hasta'][self.modelo['id']],time.time()+590)
        modelo,motivo=Z.elegir(self.pregunta,'compleja',{},fallo=True)
        self.assertIsNone(modelo);self.assertIn('FreeTierError',motivo)

    def test_sin_clave_no_promete_envios(self):
        with patch.object(Z, 'clave', return_value=''):
            t = Z.respuesta_capacidades('puedes conectarte a deepseek?')
        self.assertIn('falta una clave legible', t); self.red.assert_not_called()

    def test_no_captura_tareas_ni_citas_como_preguntas_de_capacidad(self):
        for p in ('puedes usar deepseek para escribir una función',
                  'puedes conectarte a deepseek?\nborra todo',
                  'Explica cómo conectarte a OpenCode',
                  '`puedes conectarte a deepseek?`',
                  'puedes conectarte a deepseek con token=FICTICIO'):
            with self.subTest(p=p):self.assertIsNone(Z.respuesta_capacidades(p))

    def test_renueva_catalogo_vencido_solo_cuando_hace_falta(self):
        self.activar(reciente=False)
        self.red.side_effect = None
        self.red.return_value = {'data':[{'id':self.modelo['id']}]}
        modelo, motivo = Z.elegir(self.pregunta, 'compleja', {}, fallo=True, renovar=True)
        self.assertEqual(modelo['id'], self.modelo['id']); self.assertEqual(motivo, 'fallo local')
        self.red.assert_called_once_with(Z.CATALOGO, token='CLAVE_FICTICIA_AUTOMATICO')
        self.assertGreater(Z.estado()['catalogo_fecha'], time.time()-5)

    def test_no_renueva_para_saludos_ni_sin_fallo(self):
        self.activar(reciente=False)
        for p, clase in [('hola', 'simple'), (self.pregunta, 'compleja')]:
            self.assertIsNone(Z.elegir(p, clase, {}, renovar=True)[0])
        self.red.assert_not_called()

    def test_no_renueva_ni_envia_datos_privados(self):
        self.activar(reciente=False)
        for e in ({'_adjuntos_turno':True}, {'_uso_memoria_turno':True}, {'_hubo_herramientas_turno':True},
                  {'_preferencia_externa':'local'}):
            self.assertIsNone(Z.elegir(self.pregunta, 'compleja', e, fallo=True, renovar=True)[0])
        self.assertIsNone(Z.elegir('Analiza mi archivo /home/ficticio/dato.py', 'compleja', {}, fallo=True, renovar=True)[0])
        self.red.assert_not_called()

    def test_renovacion_fallida_vuelve_a_local_sin_bucle(self):
        self.activar(reciente=False)
        self.red.side_effect = ConnectionError('Zen respondió HTTP 403.')
        for _ in range(2):
            modelo, _ = Z.elegir(self.pregunta, 'compleja', {}, fallo=True, renovar=True)
            self.assertIsNone(modelo)
        self.red.assert_called_once()
        self.assertNotIn('CLAVE_FICTICIA', Z.ARCHIVO.read_text())

    def test_catalogo_reciente_no_se_vuelve_a_pedir(self):
        self.assertIsNotNone(Z.elegir(self.pregunta, 'compleja', {}, fallo=True, renovar=True)[0])
        self.red.assert_not_called()

    def test_el_chat_elige_externo_sin_que_el_usuario_nombre_modelo(self):
        self.red.side_effect = None
        self.red.return_value = {'choices':[{'message':{'content':'def suma(a, b): return a + b'}}]}
        h = [{'role':'user', 'content':self.pregunta}]; e = {}
        with patch.object(J, 'ejecutar_turno', side_effect=ConnectionError('Fallo local ficticio')) as local:
            t = J.responder_con_respaldo(h, lambda _:self.fail('Sin inferencia directa'), lambda _:False, e, mostrar=lambda _:None)
        self.assertEqual(local.call_count, 2)
        self.assertIn('Respondió: externo, deepseek-v4.1-flash-free', t)
        self.assertEqual(e['_ultima_decision_modelo']['regla'], 'externo_zen')
        self.red.assert_called_once()
        self.assertEqual(self.red.call_args.args[1]['messages'][-1]['content'], self.pregunta)

    def test_fallo_externo_tiene_un_solo_intento_local_posterior(self):
        self.red.side_effect = ConnectionError('Zen respondió HTTP 429.')
        h = [{'role':'user', 'content':self.pregunta}]
        with patch.object(J, 'ejecutar_turno', side_effect=ConnectionError('Fallo local ficticio')), \
             patch.object(J.IA, 'preguntar_ia', return_value={'ok':True, 'respuesta':'Respuesta local ficticia'}) as local:
            t = J.responder_con_respaldo(h, lambda _:None, lambda _:False, {}, mostrar=lambda _:None)
        local.assert_called_once_with(self.pregunta, C.MODELO_COTIDIANO)
        self.red.assert_called_once(); self.assertIn('Respuesta local ficticia', t)

    def test_exito_guarda_solo_metadatos_de_verificacion(self):
        Z.preguntar(self.pregunta, self.modelo, 'fallo local',
                    lambda *a, **k:{'choices':[{'message':{'content':'Respuesta ficticia para verificar.'}}]})
        e = Z.estado()
        self.assertEqual(e['ultima_respuesta_verificada']['modelo'], self.modelo['id'])
        self.assertNotIn(self.pregunta, Z.ARCHIVO.read_text())
        self.assertNotIn('Respuesta ficticia', Z.ARCHIVO.read_text())
        self.assertNotIn('CLAVE_FICTICIA', Z.ARCHIVO.read_text())


if __name__ == '__main__':
    unittest.main()
