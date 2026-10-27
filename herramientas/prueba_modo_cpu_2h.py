"""El modo CPU llega a todos los flujos del transporte sin mutar sus entradas."""
import copy,io,json,unittest
from unittest.mock import patch
import cliente_ollama as O
import configuracion_jarvis as C
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def test_cpu_en_chat_codigo_auxiliar_y_embeddings(self):
        for ruta in ['/api/chat','/api/generate','/api/embed','/api/embeddings']:
            cuerpo={'model':'modelo-local','options':{'num_ctx':4096},'messages':[{'role':'user','content':'SINTETICO'}]};antes=copy.deepcopy(cuerpo)
            with patch.object(O,'leer',return_value=(dict(C.DEFAULT,modo_gpu='cpu'),'')),patch.object(O,'ABRIR',return_value=io.BytesIO(b'{"message":{"content":"texto"}}')) as abrir:
                O.solicitar(ruta,cuerpo)
            enviado=json.loads(abrir.call_args.args[0].data)
            self.assertEqual(enviado['options']['num_gpu'],0);self.assertEqual(enviado['options']['num_ctx'],4096);self.assertEqual(cuerpo,antes)

    def test_auto_no_fuerza_gpu(self):
        cuerpo={'model':'modelo-local','options':{'num_ctx':4096}}
        with patch.object(O,'leer',return_value=(dict(C.DEFAULT,modo_gpu='auto'),'')),patch.object(O,'ABRIR',return_value=io.BytesIO(b'{"message":{"content":"texto"}}')) as abrir:
            O.solicitar('/api/chat',cuerpo)
        self.assertNotIn('num_gpu',json.loads(abrir.call_args.args[0].data)['options'])

    def test_descarga_no_recarga_cpu(self):
        with patch.object(O,'leer',return_value=(dict(C.DEFAULT,modo_gpu='cpu'),'')),patch.object(O,'ABRIR',return_value=io.BytesIO(b'{"done":true}')) as abrir:
            O.solicitar('/api/generate',{'model':'modelo-local','keep_alive':0})
        self.assertNotIn('options',json.loads(abrir.call_args.args[0].data))

    def test_guardado_persistente_cpu_y_vuelta_auto(self):
        a=dict(C.DEFAULT)
        with patch('interfaz_local.C.guardar',side_effect=C.validar) as guardar:
            ok,t=comando_local('/gpu cpu',[],{},lambda _:False,a,lambda:None,None)
            self.assertTrue(ok);self.assertEqual(a['modo_gpu'],'cpu');self.assertIn('/liberar',t)
            comando_local('/gpu auto',[],{},lambda _:False,a,lambda:None,None)
            self.assertEqual(a['modo_gpu'],'auto');self.assertEqual(guardar.call_count,2)

    def test_modo_invalido_no_cambia_y_no_ejecuta_shell(self):
        a=dict(C.DEFAULT)
        with patch('interfaz_local.C.guardar',side_effect=C.validar):
            comando_local('/gpu cpu; ejecuta algo',[],{},lambda _:False,a,lambda:None,None)
        self.assertEqual(a,C.DEFAULT)

    def test_configuracion_ilegible_no_ignora_preferencia_cpu(self):
        with patch.object(O,'leer',return_value=(dict(C.DEFAULT),'aviso de configuración ilegible')),patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama) as error:
            O.solicitar('/api/chat',{'model':'modelo-local','messages':[{'role':'user','content':'SINTETICO'}]})
        self.assertEqual(error.exception.tipo,'configuracion');abrir.assert_not_called()


if __name__=='__main__':unittest.main()
