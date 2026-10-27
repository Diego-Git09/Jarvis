"""Persistencia, secreto fuera de JSON y límites de respaldo: sin llavero ni nube reales."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import perfiles_ia as P
import segunda_opinion as IA
import jarvis_agente as J


class Pruebas(unittest.TestCase):
    def setUp(self):
        # Se conserva la comprobación del adaptador histórico con transporte
        # simulado; la política real se verifica en prueba_respaldo_local_2h.
        politica=patch('politica_ia.permite_externa',return_value=True);politica.start();self.addCleanup(politica.stop)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.archivo=Path(self.tmp.name)/'datos'/'perfiles_ia.json'
        self.parche=patch.object(P,'ARCHIVO',self.archivo);self.parche.start();self.addCleanup(self.parche.stop)
        self.vault={};self.calls=[]
        def secret(op,ident,clave=None):
            self.calls.append(op)
            if op=='guardar':self.vault[ident]=clave;return True
            if op=='leer':return self.vault.get(ident,'')
            self.vault.pop(ident,None);return True
        self.secreto=patch.object(P,'_secret',side_effect=secret);self.secreto.start();self.addCleanup(self.secreto.stop)
        IA.SESION.clear();self.addCleanup(IA.SESION.clear)
        self.catalogo=patch.object(J.O,'modelos',return_value=['jarvis-deepseek:8b','qwen3:8b']);self.catalogo.start();self.addCleanup(self.catalogo.stop)

    def guardar(self,prov='OpenAI',key='clave-ficticia'):
        return P.guardar_perfil(prov,'','modelo-test',key)

    def test_perfiles_se_recuperan_y_clave_no_esta_en_archivo_o_lista(self):
        for p in ('OpenAI','Anthropic','DeepSeek'):self.guardar(p,'secreto-'+p)
        IA.SESION.clear()
        self.assertEqual(IA.configuracion('Anthropic')['clave'],'secreto-Anthropic')
        self.assertEqual(len(P.listar()),3)
        self.assertNotIn('secreto-',self.archivo.read_text());self.assertNotIn('secreto-',json.dumps(P.listar()))
        self.assertEqual(os.stat(self.archivo).st_mode&0o777,0o600);self.assertEqual(os.stat(self.archivo.parent).st_mode&0o777,0o700)

    def test_llavero_no_disponible_no_guarda_metadata_ni_clave_en_plano(self):
        with patch.object(P,'_secret',side_effect=ValueError('llavero bloqueado')):
            with self.assertRaises(ValueError):self.guardar()
        self.assertFalse(self.archivo.exists())

    def test_error_al_guardar_no_pierde_clave_anterior(self):
        self.guardar();antes=self.archivo.read_text();ref=P.leer()['perfiles']['OpenAI']['credencial']
        with patch.object(P,'_guardar',side_effect=OSError('disco lleno')):
            with self.assertRaises(OSError):self.guardar(key='clave-nueva')
        self.assertEqual(self.archivo.read_text(),antes);self.assertEqual(P.configuracion()['clave'],'clave-ficticia');self.assertEqual(set(self.vault),{ref})

    def test_clave_vacia_conserva_la_del_mismo_perfil(self):
        self.guardar();ref=P.leer()['perfiles']['OpenAI']['credencial']
        P.guardar_perfil('OpenAI','','otro-modelo','')
        self.assertEqual(P.leer()['perfiles']['OpenAI']['credencial'],ref);self.assertEqual(P.configuracion()['clave'],'clave-ficticia')
        with self.assertRaises(ValueError):P.guardar_perfil('Gemini','','modelo','')

    def test_destino_modificado_no_recupera_ni_transmite_el_secreto(self):
        self.guardar();d=P.leer();d['perfiles']['OpenAI']['url']='https://example.com/chat/completions';P._guardar(d);self.calls.clear()
        with self.assertRaises(ValueError):P.configuracion()
        self.assertEqual(self.calls,[])

    def test_eliminar_solo_el_perfil_elegido(self):
        self.guardar();self.guardar('Anthropic');P.eliminar('OpenAI')
        self.assertEqual([p['proveedor'] for p in P.listar()],['Anthropic']);self.assertEqual(P.opciones()['preferido'],'Anthropic');self.assertEqual(len(self.vault),1)

    def test_respaldo_envia_solo_pregunta_sin_historial_y_no_repite_escrituras(self):
        self.guardar();P.guardar_opciones(True)
        anterior=[{'role':'system','content':'reglas privadas'},{'role':'user','content':'dato privado anterior'},{'role':'assistant','content':'respuesta anterior'},{'role':'user','content':'Explícame cómo funciona una batería'}]
        with patch.object(J,'ejecutar_turno',side_effect=[ConnectionError('timeout'),'Opinión local']) as local,patch.object(IA,'preguntar_externa') as nube:
            texto=J.responder_con_respaldo(anterior,lambda _:None,lambda _:self.fail('Ya autorizó'),{},mostrar=lambda _:None)
        self.assertIn('Respaldo local',texto);self.assertEqual(local.call_args.kwargs['modelo_forzado'],'qwen3:8b')
        nube.assert_not_called()

    def test_despues_de_escritura_fallida_no_consulta_nube(self):
        self.guardar();P.guardar_opciones(True)
        h=[{'role':'user','content':'Explícame ese cambio'}]
        def local(*a,**k):
            h.extend([{'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{}}}]}]);raise ConnectionError('timeout')
        with patch.object(J,'ejecutar_turno',side_effect=local),patch.object(IA,'preguntar_externa') as nube:
            texto=J.responder_con_respaldo(h,None,lambda _:False,{},mostrar=lambda _:None)
        nube.assert_not_called();self.assertIn('No envié',texto)

    def test_adjunto_o_segundo_cerebro_no_se_delegan(self):
        self.guardar();P.guardar_opciones(True)
        for p,estado in (('Resume mi Segundo Cerebro',{}),('Explica esto',{'_adjuntos_turno':True}),('Edita un archivo',{})):
            h=[{'role':'user','content':p}]
            with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('timeout')),patch.object(IA,'preguntar_externa') as nube:J.responder_con_respaldo(h,None,lambda _:False,estado,mostrar=lambda _:None)
            nube.assert_not_called()

    def test_complemento_conserva_respuesta_local_y_no_envia_borrador(self):
        self.guardar();P.guardar_opciones(True);h=[{'role':'user','content':'Dame ideas para estudiar'}]
        with patch.object(J,'ejecutar_turno',return_value='Ideas locales privadas'),patch.object(IA,'preguntar_ia',return_value={'ok':True,'modelo':'qwen3:8b','origen':'Ollama local','respuesta':'Más ideas'}) as local,patch.object(IA,'preguntar_externa') as nube:
            texto=J.responder_con_respaldo(h,None,lambda _:False,{},mostrar=lambda _:None,complementar=True)
        self.assertIn('Ideas locales privadas',texto);self.assertIn('Más ideas',texto);self.assertNotIn('privadas',local.call_args.args[0]);nube.assert_not_called()

    def test_fallo_sin_perfil_no_finge_exito_y_no_hace_otra_consulta(self):
        h=[{'role':'user','content':'Pregunta'}];estado={}
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('timeout')),patch.object(IA,'preguntar_externa') as nube:
            texto=J.responder_con_respaldo(h,None,lambda _:False,estado,mostrar=lambda _:None)
        nube.assert_not_called();self.assertEqual(estado['_estado_respuesta'],'fallida');self.assertIn('No pude',texto)

    def test_autorizacion_persistente_se_respeta_y_se_puede_retirar(self):
        self.guardar();respuesta=json.dumps({'choices':[{'message':{'content':'OK'},'finish_reason':'stop'}]}).encode()
        P.guardar_opciones(True)
        with patch.object(IA.WEB,'solicitar_publico',return_value=(respuesta,'application/json','url')) as red:
            self.assertTrue(IA.preguntar_externa('Pregunta',lambda _:self.fail('No vuelve a pedir'),automatico=True)['ok'])
            P.guardar_opciones(False)
            self.assertFalse(IA.preguntar_externa('Pregunta',lambda _:False,automatico=True)['ok'])
            self.assertEqual(red.call_count,1)

    def test_listado_google_no_pone_clave_en_url_y_filtra_embeddings(self):
        respuesta=json.dumps({'models':[{'name':'models/gemini-flash','supportedGenerationMethods':['generateContent']},{'name':'models/text-embedding','supportedGenerationMethods':['embedContent']}]}).encode()
        with patch.object(IA.WEB,'solicitar_publico',return_value=(respuesta,'application/json','url')) as red:r=IA.listar_modelos_remotos('Gemini','','clave-ficticia')
        self.assertFalse(r['ok']);red.assert_not_called()

    def test_preguntar_natural_a_un_proveedor_elegido_conserva_pregunta(self):
        from interfaz_local import comando_local
        with patch.object(IA,'preguntar_externa',return_value={'ok':True,'modelo':'gemini','origen':'Gemini','respuesta':'Respuesta'}) as nube:
            hecho,t=comando_local('Jarvis, pregúntale a Gemini cómo funciona una batería',[],{},lambda _:True,J.AJUSTES,lambda:None,None)
        self.assertTrue(hecho);self.assertIn('retirado',t);nube.assert_not_called()

    def test_timeout_de_respaldo_se_aplica_y_se_restaura_al_salir(self):
        self.guardar();P.guardar_opciones(True,timeout_local=20);J.TIEMPO_MODELO.fin=None
        visto=[]
        def local(*a,**k):visto.append(J.TIEMPO_MODELO.fin);return 'Respuesta local'
        with patch.object(J,'ejecutar_turno',side_effect=local):J.responder_con_respaldo([{'role':'user','content':'Pregunta'}],None,lambda _:False,{},mostrar=lambda _:None)
        self.assertIsNone(visto[0]);self.assertIsNone(J.TIEMPO_MODELO.fin)

    def test_peticion_actual_solo_local_prevalece_sobre_respaldo_y_checkbox(self):
        self.guardar();P.guardar_opciones(True)
        h=[{'role':'user','content':'Responde solo local; no uses otra IA. ¿Qué es una batería?'}]
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('timeout')),patch.object(IA,'preguntar_externa') as nube:
            t=J.responder_con_respaldo(h,None,lambda _:False,{},mostrar=lambda _:None,complementar=True)
        nube.assert_not_called();self.assertIn('no envié',t)
        self.assertNotIn('preguntar_ia_externa',{h['function']['name'] for h in J.herramientas_para_turno(h)})
        with patch.object(IA,'preguntar_externa') as nube:
            r=J.consulta_contextual('preguntar_ia_externa',{'pregunta':'Pregunta'},h,lambda _:self.fail('No debe pedir permiso para algo prohibido'),{})
        nube.assert_not_called();self.assertFalse(r['ok'])


if __name__=='__main__':unittest.main()
