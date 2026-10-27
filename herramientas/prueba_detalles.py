"""Detalle fresco, navegación directa y comprobantes de acciones."""
import unittest
from unittest.mock import patch
import jarvis_agente as J
from interfaz_jarvis import comando
from lenguaje_jarvis import interpretar


class Pruebas(unittest.TestCase):
    def test_ver_completo_sin_recortar_ni_cambiar_referencias(self):
        state={'_lista_memorias':{6:106,7:107},'_pagina_memorias':{'desplazamiento':5}}
        contenido='contenido completo '*200
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[{'id':106,'titulo':'T','contenido':contenido,'proyecto':'Jarvis','creado':'2026-10-12T05:00:00Z'}]}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:self.fail('Es lectura'),state)
            handled,texto=comando('/ver 6',[],state,ejecutar,'s')
            self.assertTrue(handled);self.assertIn(contenido,texto)
            self.assertIn('02:00:00 (Chile)',texto)
            llamar.assert_called_once_with('consultar_memoria',{'id_memoria':106})
            self.assertEqual(state['_lista_memorias'],{6:106,7:107})
            self.assertEqual(state['_pagina_memorias']['desplazamiento'],5)

    def test_numero_no_visible_o_recuerdo_borrado(self):
        with patch.object(J.CEREBRO,'llamar') as llamar:
            r=J.ejecutar_herramienta('ver_recuerdo',{'numero_recuerdo':2},lambda _:False,{})
            self.assertFalse(r['ok']);llamar.assert_not_called()
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[]}):
            self.assertFalse(J.ejecutar_herramienta('ver_recuerdo',{'numero_recuerdo':2},lambda _:False,{'_lista_memorias':{2:100}})['ok'])

    def test_saltar_pagina_estable_y_limites(self):
        state={};h=[];rows=[{'id':n,'contenido':'dato','titulo':str(n)} for n in range(1,14)]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':rows}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            comando('/recuerdos',h,state,ejecutar,'s')
            texto=comando('/pagina 3',h,state,ejecutar,'s')[1]
            self.assertIn('Página 3 de 3',texto)
            self.assertEqual(list(state['_lista_memorias'].values()),[11,12,13])
            self.assertIn('entre 1 y 3',comando('/pagina 4',h,state,ejecutar,'s')[1])
            self.assertEqual(list(state['_lista_memorias'].values()),[11,12,13])
            comando('/pagina 1',h,state,ejecutar,'s')
            self.assertEqual(llamar.call_count,1)

    def test_comprobante_denegado_no_se_convierte_en_exito(self):
        state={}
        J.ejecutar_herramienta('crear_proyecto',{'proyecto':'Jarvis'},lambda _:False,state)
        texto=comando('/ultima_accion',[],state,None,'s')[1]
        self.assertIn('no autorizó',texto)
        self.assertFalse(state['_ultima_accion']['ok'])

    def test_comprobante_no_se_sobrescribe_con_lecturas(self):
        state={}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'estado':'creado','proyecto':'Jarvis'}),patch.object(J.L,'_registrar'):
            J.ejecutar_herramienta('crear_proyecto',{'proyecto':'Jarvis'},lambda _:True,state)
        anterior=dict(state['_ultima_accion'])
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'proyectos':[]}):
            J.ejecutar_herramienta('listar_proyectos',{},lambda _:False,state)
        self.assertEqual(state['_ultima_accion'],anterior)
        self.assertIn('creado',comando('qué hiciste',[],state,None,'s')[1])

    def test_frases_y_referencia_de_pagina(self):
        state={'_lista_memorias':{6:106,7:107}}
        self.assertEqual(interpretar('muéstrame el segundo completo',state).argumentos,{'numero_recuerdo':7})
        self.assertEqual(interpretar('ve a la página dos',state).argumentos,{'pagina':2})
        self.assertEqual(interpretar('muestra la última acción',state).nombre,'/ultima_accion')
        self.assertEqual(interpretar('muéstrame el tercero completo',state).nombre,'aclarar')
        self.assertIsNone(interpretar('muestra dos',state))

    def test_nuevo_borra_comprobante_y_sin_historial_lo_informa(self):
        self.assertIn('no hay',comando('/ultima_accion',[],{},None,'s')[1])
        state={'_ultima_accion':{'ok':True,'detalle':'creado','fecha':'hoy'}}
        comando('/nuevo',[],state,None,'s')
        self.assertNotIn('_ultima_accion',state)


if __name__=='__main__':unittest.main()
