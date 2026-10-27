"""Navegación y contexto de proyecto; nunca modifica memorias reales."""
import unittest
from unittest.mock import patch
import jarvis_agente as J
from interfaz_jarvis import comando
from lenguaje_jarvis import interpretar, seleccion


class Pruebas(unittest.TestCase):
    def test_anterior_conserva_la_misma_lista(self):
        rows=[{'id':n,'titulo':str(n),'contenido':'dato','proyecto':'Jarvis'} for n in range(1,13)]
        h=[];state={}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':rows}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            primera=comando('/recuerdos',h,state,ejecutar,'s')[1]
            comando('/mas',h,state,ejecutar,'s')
            self.assertEqual(state['_pagina_memorias']['desplazamiento'],5)
            llamar.return_value={'ok':True,'memorias':[{'id':99,'contenido':'nuevo'}]+rows}
            self.assertEqual(comando('/anterior',h,state,ejecutar,'s')[1],primera)
            self.assertEqual(llamar.call_count,1)
            self.assertIn('primera',comando('/anterior',h,state,ejecutar,'s')[1])

    def test_actualizar_conserva_filtro_orden_vuelve_al_inicio(self):
        state={};h=[]
        rows=[{'id':n,'titulo':str(n),'contenido':'dato','proyecto':'sin_clasificar','creado':f'2026-10-12T0{n}:00:00Z'} for n in range(1,8)]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':rows}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            comando('recuerdos sin clasificar ordenados del mas antiguo al mas nuevo (por fecha)',h,state,ejecutar,'s')
            comando('/mas',h,state,ejecutar,'s')
            comando('/actualizar',h,state,ejecutar,'s')
            self.assertEqual(llamar.call_count,2)
            llamar.assert_called_with('listar_memorias',{'proyecto':'sin_clasificar','orden':'antiguos'})
            self.assertEqual(state['_pagina_memorias']['desplazamiento'],0)

    def test_ultimo_exclusiones_y_fuera_de_pagina(self):
        state={'_lista_memorias':{6:106,7:107,8:108,9:109}}
        self.assertEqual(seleccion('ultimo',state),[9])
        self.assertEqual(seleccion('el penultimo',state),[8])
        self.assertEqual(seleccion('todos menos el segundo',state),[6,8,9])
        self.assertEqual(seleccion('todos excepto ocho y nueve',state),[6,7])
        self.assertIsNone(seleccion('todos menos uno',state))
        self.assertEqual(interpretar('pasa el último a Jarvis',state).argumentos['numeros'],[9])

    def test_proyecto_activo_filtra_y_quita_referencias_anteriores(self):
        state={'_lista_memorias':{1:100},'_memorias':{100:{'contenido':'viejo'}}};h=[]
        with patch.object(J.CEREBRO,'llamar',side_effect=[{'ok':True,'proyectos':[{'proyecto':'Jarvis','total':1}]},
             {'ok':True,'memorias':[{'id':2,'contenido':'dato','proyecto':'Jarvis'}]}]) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            self.assertTrue(comando('trabajemos en jarvis',h,state,ejecutar,'s')[0])
            self.assertEqual(state['_proyecto_activo'],'Jarvis')
            self.assertNotIn('_lista_memorias',state)
            comando('/recuerdos',h,state,ejecutar,'s')
            llamar.assert_called_with('listar_memorias',{'proyecto':'Jarvis'})
            self.assertEqual(interpretar('busca recuerdos sobre Qwen',state).argumentos['proyecto'],'Jarvis')
            comando('/todos',h,state,ejecutar,'s')
            self.assertNotIn('_proyecto_activo',state)
            self.assertNotIn('_lista_memorias',state)

    def test_proyecto_inexistente_no_cambia_el_activo(self):
        state={'_proyecto_activo':'Jarvis'}
        def ejecutar(*_):return {'ok':True,'proyectos':[{'proyecto':'Jarvis','total':1}]}
        _,texto=comando('/proyecto inexistente',[],state,ejecutar,'s')
        self.assertIn('no existe',texto);self.assertEqual(state['_proyecto_activo'],'Jarvis')

    def test_lectura_explicita_puede_usar_otro_proyecto(self):
        state={'_proyecto_activo':'Jarvis'}
        self.assertEqual(interpretar('muestra el proyecto personal',state).argumentos['proyecto'],'personal')
        self.assertEqual(interpretar('mueve el primero a estudios',{'_proyecto_activo':'Jarvis','_lista_memorias':{1:1}}).argumentos['proyecto'],'estudios')
        self.assertIsNone(interpretar('mueve el primero',state))

    def test_aliases_y_nuevo_limpian_contexto(self):
        self.assertEqual(interpretar('atrás',{}).nombre,'/anterior')
        self.assertEqual(interpretar('refresca el listado',{}).nombre,'/actualizar')
        state={'_proyecto_activo':'Jarvis'}
        comando('/nuevo',[],state,None,'s')
        self.assertEqual(state,{})


if __name__=='__main__':unittest.main()
