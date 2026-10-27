"""Regresiones de capacidades, ideas y contexto: clientes falsos, sin red real."""
import unittest
import json
from unittest.mock import patch
import jarvis_agente as J
from interfaz_local import comando_local
from lenguaje_jarvis import resumen_vocabulario


class EstadoFalso:
    def __init__(self,ok=True):self.ok=ok;self.llamadas=[]
    def llamar(self,n,a):
        self.llamadas.append(n)
        return {'ok':self.ok,'consultado':'2026-10-13T00:00:00+00:00'}


class Pruebas(unittest.TestCase):
    def local(self,p,cerebro):
        return comando_local(p,[],{},lambda _:self.fail('No debe pedir permiso'),J.AJUSTES,lambda:None,cerebro)

    def test_acceso_brain_se_comprueba_y_no_se_niega(self):
        for p in ('puedes ver mi segundo cerebro?','tienes acceso a mi Segundo Cerebro?','hola Jarvis, puedes consultar el Segundo Cerebro?'):
            c=EstadoFalso();ok,t=self.local(p,c)
            self.assertTrue(ok);self.assertIn('Sí.',t);self.assertEqual(c.llamadas,['consultar_estado_cerebro'])
            self.assertIn('12-10-2026 21:00:00',t)

    def test_no_afirma_conexion_cuando_falla(self):
        ok,t=self.local('puedes ver mi segundo cerebro?',EstadoFalso(False))
        self.assertTrue(ok);self.assertIn('no pude confirmar',t);self.assertNotIn('Sí.',t)

    def test_ideas_exactas_del_usuario_no_disculpan_ni_inventan_comando(self):
        ok,t=self.local('Jarvis dame ideas para mejorarte, la idea es trabajar en ti durante una hora',EstadoFalso())
        self.assertTrue(ok);self.assertIn('Interfaz',t);self.assertNotIn('/no_think',t);self.assertNotIn('interpreté mal',t)

    def test_ideas_sobre_interfaz_se_enfocan_en_interfaz(self):
        ok,t=self.local('Quiero ideas para mejorar tu interfaz; no estoy corrigiendo una palabra',EstadoFalso())
        self.assertTrue(ok);self.assertIn('Interfaz y lectura',t);self.assertNotIn('Comprensión del español chileno',t)

    def test_glosario_selecciona_solo_expresiones_pertinentes(self):
        t=resumen_vocabulario('tengo un cacho, hazlo al tiro')
        self.assertIn('cacho',t);self.assertLess(len(t),1000)
        self.assertEqual(resumen_vocabulario('hola'), '')
        self.assertNotIn('/no_think',J.prompt_para_turno('hola'))

    def test_contexto_reserva_espacio_sin_borrar_sesion(self):
        h=[{'role':'system','content':J.SISTEMA}]
        for _ in range(18):h.extend([{'role':'user','content':'Consulta anterior. '*100},{'role':'assistant','content':'Respuesta anterior. '*100}])
        h.append({'role':'user','content':'Hola Jarvis'})
        original=len(h)
        with patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'Hola'})}}) as solicitar:
            J.enviar_a_ollama(h)
        cuerpo=solicitar.call_args.args[1]
        self.assertEqual(cuerpo['tools'],[]);self.assertEqual(cuerpo['messages'][-1]['content'],'Hola Jarvis')
        self.assertLess(len(cuerpo['messages']),len(h));self.assertEqual(len(h),original)

    def test_propuesta_literal_conserva_lineas_ajenas(self):
        args={'ruta':'ejemplo.txt','contenido_nuevo':'Cuatro\n'}
        h=[{'role':'user','content':'Prepara una propuesta para cambiar Dos por Cuatro. No escribas nada.'}]
        with patch.object(J.L,'_resolver',return_value='archivo'),patch.object(J.E,'_leer_texto_estricto',return_value=b'Uno\nDos\n'):
            segura=J.propuesta_literal_segura(args,h)
        self.assertEqual(segura['contenido_nuevo'],'Uno\nCuatro\n');self.assertEqual(args['contenido_nuevo'],'Cuatro\n')

    def test_no_reinterpreta_edicion_ambigua_o_multiple(self):
        args={'ruta':'ejemplo.txt','contenido_nuevo':'Cambio completo'}
        for pedido in ('Cambia Dos por Cuatro y cambia Uno por Cinco','Cambia Dos por Cuatro y elimina Uno','Mejora todo el documento'):
            with patch.object(J.E,'_leer_texto_estricto') as leer:
                self.assertEqual(J.propuesta_literal_segura(args,[{'role':'user','content':pedido}]),args)
                leer.assert_not_called()

    def test_ultimo_recuerdo_con_proyecto_no_lista_estructura(self):
        ok,t=self.local('Muéstrame el último recuerdo que guardó Segundo Cerebro y su proyecto',EstadoFalso())
        self.assertFalse(ok);self.assertEqual(t,'')
        intencion=J.interpretar('Muéstrame el último recuerdo que guardó Segundo Cerebro y su proyecto',{})
        self.assertEqual(intencion.nombre,'consultar_ultimo_recuerdo')

    def test_definicion_conocida_no_inventa_significados(self):
        ok,t=self.local('Tengo un cacho con la memoria. ¿Qué significa cacho en Chile?',EstadoFalso())
        self.assertTrue(ok);self.assertIn('problema o enredo',t);self.assertNotIn('conseguir',t)
        ok,t=self.local('Qué quiere decir cachai?',EstadoFalso())
        self.assertTrue(ok);self.assertIn('entiendes',t)


if __name__=='__main__':unittest.main()
