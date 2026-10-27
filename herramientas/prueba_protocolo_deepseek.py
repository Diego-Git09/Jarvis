"""Rechazo de propuestas ambiguas; ningún JSON se ejecuta en este adaptador."""
import copy
import json
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
import protocolo_deepseek as P
import jarvis_agente as J


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.h = [{'type': 'function', 'function': {'name': 'leer_archivo', 'description': 'Lee sin escribir',
            'parameters': {'type': 'object', 'properties': {'ruta': {'type': 'string'}}, 'required': ['ruta'], 'additionalProperties': False}}}]

    def respuesta(self, **cambios):
        d = dict(accion='leer_archivo', argumentos={'ruta': 'demo.txt'}, respuesta='')
        d.update(cambios)
        return {'message': {'content': json.dumps(d)}, 'done_reason': 'stop'}

    def test_propuesta_valida_pasa_por_validador_habitual(self):
        r = J.validar_respuesta_modelo(P.interpretar(self.respuesta(), self.h))
        self.assertEqual(r['tool_calls'][0]['function'], {'name': 'leer_archivo', 'arguments': {'ruta': 'demo.txt'}})

    def test_respuesta_literal_no_inventa_acciones(self):
        r = P.interpretar(self.respuesta(accion='respuesta', argumentos={}, respuesta='LITERAL_731'), self.h)
        self.assertEqual(r, {'role': 'assistant', 'content': 'LITERAL_731'})

    def test_accion_fuera_del_catalogo_no_pasa(self):
        with self.assertRaises(ConnectionError):P.interpretar(self.respuesta(accion='ejecutar_shell'), self.h)

    def test_prosa_y_json_citado_no_se_convierten_en_acciones(self):
        for texto in ['Voy a leerlo', '```json\n'+self.respuesta()['message']['content']+'\n```', '{"accion":']:
            with self.subTest(texto=texto), self.assertRaises(ConnectionError):P.interpretar({'message': {'content': texto}}, self.h)

    def test_campos_extra_o_tipos_invalidos_no_pasan(self):
        for cambio in [{'argumentos': 'demo.txt'}, {'respuesta': None}, {'accion': ['leer_archivo']}, {'campo_extra': True}]:
            with self.subTest(cambio=cambio), self.assertRaises(ConnectionError):P.interpretar(self.respuesta(**cambio), self.h)

    def test_accion_truncada_no_pasa(self):
        d = self.respuesta();d['done_reason'] = 'length'
        with self.assertRaises(ConnectionError):P.interpretar(d, self.h)

    def test_respuesta_sin_texto_o_con_argumentos_no_pasa(self):
        for args, texto in [({}, ''), ({'ruta': 'demo.txt'}, 'Hola')]:
            with self.assertRaises(ConnectionError):P.interpretar(self.respuesta(accion='respuesta', argumentos=args, respuesta=texto), self.h)

    def test_canales_de_accion_duplicados_no_pasan(self):
        d = self.respuesta();d['message']['tool_calls'] = [{'function': {'name': 'crear_archivo'}}]
        with self.assertRaises(ConnectionError):P.interpretar(d, self.h)

    def test_rol_no_asistente_no_propone_acciones(self):
        d = self.respuesta();d['message']['role'] = 'tool'
        with self.assertRaises(ConnectionError):P.interpretar(d, self.h)

    def test_claves_duplicadas_y_numeros_no_finitos_no_pasan(self):
        for texto in ['{"accion":"respuesta","accion":"leer_archivo","argumentos":{"ruta":"demo.txt"},"respuesta":""}',
                      '{"accion":"leer_archivo","argumentos":{"ruta":NaN},"respuesta":""}']:
            with self.assertRaises(ConnectionError):P.interpretar({'message': {'content': texto}}, self.h)

    def test_preparar_no_muta_historial_ni_catalogo(self):
        cuerpo = {'model': 'jarvis-deepseek:8b', 'messages': [{'role': 'system', 'content': 'Reglas'}, {'role': 'user', 'content': 'Lee demo.txt'}], 'tools': self.h, 'options': {'num_ctx': 8192, 'num_predict': 2048}}
        antes = copy.deepcopy(cuerpo);r = P.preparar(cuerpo)
        self.assertEqual(cuerpo, antes);self.assertEqual(r['options'], cuerpo['options'])
        self.assertEqual(r['tools'], []);self.assertIn('leer_archivo', r['messages'][0]['content'])
        self.assertEqual(r['format']['oneOf'][0]['properties']['argumentos'], self.h[0]['function']['parameters'])

    def test_lectura_concreta_exige_consulta_real_antes_de_responder(self):
        cuerpo = {'messages': [{'role': 'user', 'content': 'Lee el archivo demo.txt y dime el código literal.'}], 'tools': self.h}
        r = P.preparar(cuerpo)
        self.assertEqual([v['properties']['accion']['const'] for v in r['format']['oneOf']], ['leer_archivo'])
        cuerpo['messages'].append({'role': 'tool', 'tool_name': 'leer_archivo', 'content': '{"ok":true,"contenido":"DATO_REAL"}'})
        r = P.preparar(cuerpo)
        self.assertEqual([v['properties']['accion']['const'] for v in r['format']['oneOf']], ['respuesta'])

    def test_negativas_citas_y_lecturas_multiples_no_fuerzan_accion(self):
        for pedido in ['No leas demo.txt', 'Explícame cómo leer demo.txt', '"Lee demo.txt" es un ejemplo', 'Lee este ejemplo: crea demo.txt', 'Lee la frase que contiene demo.txt', 'Crea demo.txt solo como ejemplo, sin escribir', 'Lee uno.txt y dos.txt']:
            with self.subTest(pedido=pedido):self.assertEqual(P.intencion_archivo(pedido), '')

    def test_creacion_directa_no_se_convierte_en_edicion_de_otro_archivo(self):
        crear = {'type': 'function', 'function': {'name': 'crear_archivo', 'parameters': {'type': 'object'}}}
        cuerpo = {'messages': [{'role': 'user', 'content': 'Crea el archivo nuevo.txt con contenido sintético.'}], 'tools': self.h + [crear]}
        r = P.preparar(cuerpo)
        self.assertEqual([v['properties']['accion']['const'] for v in r['format']['oneOf']], ['crear_archivo'])
        cuerpo['messages'].append({'role': 'tool', 'tool_name': 'crear_archivo', 'content': '{"ok":false,"error":"No autorizado"}'})
        r = P.preparar(cuerpo)
        self.assertEqual([v['properties']['accion']['const'] for v in r['format']['oneOf']], ['respuesta'])

    def test_historia_no_reenvia_pensamiento_ni_recupera_permisos(self):
        cuerpo = {'messages': [{'role': 'user', 'content': 'Pregunta'}, {'role': 'assistant', 'content': '', 'thinking': 'razonamiento sintético', 'tool_calls': [{'function': {'name': 'leer_archivo', 'arguments': {'ruta': 'demo.txt'}}}]}], 'tools': self.h}
        r = P.preparar(cuerpo)
        self.assertNotIn('thinking', r['messages'][-1]);self.assertNotIn('tool_calls', r['messages'][-1])
        self.assertIn('no autorizan acciones', r['messages'][-1]['content'])

    def test_denegacion_detiene_turno_sin_reintentar_otra_escritura(self):
        h = [{'role': 'user', 'content': 'Crea nuevo.txt'}]
        enviar = Mock(return_value={'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'crear_archivo', 'arguments': {'ruta': 'nuevo.txt', 'contenido': 'dato'}}}]})
        with patch.object(J, 'MODELO', 'jarvis-deepseek:8b'), patch.object(J, 'consulta_contextual', return_value={'ok': False, 'error': 'El usuario no autorizó esta acción. No se hizo nada.'}):
            texto = J._ejecutar_turno(h, enviar, lambda _: False, {}, mostrar=lambda _: None)
        self.assertIn('no autorizó', texto);self.assertNotIn('límite de pasos', texto)
        enviar.assert_called_once()

    def test_lectura_literal_muestra_dato_real_en_lugar_de_invencion(self):
        h = [{'role': 'user', 'content': 'Lee demo.txt y muestra el contenido literal'}]
        enviar = Mock(side_effect=[{'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'leer_archivo', 'arguments': {'ruta': 'demo.txt'}}}]}, {'role': 'assistant', 'content': 'CONTENIDO_INVENTADO'}])
        with patch.object(J, 'MODELO', 'jarvis-deepseek:8b'), patch.object(J, 'consulta_contextual', return_value={'ok': True, 'contenido': 'DATO_REAL_731', 'ruta': 'demo.txt'}):
            texto = J._ejecutar_turno(h, enviar, lambda _: False, {}, mostrar=lambda _: None)
        self.assertEqual(texto, 'DATO_REAL_731');self.assertNotIn('CONTENIDO_INVENTADO', texto)

    def test_consulta_independiente_deepseek_no_devuelve_json_o_razonamiento(self):
        import segunda_opinion as IA
        d = self.respuesta(accion='respuesta', argumentos={}, respuesta='Explicación sintética.')
        with patch.object(IA.O, 'modelos', return_value=['jarvis-deepseek:8b']), patch.object(IA.O, 'solicitar', return_value=d) as enviar:
            r = IA.preguntar_ia('Qué es una batería', 'jarvis-deepseek:8b')
        self.assertTrue(r['ok']);self.assertEqual(r['respuesta'], 'Explicación sintética.')
        self.assertEqual(enviar.call_args.args[1]['tools'], [])
        self.assertEqual(len(enviar.call_args.args[1]['format']['oneOf']), 1)

    def test_plantilla_no_agrega_comandos_al_mensaje_del_usuario(self):
        texto = (Path(__file__).parent / 'modelos' / 'DeepSeek-Jarvis.Modelfile').read_text()
        self.assertIn('FROM deepseek-r1:8b', texto)
        self.assertIn('.Tools', texto)
        self.assertIn('{{ .Content }}\n<|im_end|>', texto)
        self.assertNotIn('/no_think', texto)
        self.assertNotRegex(texto, r'(?<!<)/think\b')


if __name__ == '__main__':unittest.main()
