"""Lectura integral explícita y controles de presentación/configuración."""
import unittest
from unittest.mock import patch,Mock
import analisis_completo as A
import mensajes_largos as M
import configuracion_jarvis as C
import control_recursos as R
from interfaz_local import comando_local

class Pruebas(unittest.TestCase):
    def test_envia_todos_los_datos_sin_herramientas_y_sin_recortes(self):
        e={};texto='inicio\n'+('dato sintético '*1200)+'\nFINAL_X';M.preparar(texto,e)
        enviar=Mock(return_value={'message':{'content':'FINAL_X'},'prompt_eval_count':7210,'done_reason':'stop'})
        t=A.analizar(e['_mensaje_largo'],'Qué identificador hay al final?',dict(C.DEFAULT,num_ctx=32768),enviar)
        cuerpo=enviar.call_args.args[1];self.assertIn(texto,cuerpo['messages'][1]['content']);self.assertNotIn('tools',cuerpo)
        self.assertFalse(cuerpo['truncate']);self.assertFalse(cuerpo['shift']);self.assertIn('7210',t)
    def test_limite_no_recorta_ni_reintenta_con_otro_modelo(self):
        e={};M.preparar('dato '*3000,e);enviar=Mock(side_effect=ConnectionError('context length'))
        t=A.analizar(e['_mensaje_largo'],'Resume',C.DEFAULT,enviar)
        self.assertIn('No lo recorté',t);enviar.assert_called_once();self.assertEqual(len(''.join(e['_mensaje_largo']['tramos'])),15000)
    def test_rechaza_datos_conservados_alterados(self):
        e={};M.preparar('dato',e);e['_mensaje_largo']['tramos']=['otro'];enviar=Mock()
        self.assertIn('cambió',A.analizar(e['_mensaje_largo'],'Resume',C.DEFAULT,enviar));enviar.assert_not_called()
    def test_contexto_muestra_mixto_y_limites(self):
        ajustes=C.validar({'modo_gpu':'mixto','capas_gpu':12,'num_ctx':32768})
        ok,t=comando_local('/contexto',[],{},lambda _:False,ajustes,lambda:None,None)
        self.assertTrue(ok);self.assertIn('12 capas GPU',t);self.assertIn('32768',t)
    def test_no_confunde_runner_oficial_con_proceso_ajeno(self):
        def ejecutar(cmd,**kw):
            if '--query-compute-apps=pid,process_name,used_gpu_memory' in cmd:
                return Mock(returncode=0,stdout='42, /usr/local/lib/ollama/llama-server, 6153\n43, /opt/renderizador, 3000\n')
            return Mock(returncode=0,stdout='| 0 N/A N/A 42 C /usr/local/lib/ollama/llama-server 6153MiB |\n| 0 N/A N/A 44 G /opt/editor 2500MiB |')
        with patch.object(R.subprocess,'run',side_effect=ejecutar),patch.object(R.Path,'glob',return_value=[]):r=R.procesos()
        self.assertEqual({p['nombre'] for p in r['pesados']},{'renderizador','editor'})
    def test_descarga_espera_la_confirmacion_de_api_ps(self):
        import recursos_ollama as RE
        c=Mock();c.solicitar.side_effect=[{'models':[{'name':'modelo'}]},{'models':[]}]
        with patch.object(RE.time,'sleep'):self.assertEqual(RE.esperar_descarga(c,['modelo'],10**15),set())
        self.assertEqual(c.solicitar.call_count,2)

    def test_solo_texto_no_anuncia_escrituras_al_modelo(self):
        import jarvis_agente as J
        for pregunta in ['Escribe una clase Java Persona. No crees archivos.','Crea un ejemplo Kotlin. Solo texto.']:
            hs=J.herramientas_para_turno([{'role':'user','content':pregunta}])
            self.assertFalse({h['function']['name'] for h in hs}&J.REQUIEREN_PERMISO)

    def test_reposo_sin_lectura_valida_no_confirma_descarga(self):
        c=Mock();c.solicitar.return_value={}
        with patch.object(R,'_REGISTRO',{'modelo':0}):
            self.assertEqual(R.comprobar_reposo(c,1),[]);self.assertIn('modelo',R._REGISTRO)
    def test_estado_local_no_publica_y_pide_permiso(self):
        c=Mock();permisos=[]
        with patch('estado_ia.generar',return_value='Estado sintético') as generar:
            ok,t=comando_local('/estado_ia local',[],{},lambda t:permisos.append(t) or True,C.DEFAULT,lambda:None,c)
        self.assertTrue(ok);self.assertEqual(len(permisos),1);generar.assert_called_once();c.publicar_documento.assert_not_called();self.assertIn('No se publicó',t)
    def test_aviso_de_memoria_no_dispara_otro_modelo(self):
        import jarvis_agente as J
        from cliente_ollama import ErrorOllama
        h=[{'role':'user','content':'hola'}]
        with patch.object(J,'ejecutar_turno',side_effect=ErrorOllama('Simulación: poca VRAM',tipo='recursos')) as turno,patch.object(J.O,'modelos') as modelos:
            t=J.responder_con_respaldo(h,lambda _:None,lambda _:False,{})
        turno.assert_called_once();modelos.assert_not_called();self.assertIn('No intenté cargar el otro modelo',t)

if __name__=='__main__':unittest.main()
