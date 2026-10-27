"""Modelo real del turno y recuperación local sin duplicar operaciones."""
import json
import unittest
from unittest.mock import patch
import configuracion_jarvis as C
import jarvis_agente as J
import respaldo_local as R
import segunda_opinion as IA
from interfaz_local import comando_local

DS=C.MODELO_PREDETERMINADO
Q=C.MODELO_COTIDIANO


class Pruebas(unittest.TestCase):
    def setUp(self):
        for obj,nombre,valor in [(J,'MODELO',DS),(J,'AJUSTES',dict(C.DEFAULT)),(J.O,'modelos',lambda:[DS,Q]),(J.CODIGO,'contexto',lambda *a:''),(J.SEGUIMIENTO,'iniciar_android',lambda *a:None)]:
            p=patch.object(obj,nombre,valor);p.start();self.addCleanup(p.stop)
        self.externa_real=IA.preguntar_externa
        self.nube=patch.object(IA,'preguntar_externa',side_effect=AssertionError('Respaldo externo prohibido'))
        self.nube.start();self.addCleanup(self.nube.stop)

    def h(self,p='Explica una batería'):
        return [{'role':'system','content':J.SISTEMA},{'role':'user','content':p}]

    def test_modelo_principal_sin_fallo_no_consulta_otro(self):
        with patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'Dato sintético'})}}) as inferir:
            self.assertEqual(J.responder_con_respaldo(self.h(),J.enviar_a_ollama,lambda _:False,{},mostrar=lambda _:None),'Dato sintético')
        inferir.assert_called_once();self.assertEqual(inferir.call_args.args[1]['model'],DS)

    def test_fallo_deepseek_contesta_qwen_con_historial_y_pedido_intactos(self):
        h=self.h('Explica una batería');h[1:1]=[{'role':'user','content':'Dato sintético ANTECEDENTE_618'},{'role':'assistant','content':'Entendido'}]
        cuerpos=[]
        def enviar(ruta,cuerpo,**kw):
            cuerpos.append(cuerpo)
            if cuerpo['model']==DS:raise J.O.ErrorOllama('Tiempo de prueba agotado',tipo='timeout')
            return {'message':{'role':'assistant','content':'Respuesta de respaldo'}}
        with patch.object(J.O,'solicitar',side_effect=enviar):
            r=J.responder_con_respaldo(h,J.enviar_a_ollama,lambda _:False,{},mostrar=lambda _:None)
        self.assertIn('Respaldo local: '+Q,r);self.assertIn('Respuesta de respaldo',r)
        self.assertEqual([c['model'] for c in cuerpos],[DS,Q])
        self.assertNotIn('format',cuerpos[1])
        self.assertIn('ANTECEDENTE_618',json.dumps(cuerpos[1]['messages']))
        self.assertEqual([m['content'] for m in h if m['role']=='user'][-1],'Explica una batería')
        self.assertEqual(J.ESTADISTICAS['modelo'],Q)

    def test_respaldo_inverso(self):
        with patch.object(J,'MODELO',Q),patch.object(J,'ejecutar_turno',side_effect=[ConnectionError('Error sintético'),'Resultado']) as ejecutar:
            r=J.responder_con_respaldo(self.h(),None,None,{},mostrar=lambda _:None)
        self.assertIn('Respaldo local: '+DS,r)
        self.assertEqual(ejecutar.call_args.kwargs['modelo_forzado'],DS)

    def test_ambos_fallan_solo_dos_intentos_y_estado_pendiente(self):
        estado={}
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('Error sintético')) as ejecutar:
            r=J.responder_con_respaldo(self.h(),None,None,estado,mostrar=lambda _:None)
        self.assertEqual(ejecutar.call_count,2);self.assertIn('respaldo local tampoco',r)
        self.assertEqual(estado['_estado_respuesta'],'fallida')

    def test_accion_iniciada_bloquea_respaldo(self):
        h=self.h()
        def ejecutar(*a,**kw):
            h.append({'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{'ruta':'no_escribir.txt'}}}]})
            raise ConnectionError('No se obtuvo resultado')
        with patch.object(J,'ejecutar_turno',side_effect=ejecutar) as motor:
            r=J.responder_con_respaldo(h,None,None,{},mostrar=lambda _:None)
        motor.assert_called_once();self.assertIn('ni repetí herramientas',r)
        self.assertTrue(any(m.get('role')=='tool' for m in h))

    def test_lectura_previa_tampoco_se_repite_automaticamente(self):
        h=self.h('Lee demo.txt y explica los datos')
        respuestas=[{'message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'leer_archivo','arguments':{'ruta':'demo.txt'}}}]}},ConnectionError('Interrumpido')]
        # El primer mensaje usa el protocolo nativo de Qwen; todo es sintético.
        with patch.object(J,'MODELO',Q),patch.object(J.O,'solicitar',side_effect=respuestas) as inferir,patch.dict(J.FUNCIONES,{'leer_archivo':lambda **kw:{'ok':True,'ruta':'demo.txt','contenido':'DATO_SINTETICO','cortado':False}}):
            r=J.responder_con_respaldo(h,J.enviar_a_ollama,lambda _:False,{},mostrar=lambda _:None)
        self.assertEqual(inferir.call_count,2);self.assertIn('ni repetí herramientas',r)

    def test_modelo_ausente_avisa_sin_descargar(self):
        with self.assertRaisesRegex(ConnectionError,'no está instalado'):
            R.elegir(DS,[DS],J.O.BASE)

    def test_servidor_remoto_no_es_respaldo_local(self):
        with self.assertRaisesRegex(ConnectionError,'este equipo'):
            R.elegir(DS,[DS,Q],'https://example.com')

    def test_no_otro_modelo_se_respeta(self):
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('Error sintético')) as ejecutar:
            r=J.responder_con_respaldo(self.h('No uses otro modelo. Explica una batería'),None,None,{},mostrar=lambda _:None)
        ejecutar.assert_called_once();self.assertIn('Respeté',r)

    def test_identidad_sale_de_config_y_ultima_inferencia(self):
        for pregunta in ('¿Qué modelo usas?','¿Estás usando DeepSeek?','¿Usas Qwen o DeepSeek?','¿Cuál es el modelo que me está contestando?'):
            with self.subTest(pregunta=pregunta),patch('interfaz_local.O.diagnostico',return_value={'ok':True,'version':'prueba','modelos':[DS,Q]}):
                hecho,texto=comando_local(pregunta,[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None,{'modelo':Q})
                self.assertTrue(hecho);self.assertIn('modelo configurado '+DS,texto);self.assertIn('Última respuesta del motor en esta apertura: '+Q,texto)

    def test_proveedor_retirado_no_lee_clave_ni_llama_red(self):
        self.assertNotIn('Gemini',IA.P.PRESETS)
        with patch.object(IA.P,'_secret') as llavero,patch.object(IA.WEB,'solicitar_publico') as red:
            r=self.externa_real('Dato sintético',lambda _:True,perfil='Gemini')
            modelos=IA.listar_modelos_remotos('Gemini','','clave-ficticia')
        self.assertFalse(r['ok']);self.assertFalse(modelos['ok']);llavero.assert_not_called();red.assert_not_called()

    def test_todos_los_proveedores_externos_bloqueados_antes_del_llavero(self):
        with patch.object(IA.P,'_secret') as llavero,patch.object(IA.WEB,'solicitar_publico') as red:
            for proveedor in ('OpenAI','Anthropic','DeepSeek','Compatible'):
                with self.subTest(proveedor=proveedor):
                    r=self.externa_real('Dato sintético',lambda _:self.fail('No se pide permiso para algo bloqueado'),perfil=proveedor)
                    self.assertFalse(r['ok']);self.assertIn('bloqueadas',r['error'])
                    self.assertFalse(IA.listar_modelos_remotos(proveedor,'https://example.com','clave-ficticia')['ok'])
        llavero.assert_not_called();red.assert_not_called()


if __name__=='__main__':unittest.main()
