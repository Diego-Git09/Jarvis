"""La prohibición cubre servicios API, servidores remotos y aliases cloud."""
import io
import json
import unittest
from unittest.mock import patch
import cliente_ollama as O
import politica_ia as P
import segunda_opinion as IA


class Pruebas(unittest.TestCase):
    def test_ninguna_redireccion_puede_reenviar_prompt(self):
        import urllib.request
        r=urllib.request.Request('http://127.0.0.1:11434/api/chat',data=b'PREGUNTA_SINTETICA')
        for codigo in (301,302,303,307,308):
            with self.assertRaises(O.ErrorOllama) as e:O.SinRedireccion().redirect_request(r,None,codigo,'',{},'https://externo.invalid')
            self.assertEqual(e.exception.tipo,'politica');self.assertNotIn('PREGUNTA_SINTETICA',str(e.exception))

    def respuesta(self,d):return io.BytesIO(json.dumps(d).encode())

    def test_cloud_no_recibe_prompt_ni_si_hay_clave_en_entorno(self):
        for modelo in ('modelo:cloud','proveedor/modelo:cloud','modelo:8b-cloud'):
            with self.subTest(modelo=modelo),patch.object(O,'ABRIR') as abrir, self.assertRaisesRegex(O.ErrorOllama,'bloqueados'):
                O.solicitar('/api/chat',{'model':modelo,'messages':[{'role':'user','content':'DATO_SINTETICO_NO_TRANSMITIR'}]})
            abrir.assert_not_called()

    def test_servidor_ia_externo_bloqueado_antes_de_abrir(self):
        with patch.object(O,'BASE','https://ollama.com'),patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama):
            O.solicitar('/api/chat',{'model':'qwen3:8b','messages':[{'role':'user','content':'DATO_SINTETICO'}]})
        abrir.assert_not_called()

    def test_tampoco_consulta_catalogos_o_metadatos_de_servidor_externo(self):
        for ruta in ['/api/tags','/api/version','/api/show','/api/ps']:
            with patch.object(O,'BASE','https://servidor-externo.invalid'),patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama):
                O.solicitar(ruta)
            abrir.assert_not_called()

    def test_alias_remoto_sin_cloud_en_nombre_no_recibe_prompt(self):
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'ABRIR',return_value=self.respuesta({'remote_host':'https://ollama.com','remote_model':'modelo'})) as abrir,self.assertRaises(O.ErrorOllama):
            O.solicitar('/api/chat',{'model':'alias-local','messages':[{'role':'user','content':'DATO_SINTETICO_NO_TRANSMITIR'}]})
        abrir.assert_called_once()
        self.assertTrue(abrir.call_args.args[0].full_url.endswith('/api/show'))
        self.assertEqual(json.loads(abrir.call_args.args[0].data),{'model':'alias-local'})

    def test_sin_evidencia_de_pesos_no_infiere(self):
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'ABRIR',return_value=self.respuesta({})) as abrir,self.assertRaisesRegex(O.ErrorOllama,'pesos locales'):
            O.solicitar('/api/chat',{'model':'alias','messages':[{'role':'user','content':'Prueba sintética'}]})
        abrir.assert_called_once()

    def test_pesos_locales_permiten_chat_tras_consulta_sin_datos(self):
        from prueba_control_recursos import INFO,foto
        respuestas=[self.respuesta(INFO),self.respuesta(INFO),self.respuesta({'models':[{'name':'qwen3:8b','size':5200000000}]}),self.respuesta({'models':[]}),self.respuesta({'message':{'content':'Respuesta sintética'}})]
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch('control_recursos.instantanea',return_value=foto()),patch('control_recursos.registrar'),patch.object(O,'ABRIR',side_effect=respuestas) as abrir:
            r=O.solicitar('/api/chat',{'model':'qwen3:8b','messages':[{'role':'user','content':'Pregunta sintética'}]})
        self.assertEqual(r['message']['content'],'Respuesta sintética')
        self.assertEqual(len(abrir.call_args_list),5)
        self.assertTrue(abrir.call_args_list[-1].args[0].full_url.endswith('/api/chat'))
        for llamada in abrir.call_args_list[:-1]:
            self.assertNotIn('Pregunta sintética',(llamada.args[0].data or b'').decode())

    def test_catalogo_no_ofrece_proxy_ni_tag_cloud(self):
        datos={'models':[{'name':'local:8b'},{'name':'modelo:cloud'},{'name':'alias','remote_model':'modelo','remote_host':'https://ollama.com'}]}
        with patch.object(O,'solicitar',return_value=datos):self.assertEqual(O.modelos(),['local:8b'])

    def test_api_configuracion_y_listado_se_bloquean_antes_del_llavero(self):
        with patch.object(IA.P,'_secret') as secreto,patch.object(IA.WEB,'solicitar_publico') as red:
            with self.assertRaisesRegex(ValueError,'bloqueadas'):IA.configuracion('OpenAI')
            with self.assertRaisesRegex(ValueError,'bloqueadas'):IA.configurar('OpenAI','','modelo','clave-ficticia')
            self.assertFalse(IA.listar_modelos_remotos('OpenAI','','clave-ficticia')['ok'])
        secreto.assert_not_called();red.assert_not_called();self.assertFalse(P.permite_externa())


if __name__=='__main__':unittest.main()
