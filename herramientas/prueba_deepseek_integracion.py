"""Auxiliar opcional local: pruebas de contrato sin descargar ni ejecutar modelos."""
import os
import unittest
from unittest.mock import patch

import auxiliar_deepseek as A
import coordinador_deepseek as C
import control_deepseek as D
import enrutador_modelos as E


class Pruebas(unittest.TestCase):
    def test_auxiliar_desactivado_no_infiere(self):
        with patch.dict(os.environ,{'JARVIS_DEEPSEEK':'0'}),patch.object(A,'analizar') as enviar:
            self.assertEqual(C.preparar_analisis('Analiza esta arquitectura')['estado'],'desactivado')
            enviar.assert_not_called()

    def test_permiso_de_contexto_no_se_infiere_del_vocabulario(self):
        with patch.dict(os.environ,{'JARVIS_DEEPSEEK':'1'}),patch.object(A,'analizar') as enviar:
            self.assertEqual(C.preparar_analisis('Analiza mis documentos',permitido=False)['estado'],'omitido');enviar.assert_not_called()

    def test_pregunta_simple_no_activa_auxiliar(self):
        self.assertFalse(E.decidir_modelo('hola')['usar_deepseek'])

    def test_modelo_elegido_local(self):
        self.assertEqual(E.decidir_modelo('Compara estas arquitecturas')['modelo_auxiliar'],'jarvis-deepseek:8b')

    def test_transporte_compartido_y_sin_herramientas(self):
        with patch.object(A.O,'BASE','http://127.0.0.1:11434'),patch.object(A.O,'solicitar',return_value={'message':{'content':'Conclusión breve.'}}) as enviar:
            self.assertTrue(A.analizar('Analiza la estrategia',timeout=90)['usado'])
            args,kw=enviar.call_args
            self.assertEqual(args[0],'/api/chat');self.assertEqual(args[1]['model'],'jarvis-deepseek:8b');self.assertNotIn('tools',args[1]);self.assertEqual(kw['timeout'],30)

    def test_servidor_remoto_no_recibe_auxiliar(self):
        with patch.object(A.O,'BASE','http://otro-equipo:11434'),patch.object(A.O,'solicitar') as enviar:
            self.assertFalse(A.analizar('Analiza esta estrategia')['usado']);enviar.assert_not_called()

    def test_secretos_redactados_antes_de_enviar(self):
        with patch.object(A.O,'BASE','http://localhost:11434'),patch.object(A.O,'solicitar',return_value={'message':{'content':'Análisis final.'}}) as enviar:
            A.analizar('Analiza esta estrategia api_key=clave-ficticia','password=otra-clave-ficticia')
            self.assertNotIn('clave-ficticia',str(enviar.call_args))

    def test_errores_auxiliar_no_se_presentan_como_respuesta(self):
        with patch.object(A.O,'BASE','http://localhost:11434'),patch.object(A.O,'solicitar',side_effect=ConnectionError('Fallo sintético')):
            r=A.analizar('Analiza la estrategia');self.assertFalse(r['usado']);self.assertEqual(r['analisis'],'')

    def test_respuesta_vacia_no_se_utiliza(self):
        with patch.object(A.O,'BASE','http://localhost:11434'),patch.object(A.O,'solicitar',return_value={'message':{'content':''}}):
            self.assertFalse(A.analizar('Analiza la estrategia')['usado'])

    def test_coordinador_acota_salida(self):
        with patch.dict(os.environ,{'JARVIS_DEEPSEEK':'1'}),patch.object(A,'analizar',return_value={'usado':True,'analisis':'dato '*1000}):
            r=C.preparar_analisis('Analiza la estrategia');self.assertEqual(r['estado'],'utilizado');self.assertLessEqual(len(r['analisis']),D.limite_analisis())

    def test_contexto_no_textual_se_rechaza(self):
        with patch.object(A.O,'solicitar') as enviar:
            self.assertFalse(A.analizar(None)['usado']);self.assertFalse(A.analizar('Analiza',contexto={})['usado']);enviar.assert_not_called()


if __name__=='__main__':unittest.main()
