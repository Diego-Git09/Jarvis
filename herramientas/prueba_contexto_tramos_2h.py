"""Catálogos pertinentes, presupuesto completo y texto largo sin ejecución."""
import copy
import json
import unittest
from unittest.mock import patch
import configuracion_jarvis as C
import jarvis_agente as J
import mensajes_largos as M
import presupuesto_contexto as P
import protocolo_deepseek as DS
from interfaz_jarvis import comando,renderizar
from interfaz_local import comando_local
from entrada_jarvis import leer_pregunta,TextoPegado


class Pruebas(unittest.TestCase):
    def nombres(self,p):return {x['function']['name'] for x in J.herramientas_para_turno([{'role':'user','content':p}])}

    def test_lista_proyectos_no_carga_todas_las_mutaciones(self):
        self.assertEqual(self.nombres('muestra mis proyectos'),{'listar_proyectos'})

    def test_corregir_no_anuncia_olvidar_ni_crear_proyectos(self):
        nombres=self.nombres('corrige una memoria')
        self.assertIn('corregir_memoria',nombres);self.assertIn('ver_recuerdo',nombres)
        self.assertNotIn('olvidar_memoria',nombres);self.assertNotIn('crear_proyecto',nombres)

    def test_ultima_conversacion_carga_la_consulta_correcta(self):
        self.assertIn('consultar_ultima_conversacion',self.nombres('cuál fue la última conversación'))

    def test_recuento_recuerdos_no_exige_total_redundante(self):
        texto=renderizar('listar_proyectos',{'ok':True,'proyectos':[{'proyecto':'SINTETICO','recuerdos':1,'conversaciones':2}]})
        self.assertIn('1 recuerdo(s)',texto);self.assertIn('2 conversación(es)',texto)

    def test_peticion_ambigua_no_carga_todo_el_programa(self):
        nombres=self.nombres('revisa todo')
        self.assertLessEqual(len(nombres),6)
        self.assertFalse(nombres & J.REQUIEREN_PERMISO)

    def test_formato_no_duplica_parametros_en_catalogo(self):
        h=J.herramientas_para_turno([{'role':'user','content':'corrige una memoria'}])
        cuerpo=DS.preparar({'messages':[{'role':'user','content':'corrige una memoria'}],'tools':h})
        self.assertNotIn('parameters',cuerpo['messages'][0]['content'])
        for v in cuerpo['format']['oneOf'][1:]:
            original=next(x['function'] for x in h if x['function']['name']==v['properties']['accion']['const'])
            self.assertEqual(v['properties']['argumentos'],original['parameters'])

    def test_esquema_se_cuenta_aunque_tools_este_vacio(self):
        c={'messages':[{'role':'system','content':'Reglas'},{'role':'user','content':'Pregunta'},{'role':'tool','content':'DATO_SINTETICO_728'}],'tools':[],'format':{'type':'object','properties':{'dato':{'type':'string'}}}}
        r=P.componentes(c,8192,2048)
        self.assertGreater(r['herramientas_tokens_estimados'],P.tokens({'tools':[],'format':{}}))
        self.assertGreater(r['resultados_tokens_estimados'],0)
        self.assertFalse(r['tokenizacion_exacta']);self.assertNotIn('DATO_SINTETICO_728',json.dumps(r))

    def test_estima_bytes_multibyte_sin_llamarlo_tokenizacion_exacta(self):
        self.assertGreater(P.tokens('á'*50),P.tokens('a'*50))
        self.assertEqual(P.limites(4096,2048)['salida_reservada_tokens'],1365)

    def test_metricas_y_contexto_muestran_total_real(self):
        estado={};h=[{'role':'system','content':J.prompt_para_turno('Hola')},{'role':'user','content':'Hola'}]
        respuesta={'message':{'role':'assistant','content':'{"accion":"respuesta","argumentos":{},"respuesta":"Hola"}'},'prompt_eval_count':42}
        with patch.object(J.TIEMPO_MODELO,'estado',estado,create=True),patch.object(J,'MODELO',C.MODELO_PREDETERMINADO),patch.object(J.O,'solicitar',return_value=respuesta):
            J.enviar_a_ollama(h)
        hecho,texto=comando_local('/contexto',h,estado,lambda _:False,dict(C.DEFAULT),lambda:None,None,J.ESTADISTICAS)
        self.assertTrue(hecho);self.assertIn('42 tokens en total',texto)
        self.assertIn('Reglas:',texto);self.assertIn('Herramientas y esquema:',texto)
        self.assertIn('no un tokenizador exacto',texto)

    def test_contexto_4096_compacta_reglas_propias_para_qwen(self):
        ajustes=dict(C.DEFAULT,num_ctx=4096,num_predict=1024)
        h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':'Hola'}]
        with patch.object(J,'AJUSTES',ajustes),patch.object(J,'MODELO',C.MODELO_COTIDIANO),patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':'Hola'}}) as enviar:
            J.enviar_a_ollama(h)
        self.assertIn('controlador',enviar.call_args.args[1]['messages'][0]['content'])
        self.assertEqual(enviar.call_args.args[1]['options']['num_ctx'],4096)
        self.assertEqual(h[0]['content'],J.SISTEMA)

    def test_tramos_reconstruyen_texto_exacto_y_lineas(self):
        texto=('área sintética\n'*1000)+'FINAL_SINTETICO'
        estado={};M.preparar(texto,estado)
        self.assertEqual(''.join(estado['_mensaje_largo']['tramos']),texto)
        self.assertTrue(all(len(t)<=M.TAMANO_TRAMO for t in estado['_mensaje_largo']['tramos']))

    def test_pagina_elegida_y_avance_sin_ejecutar(self):
        estado={};M.preparar('A'*4500,estado)
        self.assertIn('Tramo 1/3',M.comando('/tramo 1',estado)[1])
        self.assertIn('Tramo 2/3',M.comando('/mas_mensaje',estado)[1])
        self.assertEqual(estado['_tramo_mensaje_visible']['texto'],'A'*2000)
        self.assertIn('entre 1 y 3',M.comando('/tramo 99',estado)[1])

    def test_comandos_incrustados_no_se_ejecutan(self):
        texto='/mover a.txt b.txt\n'+('datos sin ejecutar\n'*1200)
        estado={};h=[{'role':'system','content':J.SISTEMA}]
        with patch.object(J,'ejecutar_herramienta',side_effect=AssertionError('No debe ejecutar')):
            hecho,respuesta=comando(texto,h,estado,lambda *a:self.fail('No ejecuta'),J.SISTEMA)
        self.assertTrue(hecho);self.assertIn('tramo',respuesta)
        self.assertEqual(''.join(estado['_mensaje_largo']['tramos']),texto)

    def test_mensaje_12001_se_conserva_sin_modelo_ni_nube(self):
        texto='DATO_SINTETICO '*1000;h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':texto}];estado={}
        with patch.object(J,'ejecutar_turno') as motor,patch.object(J.IA,'preguntar_externa') as nube:
            respuesta=J.responder_con_respaldo(h,None,None,estado,mostrar=lambda _:None)
        motor.assert_not_called();nube.assert_not_called();self.assertIn('/tramo 1',respuesta)
        self.assertEqual(h[1]['content'],texto)

    def test_limite_de_contexto_inferior_propone_tramos_sin_respaldo(self):
        texto='datos de prueba '*350;h=[{'role':'user','content':texto}];estado={}
        with patch.object(J,'ejecutar_turno',side_effect=J.O.ErrorOllama('Contexto de prueba',tipo='contexto')) as motor:
            respuesta=J.responder_con_respaldo(h,None,None,estado,mostrar=lambda _:None)
        motor.assert_called_once();self.assertIn('/tramo 1',respuesta)

    def test_indice_no_revela_todo_el_mensaje(self):
        estado={};M.preparar('SINTETICO_PRIVADO '*1000,estado)
        self.assertNotIn('SINTETICO_PRIVADO',M.comando('/tramos',estado)[1])
        self.assertIn('No hay',M.comando('/tramo 1',{})[1])

    def test_referencia_no_arrastra_otros_tramos_o_tema(self):
        estado={};M.preparar('PRIMER_TRAMO '+('A'*2100)+'ULTIMO_TRAMO',estado);M.comando('/tramo 1',estado)
        contexto=M.contexto('explica ese tramo',estado)
        self.assertIn('PRIMER_TRAMO',contexto);self.assertNotIn('ULTIMO_TRAMO',contexto)
        self.assertEqual(M.contexto('otro tema: explica esto',estado),'')

    def test_tramo_llega_al_modelo_con_catalogo_vacio(self):
        estado={};texto='MARCA_SINTETICA_841\n'+'A'*15000
        M.preparar(texto,estado);M.comando('/tramo 1',estado)
        h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':texto},{'role':'assistant','content':'Dividido en tramos'},{'role':'user','content':'Explica ese tramo'}]
        salida={'message':{'role':'assistant','content':'{"accion":"respuesta","argumentos":{},"respuesta":"Marca sintética"}'}}
        with patch.object(J,'MODELO',C.MODELO_PREDETERMINADO),patch.object(J.CODIGO,'contexto',return_value=''),patch.object(J.O,'solicitar',return_value=salida) as enviar:
            J.ejecutar_turno(h,J.enviar_a_ollama,lambda _:False,estado,mostrar=lambda _:None)
        cuerpo=enviar.call_args.args[1]
        self.assertIn('MARCA_SINTETICA_841',json.dumps(cuerpo['messages'],ensure_ascii=False))
        self.assertEqual(len(cuerpo['format']['oneOf']),1)

    def test_pegar_mas_de_12000_conserva_ordenes_como_datos(self):
        texto='/mover no_ejecutar.txt destino.txt\n'+'x'*12500
        entradas=iter(['/pegar',texto,'/fin'])
        recibido=leer_pregunta(lambda _:next(entradas),lambda _:None)
        self.assertIsInstance(recibido,TextoPegado);self.assertEqual(recibido,texto)

    def test_exceso_de_limite_no_modifica_tramos_anteriores(self):
        estado={};M.preparar('Datos anteriores',estado);antes=copy.deepcopy(estado)
        self.assertIn('supera',M.preparar('X'*(M.MAX_MENSAJE+1),estado))
        self.assertEqual(estado,antes)


if __name__=='__main__':unittest.main()
