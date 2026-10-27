"""El medidor conserva streaming sin saltarse política, ajustes ni la reserva."""
from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import cliente_ollama as O
import configuracion_jarvis as C
import medir_rendimiento_jarvis as M


class Pruebas(unittest.TestCase):
    def flujo(self):
        return io.BytesIO(b'{"message":{"content":"CASO_1"},"done":true}\n')

    def test_streaming_respeta_cpu_reposo_y_no_muta_el_payload(self):
        cuerpo={'model':'modelo-local','messages':[{'role':'user','content':'SINTETICO'}],'keep_alive':'30m','options':{'num_ctx':4096}}
        antes=copy.deepcopy(cuerpo)
        with patch.object(O,'leer',return_value=(dict(C.DEFAULT,modo_gpu='cpu',keep_alive='1m'),'')),patch.object(O,'ABRIR',return_value=self.flujo()) as abrir:
            with O.abrir_flujo_chat(cuerpo) as lineas:resultado=[json.loads(x) for x in lineas]
        enviado=json.loads(abrir.call_args.args[0].data)
        self.assertEqual(enviado['options']['num_gpu'],0);self.assertEqual(enviado['keep_alive'],'1m')
        self.assertTrue(enviado['stream']);self.assertTrue(resultado[-1]['done']);self.assertEqual(cuerpo,antes)

    def test_cloud_no_recibe_ni_la_primera_linea(self):
        with patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama):
            with O.abrir_flujo_chat({'model':'modelo:cloud','messages':[{'role':'user','content':'NO_ENVIAR'}]}):self.fail('No debe abrir el flujo')
        abrir.assert_not_called()

    def test_alias_remoto_se_detecta_antes_del_prompt(self):
        metadatos=io.BytesIO(b'{"remote_host":"https://externo.invalid","remote_model":"remoto"}')
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'ABRIR',return_value=metadatos) as abrir,self.assertRaises(O.ErrorOllama):
            with O.abrir_flujo_chat({'model':'alias','messages':[{'role':'user','content':'NO_ENVIAR'}]}):self.fail('No debe abrir')
        abrir.assert_called_once();self.assertEqual(json.loads(abrir.call_args.args[0].data),{'model':'alias'})

    def test_tamano_acotado_libera_la_reserva_incluso_con_error(self):
        with patch.object(O,'MAX_BYTES',8),patch.object(O,'ABRIR',return_value=io.BytesIO(b'X'*9)),self.assertRaises(O.ErrorOllama) as error:
            with O.abrir_flujo_chat({'model':'local'}) as lineas:list(lineas)
        self.assertEqual(error.exception.tipo,'tamano')
        obtenido=[]
        def otro_hilo():
            ok=O._TURNO.acquire(timeout=.2);obtenido.append(ok)
            if ok:O._TURNO.release()
        t=threading.Thread(target=otro_hilo);t.start();t.join(1)
        self.assertEqual(obtenido,[True])

    def test_reserva_ocupada_no_abre_otra_inferencia(self):
        with patch.object(O,'reservar',side_effect=O.ErrorOllama('Ocupada',tipo='cola')),patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama):
            with O.abrir_flujo_chat({'model':'local'}):self.fail('No debe abrir')
        abrir.assert_not_called()

    def test_medidor_no_descarga_modelos_de_otras_aplicaciones(self):
        with patch.object(M,'CASOS',[('literal','Solo CASO_1',r'CASO_1')]),patch.object(M,'recursos',return_value={'ram_usada_mib':0}),patch.object(O,'acreditar_pesos_locales'),patch.object(O,'solicitar',return_value={'models':[{'name':'qwen3:8b'}]}) as solicitar,patch.object(O,'ABRIR',return_value=self.flujo()),redirect_stdout(io.StringIO()):
            resultado=M.medir('modelo-local',4096,0,'1m','Reglas sintéticas')
        self.assertEqual(resultado['correctos_iniciales'],1)
        self.assertIsNotNone(resultado['casos'][0]['primer_token_s'])
        self.assertTrue(all(c.args[0]=='/api/ps' for c in solicitar.call_args_list))
        self.assertEqual(resultado['modelos_iniciales'],[{'name':'qwen3:8b'}])

    def test_main_usa_ajustes_persistidos_sin_cambiar_instalacion(self):
        ajustes=dict(C.DEFAULT,modelo=C.MODELO_COTIDIANO,keep_alive='1m',hilos=4,modo_gpu='cpu')
        with tempfile.TemporaryDirectory() as tmp:
            informe=str(Path(tmp)/'medida.json');antes=os.environ.get('JARVIS_DIR')
            with patch.object(C,'leer',return_value=(ajustes,'')),patch.object(M,'medir',return_value={'ok':True}) as medir,patch('sys.argv',['medir','--informe',informe]):M.main()
            self.assertEqual(medir.call_args.args[:4],(C.MODELO_COTIDIANO,8192,4,'1m'))
            self.assertEqual(os.environ.get('JARVIS_DIR'),antes);self.assertTrue(Path(informe).is_file())

    def test_medidor_deepseek_comprueba_texto_tras_protocolo_sin_formatearlo(self):
        propuesta=json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'CASO_1'})
        flujo=io.BytesIO((json.dumps({'message':{'content':propuesta},'done':True})+'\n').encode())
        with patch.object(M,'CASOS',[('literal','Solo CASO_1',r'^CASO_1$')]),patch.object(M,'recursos',return_value={'ram_usada_mib':0}),patch.object(O,'acreditar_pesos_locales'),patch.object(O,'solicitar',return_value={'models':[]}),patch.object(O,'ABRIR',return_value=flujo) as abrir,redirect_stdout(io.StringIO()):
            resultado=M.medir(C.MODELO_PREDETERMINADO,4096,0,'1m','Reglas sintéticas')
        self.assertEqual(resultado['correctos_iniciales'],1)
        self.assertEqual(resultado['casos'][0]['respuesta'],'CASO_1')
        self.assertIn('format',json.loads(abrir.call_args.args[0].data))

    def test_json_incompleto_no_pasa_por_contener_la_etiqueta(self):
        flujo=io.BytesIO((json.dumps({'message':{'content':'{"respuesta":"CASO_1"'},'done':True})+'\n').encode())
        with patch.object(M,'CASOS',[('literal','Solo CASO_1',r'CASO_1')]),patch.object(M,'recursos',return_value={'ram_usada_mib':0}),patch.object(O,'acreditar_pesos_locales'),patch.object(O,'solicitar',return_value={'models':[]}),patch.object(O,'ABRIR',return_value=flujo),redirect_stdout(io.StringIO()):
            resultado=M.medir(C.MODELO_PREDETERMINADO,4096,0,'1m','Reglas sintéticas')
        self.assertEqual(resultado['correctos_iniciales'],0);self.assertTrue(resultado['casos'][0]['error'])


if __name__=='__main__':unittest.main()
