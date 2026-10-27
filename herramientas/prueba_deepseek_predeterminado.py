"""Modelo principal local y rutas DeepSeek, sin modelos, nube o llavero reales."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import auxiliar_deepseek as AUX
import configuracion_jarvis as CONFIG
import coordinador_deepseek as COORD
import jarvis_agente as J
import segunda_opinion as IA
import estado_ia as ESTADO
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def test_predeterminado_y_perfiles_generales_son_deepseek_local(self):
        self.assertEqual(CONFIG.DEFAULT['modelo'], 'jarvis-deepseek:8b')
        for perfil in ('equilibrado', 'maximo'):
            self.assertEqual(CONFIG.PERFILES[perfil]['modelo'], 'jarvis-deepseek:8b')
        self.assertEqual(CONFIG.DEFAULT['ollama_url'], 'http://127.0.0.1:11434')
        self.assertEqual(CONFIG.DEFAULT['num_ctx'], 8192)

    def test_preferencia_se_conserva_al_reabrir_sin_cambiar_otros_ajustes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'configuracion.json'
            ajustes = dict(CONFIG.DEFAULT, modo='detallado', timeout_modelo=75)
            CONFIG.guardar(ajustes, p)
            cargados, aviso = CONFIG.leer(p)
            self.assertEqual(cargados, ajustes)
            self.assertEqual(cargados['modelo'], 'jarvis-deepseek:8b')
            self.assertFalse(aviso)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_principal_no_se_consulta_de_nuevo_como_auxiliar(self):
        with patch.object(COORD, 'habilitado', return_value=True), patch.object(AUX, 'analizar') as analizar:
            r = COORD.preparar_analisis('Analiza esta arquitectura', modelo_principal='jarvis-deepseek:8b')
            self.assertFalse(r['usado'])
            self.assertEqual(r['estado'], 'modelo_principal')
            analizar.assert_not_called()

    def test_auxiliar_se_mantiene_si_usuario_elige_otro_modelo(self):
        with patch.object(COORD, 'habilitado', return_value=True), patch.object(AUX, 'analizar', return_value={'usado': True, 'analisis': 'Dato sintético.'}) as analizar:
            r = COORD.preparar_analisis('Analiza esta arquitectura', modelo_principal='qwen3:8b')
            self.assertTrue(r['usado'])
            analizar.assert_called_once()

    def test_pregunta_natural_deepseek_usa_ollama_y_preserva_texto(self):
        for pedido in ('Jarvis, pregúntale a DeepSeek cómo funciona una batería', 'pregúntale a DeepSeek local cómo funciona una batería'):
            with self.subTest(pedido=pedido), patch.object(IA, 'preguntar_ia', return_value={'ok': True, 'modelo': 'jarvis-deepseek:8b', 'origen': 'Ollama local', 'respuesta': 'Dato sintético.'}) as local, patch.object(IA, 'preguntar_externa') as nube:
                hecho, texto = comando_local(pedido, [], {}, lambda _: self.fail('Una consulta local no pide permiso de nube'), dict(CONFIG.DEFAULT), lambda: None, None)
                self.assertTrue(hecho)
                self.assertIn('Ollama local', texto)
                local.assert_called_once_with('cómo funciona una batería', 'jarvis-deepseek:8b')
                nube.assert_not_called()

    def test_deepseek_no_instalado_no_recurre_a_una_api(self):
        with patch.object(IA.O, 'modelos', return_value=['qwen3:8b']), patch.object(IA, 'preguntar_externa') as nube, patch.object(IA.O, 'solicitar') as enviar:
            hecho, texto = comando_local('pregúntale a DeepSeek qué es SQL', [], {}, lambda _: False, dict(CONFIG.DEFAULT), lambda: None, None)
            self.assertTrue(hecho)
            self.assertIn('no está instalado', texto)
            nube.assert_not_called()
            enviar.assert_not_called()

    def test_api_deepseek_sigue_requiriendo_peticion_externa_explicita(self):
        with patch.object(IA, 'preguntar_externa', return_value={'ok': False, 'error': 'No configurada'}) as nube, patch.object(IA, 'preguntar_ia') as local:
            hecho,texto=comando_local('/ia_externa DeepSeek | pregunta sintética', [], {}, lambda _: False, dict(CONFIG.DEFAULT), lambda: None, None)
            self.assertTrue(hecho);self.assertIn('bloqueadas',texto)
            nube.assert_not_called()
            local.assert_not_called()

    def test_payload_principal_conserva_herramientas_y_limites(self):
        h = [{'role': 'system', 'content': 'Reglas sintéticas.'}, {'role': 'user', 'content': 'Hola'}]
        with patch.object(J, 'MODELO', 'jarvis-deepseek:8b'), patch.object(J.O, 'solicitar', return_value={'message': {'role': 'assistant', 'content': '{"accion":"respuesta","argumentos":{},"respuesta":"Hola"}'}}) as enviar:
            J.enviar_a_ollama(h)
            cuerpo = enviar.call_args.args[1]
            self.assertEqual(cuerpo['model'], 'jarvis-deepseek:8b')
            self.assertEqual(cuerpo['tools'], [])
            self.assertIn('format', cuerpo)
            self.assertFalse(cuerpo['think'])
            self.assertEqual(cuerpo['options']['num_ctx'], J.AJUSTES['num_ctx'])

    def test_estado_local_usa_configuracion_actual_y_respeta_presupuesto(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            with patch.object(ESTADO, 'TRABAJO', p), patch.object(ESTADO, 'RESUMEN', p / 'estado.md'), patch.object(ESTADO, 'leer_config', return_value=(dict(CONFIG.DEFAULT), '')):
                texto = ESTADO.generar()
                self.assertIn('Modelo activo: jarvis-deepseek:8b en Ollama', texto)
                self.assertLessEqual(len(texto), 6200)


if __name__ == '__main__':
    unittest.main()
