"""Regresiones de comandos, paginación, contexto y ejecución repetida."""
import json
import unittest
from unittest.mock import patch
import jarvis_agente as J
from interfaz_jarvis import comando, renderizar


class Pruebas(unittest.TestCase):
    def test_comandos_ayuda_y_nuevo_no_llaman_modelo(self):
        h=[{'role':'system','content':'s'},{'role':'user','content':'x'}];state={'_memorias':{1:{'contenido':'x'}}}
        def prohibido(*_): self.fail('No debe usar herramientas')
        self.assertIn('/mas',comando('/ayuda',h,state,prohibido,'s')[1])
        self.assertTrue(comando('/nuevo',h,state,prohibido,'s')[0])
        self.assertEqual(h,[{'role':'system','content':'s'}]);self.assertEqual(state,{})

    def test_mas_sin_pagina_o_al_final_no_consulta(self):
        with patch.object(J.CEREBRO,'llamar') as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,{})
            self.assertIn('/recuerdos',comando('/mas',[],{},ejecutar,'s')[1])
            self.assertIn('final',comando('/mas',[],{'_pagina_memorias':{'siguiente_desplazamiento':None}},ejecutar,'s')[1])
            llamar.assert_not_called()

    def test_paginacion_estable_si_llegan_recuerdos(self):
        recuerdos=[{'id':i,'titulo':f't{i}','proyecto':'p','contenido':'dato'} for i in range(1,13)]
        state={};h=[]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':recuerdos}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            self.assertIn('1. t1',comando('/recuerdos',h,state,ejecutar,'s')[1])
            llamar.return_value={'ok':True,'memorias':[{'id':99,'titulo':'nuevo','contenido':'nuevo'}]+recuerdos}
            self.assertIn('6. t6',comando('/mas',h,state,ejecutar,'s')[1])
            self.assertIn('11. t11',comando('/mas',h,state,ejecutar,'s')[1])
            self.assertEqual(llamar.call_count,1)
            self.assertIn('final',comando('/mas',h,state,ejecutar,'s')[1])
            comando('/recuerdos',h,state,ejecutar,'s')
            self.assertEqual(llamar.call_count,2)

    def test_proyectos_y_estado_tienen_datos_reales(self):
        r={'ok':True,'proyectos':[{'proyecto':'Jarvis','total':0},{'proyecto':'estudios','total':3}]}
        self.assertIn('Jarvis: 0',renderizar('listar_proyectos',r))
        self.assertIn('estudios: 3',renderizar('listar_proyectos',r))
        self.assertEqual(renderizar('listar_proyectos',{'ok':False,'error':'caído'}),'caído')
        estado={'ok':True,'consultado':'hoy','memorias':5,'fuentes':[{'fuente':'codex','estado':'error','pendientes':2,'lectura_reciente':False,'error':'lectura falló'}]}
        s=renderizar('consultar_estado_cerebro',estado)
        self.assertIn('2 pendiente',s);self.assertIn('lectura falló',s);self.assertIn('sin confirmar',s)

    def test_no_repite_escritura_ni_permiso(self):
        tool={'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_proyecto','arguments':{'proyecto':'Jarvis'}}}]}
        cola=iter([tool,tool,{'role':'assistant','content':'fin'}]);h=[];permisos=[]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'estado':'creado','proyecto':'Jarvis'}) as llamar,patch.object(J.L,'_registrar'):
            J.ejecutar_turno(h,lambda _:next(cola),lambda t:permisos.append(t) or True,{})
            self.assertEqual(llamar.call_count,1);self.assertEqual(len(permisos),1)
            self.assertTrue(json.loads([m['content'] for m in h if m.get('role')=='tool'][-1])['repetida'])

    def test_permiso_denegado_no_se_vuelve_a_pedir(self):
        tool={'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_proyecto','arguments':{'proyecto':'Jarvis'}}}]}
        cola=iter([tool,tool,{'role':'assistant','content':'fin'}]);permisos=[]
        with patch.object(J.CEREBRO,'llamar') as llamar:
            J.ejecutar_turno([],lambda _:next(cola),lambda t:permisos.append(t) or False,{})
            self.assertEqual(len(permisos),1);llamar.assert_not_called()

    def test_contexto_recorta_turnos_completos(self):
        h=[{'role':'system','content':'s'}]
        for n in range(8):h.extend([{'role':'user','content':str(n)},{'role':'assistant','content':'a'*3500},{'role':'tool','content':'resultado'}])
        r=J._recortar(h)
        self.assertEqual(r[0],h[0]);self.assertEqual(r[1]['role'],'user')
        self.assertEqual(len(r[1:])%3,0)
        self.assertLessEqual(len(json.dumps(r[1:],ensure_ascii=False)),J.MAX_CONTEXTO_CARACTERES+50)
        self.assertEqual(r[-1],h[-1])

    def test_respuesta_vacia_muestra_resultado_real(self):
        cola=iter([{'role':'assistant','content':'','tool_calls':[{'function':{'name':'listar_proyectos','arguments':{}}}]},{'role':'assistant','content':''}])
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'proyectos':[{'proyecto':'Jarvis','total':0}]}):
            r=J.ejecutar_turno([],lambda _:next(cola),lambda _:False,{},mostrar=lambda _:None)
        self.assertIn('Jarvis: 0',r)
        self.assertIn('Proyectos:',r)

    def test_recordatorio_no_queda_si_falla_conexion(self):
        n=[0];h=[]
        def enviar(_):
            n[0]+=1
            if n[0]==1:return {'role':'assistant','content':'Voy a crearlo.'}
            raise ConnectionError('caído')
        with self.assertRaises(ConnectionError):J.ejecutar_turno(h,enviar,lambda _:False,{})
        self.assertFalse(any(m.get('role')=='system' for m in h))

    def test_qwen_no_puede_omitir_listado(self):
        cola=iter([{'role':'assistant','content':'','tool_calls':[{'function':{'name':'listar_memorias','arguments':{}}}]},
                   {'role':'assistant','content':'Estos son los primeros 5 recuerdos. ¿Quieres ver más?'}])
        h=[];state={}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[{'id':18,'titulo':'Qwen','contenido':'Usar Jarvis','proyecto':'sin_clasificar'}]}):
            r=J.ejecutar_turno(h,lambda _:next(cola),lambda _:False,state,mostrar=lambda _:None)
        self.assertIn('1. Qwen',r);self.assertIn('Usar Jarvis',r)
        self.assertEqual(h[-1]['content'],r)
        self.assertEqual(state['_lista_memorias'],{1:18})

    def test_frase_de_captura_y_reclamo_muestran_contenido(self):
        h=[];state={}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':[{'id':18,'titulo':'Qwen','contenido':'Usar Jarvis','proyecto':'sin_clasificar'}]}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            manejado,r=comando('muéstrame los recuerdos para poder clasificarlos por recuerdos',h,state,ejecutar,'s')
            self.assertTrue(manejado);self.assertIn('1. Qwen',r)
            manejado,repetido=comando('no me mostraste los recuerdos',h,state,ejecutar,'s')
            self.assertTrue(manejado);self.assertEqual(repetido,r)
            self.assertEqual(llamar.call_count,1)

    def test_peticion_especifica_sigue_al_modelo(self):
        self.assertFalse(comando('Muéstrame los recuerdos de estudios',[],{},None,'s')[0])
        calls=[]
        self.assertTrue(comando('Clasifica los recuerdos 1 y 2 en el proyecto Jarvis',[],{},lambda n,a:calls.append((n,a)) or {'ok':False,'error':'prueba'},'s')[0])
        self.assertEqual(calls[0][0],'clasificar_recuerdos')

    def test_filtro_sin_clasificar_y_fechas_no_avanzan(self):
        registros=[{'id':i,'titulo':f't{i}','contenido':'dato','proyecto':'sin_clasificar',
                    'creado':'2026-10-12T05:42:04.430284+00:00'} for i in range(1,8)]
        h=[];state={}
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':registros}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            manejado,primera=comando('muestrame los sin clasificar',h,state,ejecutar,'s')
            self.assertTrue(manejado)
            llamar.assert_called_once_with('listar_memorias',{'proyecto':'sin_clasificar'})
            self.assertIn('12 de octubre de 2026, 02:42:04 (Chile)',primera)
            manejado,fechas=comando('me los puedes listar con la fecha y hora?',h,state,ejecutar,'s')
            self.assertTrue(manejado);self.assertEqual(primera,fechas)
            self.assertEqual(llamar.call_count,1)
            self.assertNotIn('6. t6',fechas)
            siguiente=comando('/mas',h,state,ejecutar,'s')[1]
            self.assertIn('6. t6',siguiente)
            self.assertIn('Recuerdos del proyecto sin_clasificar:',siguiente)
            self.assertEqual(llamar.call_count,1)
            self.assertEqual(state['_lista_memorias'],{6:6,7:7})

    def test_cambiar_filtro_no_reutiliza_otro_listado(self):
        state={}
        with patch.object(J.CEREBRO,'llamar',side_effect=[{'ok':True,'memorias':[{'id':1,'contenido':'todos','proyecto':'estudios'}]},
              {'ok':True,'memorias':[{'id':2,'contenido':'sin','proyecto':'sin_clasificar'}]}]) as llamar:
            J.ejecutar_herramienta('listar_memorias',{},lambda _:False,state)
            r=J.ejecutar_herramienta('listar_memorias',{'proyecto':'sin_clasificar'},lambda _:False,state)
            self.assertEqual(llamar.call_count,2)
            self.assertEqual(r['memorias'][0]['id'],2)
            self.assertEqual(state['_listado_proyecto'],'sin_clasificar')

    def test_pagina_siguiente_del_modelo_conserva_filtro(self):
        state={}
        registros=[{'id':i,'contenido':'dato','proyecto':'sin_clasificar'} for i in range(1,8)]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':registros}) as llamar:
            J.ejecutar_herramienta('listar_memorias',{'proyecto':'sin_clasificar'},lambda _:False,state)
            r=J.ejecutar_herramienta('listar_memorias',{'desplazamiento':5},lambda _:False,state)
            self.assertEqual(llamar.call_count,1)
            self.assertEqual(r['proyecto_filtro'],'sin_clasificar')
            self.assertEqual([m['id'] for m in r['memorias']],[6,7])

    def test_fecha_no_disponible_no_se_inventa(self):
        texto=renderizar('listar_memorias',{'ok':True,'memorias':[{'numero_lista':1,'contenido':'dato'}]})
        self.assertIn('Fecha de guardado: no disponible',texto)
        self.assertIn('/recuerdos',comando('me los puedes listar con la fecha y hora?',[],{},None,'s')[1])

    def test_comando_desconocido_y_frase_normal(self):
        self.assertTrue(comando('/inventado',[],{},None,'s')[0])
        self.assertFalse(comando('Quiero revisar mi proyecto',[],{},None,'s')[0])


if __name__=='__main__':unittest.main()
