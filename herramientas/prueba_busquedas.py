"""Búsqueda paginada y tamaño configurable sin cambios de memorias reales."""
import unittest
from unittest.mock import patch
import jarvis_agente as J
from interfaz_jarvis import comando


def filas(n):
    return [{'id':i,'titulo':f'Qwen {i}','contenido':'Qwen local','proyecto':'Jarvis'} for i in range(1,n+1)]


class Pruebas(unittest.TestCase):
    def test_busqueda_mas_anterior_y_actualizar(self):
        state={'_proyecto_activo':'Jarvis'};h=[]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':filas(12)}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            primera=comando('/buscar Qwen',h,state,ejecutar,'s')[1]
            self.assertIn('Resultados para «Qwen»',primera)
            self.assertIn('Página 1 de 3',primera)
            segunda=comando('/mas',h,state,ejecutar,'s')[1]
            self.assertIn('6. Qwen 6',segunda)
            self.assertNotIn('del más nuevo',segunda)
            self.assertEqual(comando('/anterior',h,state,ejecutar,'s')[1],primera)
            self.assertEqual(llamar.call_count,1)
            comando('/actualizar',h,state,ejecutar,'s')
            self.assertEqual(llamar.call_count,2)
            llamar.assert_called_with('buscar_memoria',{'consulta':'Qwen','proyecto':'Jarvis'})

    def test_tamano_20_y_navegacion(self):
        state={};h=[]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':filas(25)}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            comando('/tamano 20',h,state,ejecutar,'s')
            primera=comando('/recuerdos',h,state,ejecutar,'s')[1]
            self.assertIn('Página 1 de 2',primera)
            self.assertEqual(len(state['_lista_memorias']),20)
            segunda=comando('/mas',h,state,ejecutar,'s')[1]
            self.assertIn('21. Qwen 21',segunda)
            self.assertEqual(list(state['_lista_memorias']),[21,22,23,24,25])
            self.assertEqual(comando('/anterior',h,state,ejecutar,'s')[1],primera)
            self.assertEqual(llamar.call_count,1)

    def test_tamano_1_puede_ir_a_pagina_50(self):
        state={'_tamano_pagina':1};h=[]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':filas(50)}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            comando('/recuerdos',h,state,ejecutar,'s')
            texto=comando('/pagina 50',h,state,ejecutar,'s')[1]
            self.assertIn('Página 50 de 50',texto)
            self.assertEqual(state['_lista_memorias'],{50:50})
            self.assertEqual(llamar.call_count,1)

    def test_cambiar_tamano_limpia_referencias(self):
        state={'_lista_memorias':{1:100},'_memorias':{100:{}},'_pagina_memorias':{},'_proyecto_activo':'Jarvis'}
        comando('/tamano 10',[],state,None,'s')
        self.assertNotIn('_lista_memorias',state)
        self.assertEqual(state['_tamano_pagina'],10)
        self.assertEqual(state['_proyecto_activo'],'Jarvis')
        antes=dict(state)
        self.assertIn('entre',comando('/tamano 21',[],state,None,'s')[1])
        self.assertEqual(state,antes)

    def test_semantica_limite_y_filtro(self):
        state={'_proyecto_activo':'Jarvis'}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':filas(3)}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            texto=comando('/similares asistente local',[],state,ejecutar,'s')[1]
            llamar.assert_called_once_with('buscar_memoria_semantica',{'consulta':'asistente local','proyecto':'Jarvis','limite':5,'incluir_personal':False})
            self.assertIn('asistente local',texto)
            self.assertEqual(state['_pagina_memorias']['siguiente_desplazamiento'],None)

    def test_sin_resultados_no_deja_seleccion_anterior(self):
        state={'_lista_memorias':{1:100}}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[]}):
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            self.assertIn('No hay',comando('/buscar inexistente',[],state,ejecutar,'s')[1])
            self.assertEqual(state['_lista_memorias'],{})

    def test_frase_tamano_y_busqueda_vacia(self):
        state={}
        self.assertTrue(comando('muestra diez recuerdos por página',[],state,None,'s')[0])
        self.assertEqual(state['_tamano_pagina'],10)
        self.assertIn('seguido',comando('/buscar',[],state,None,'s')[1])
        self.assertIn('seguido',comando('/similares',[],state,None,'s')[1])


if __name__=='__main__':unittest.main()
