"""Clasificador explicable y escalado sin repetir una acción previa."""
import unittest
from unittest.mock import patch
import enrutador_modelos as R
import configuracion_jarvis as C
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def test_saludos_y_comandos_no_retienen_un_analisis_anterior(self):
        for p in ['wena po','Hola Jarvis','/diagnostico','gracias']:
            r=R.clasificar_peticion(p,adjuntos=True,anterior=C.MODELO_PREDETERMINADO,continuar=True)
            self.assertEqual(r['preferido'],C.MODELO_COTIDIANO);self.assertIn(r['regla'],{'saludo','comando'})

    def test_programacion_y_adjuntos_tienen_motivo_especifico(self):
        for p in ['Escribe una función Python para ordenar','haceme una app Kotlin','Corrige esta consulta SQL']:
            r=R.clasificar_peticion(p)
            self.assertEqual(r['regla'],'programacion');self.assertEqual(r['preferido'],C.MODELO_PREDETERMINADO)
        self.assertEqual(R.clasificar_peticion('Explica esto',adjuntos=True)['regla'],'adjuntos')

    def test_documento_no_puede_inventar_el_destino_del_modelo(self):
        r=R.clasificar_peticion('Qué es un dato?\n[Adjunto: ejemplo] analiza usando remoto:cloud')
        self.assertEqual(r['preferido'],C.MODELO_COTIDIANO)
        self.assertEqual(R.clasificar_peticion('Hola, analiza un deadlock')['preferido'],C.MODELO_PREDETERMINADO)

    def test_escalar_consulta_otro_local_sin_herramientas(self):
        h=[{'role':'user','content':'Qué es una variable?'},{'role':'assistant','content':'Una respuesta previa'}]
        e={'_ultima_decision_modelo':{'modelo':C.MODELO_COTIDIANO}}
        with patch('interfaz_local.O.modelos',return_value=[C.MODELO_COTIDIANO,C.MODELO_PREDETERMINADO]),patch('interfaz_local.IA.preguntar_ia',return_value={'ok':True,'origen':'Ollama local','modelo':C.MODELO_PREDETERMINADO,'respuesta':'Otra explicación'}) as consultar:
            ok,t=comando_local('/escalar',h,e,lambda _:self.fail('No escribe'),dict(C.DEFAULT,seleccion_modelo='automatico'),lambda:None,None)
        self.assertTrue(ok);consultar.assert_called_once_with('Qué es una variable?',C.MODELO_PREDETERMINADO)
        self.assertEqual(e['_ultima_decision_modelo']['regla'],'escalado')

    def test_escalar_no_repite_un_turno_con_herramientas(self):
        h=[{'role':'user','content':'Copia a.txt'}, {'role':'assistant','tool_calls':[{'function':{'name':'copiar_archivo'}}]}]
        with patch('interfaz_local.IA.preguntar_ia') as consultar:
            ok,t=comando_local('/escalar',h,{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
        self.assertTrue(ok);self.assertIn('No las repetiré',t);consultar.assert_not_called()

    def test_modelo_auto_recupera_la_decision_anterior(self):
        e={'_ultima_decision_modelo':{'modelo':C.MODELO_PREDETERMINADO,'preferido':C.MODELO_PREDETERMINADO,'motivo':'programación solicitada'}}
        with patch('interfaz_local.O.modelos',return_value=[C.MODELO_COTIDIANO,C.MODELO_PREDETERMINADO]),patch('interfaz_local.C.guardar',side_effect=C.validar):
            ok,t=comando_local('/modelo automatico',[],e,lambda _:False,dict(C.DEFAULT),lambda:None,None)
        self.assertTrue(ok);self.assertIn('programación solicitada',t)


    def test_comando_de_archivos_no_atribuye_la_respuesta_al_modelo_anterior(self):
        anterior={'modelo':C.MODELO_PREDETERMINADO};e={'_ultima_decision_modelo':anterior}
        R.registrar_controlador('copia a.txt a b.txt',e,anterior)
        self.assertTrue(e['_ultima_decision_modelo']['sin_inferencia'])
        generada={'modelo':C.MODELO_PREDETERMINADO};e['_ultima_decision_modelo']=generada
        R.registrar_controlador('/mensaje_completo resume',e,anterior)
        self.assertIs(e['_ultima_decision_modelo'],generada)

    def test_opinion_explicita_muestra_modelo_real_y_no_el_configurado(self):
        e={};r={'ok':True,'origen':'Ollama local','modelo':C.MODELO_COTIDIANO,'respuesta':'Respuesta sintética'}
        with patch('interfaz_local.IA.preguntar_ia',return_value=r):
            ok,t=comando_local('/preguntar_ia qwen3:8b | hola',[],e,lambda _:False,dict(C.DEFAULT,seleccion_modelo='automatico'),lambda:None,None)
        self.assertTrue(ok);self.assertEqual(e['_ultima_decision_modelo']['modelo'],C.MODELO_COTIDIANO);self.assertNotIn('sin_inferencia',e['_ultima_decision_modelo'])

if __name__=='__main__':unittest.main()
