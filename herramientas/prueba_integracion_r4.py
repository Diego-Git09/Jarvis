import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import metricas_modelos as M
import lecturas_prueba_r4 as L
class Pruebas(unittest.TestCase):
    def test_respuesta_del_agente_registra_modelo_y_tiempo(self):
        import jarvis_agente as J
        with tempfile.TemporaryDirectory() as tmp,patch.object(M,'ARCHIVO',Path(tmp)/'metricas.json'):
            e={};h=[{'role':'user','content':'Explica un ejemplo sintético'}]
            def responder(h,enviar,confirmar,e,*args):
                enviar(h);e['_ultima_decision_modelo']={'modelo':'qwen3:8b','regla':'consulta','clase':'simple'};return 'Ejemplo'
            with patch.object(J,'_responder_con_respaldo',side_effect=responder):
                self.assertEqual(J.responder_con_respaldo(h,lambda _:None,lambda _:False,e),'Ejemplo')
            self.assertEqual(next(iter(M.leer()['grupos'].values()))['respuestas'],1)
    def test_peticion_de_no_guardar_no_deja_contador(self):
        import jarvis_agente as J
        with tempfile.TemporaryDirectory() as tmp,patch.object(M,'ARCHIVO',Path(tmp)/'metricas.json'):
            def responder(h,enviar,*args):enviar(h);return 'Dato temporal'
            with patch.object(J,'_responder_con_respaldo',side_effect=responder):
                J.responder_con_respaldo([{'role':'user','content':'no guardes esto, es privado'}],lambda _:None,lambda _:False,{})
            self.assertFalse(M.ARCHIVO.exists())
    def test_broker_rechaza_lectura_antigua_sin_inventar_valores(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'sensores_reales.json';foto={'ram':{'total':123},'termica':{'cpu_c':62}}
            p.write_text(json.dumps({'monotonico':time.monotonic(),'foto':foto}))
            proceso=Mock();proceso.poll.return_value=None
            with patch.object(L.subprocess,'Popen',return_value=proceso):leer,cerrar=L.iniciar(tmp)
            self.assertEqual(leer(),foto)
            p.write_text(json.dumps({'monotonico':time.monotonic()-20,'foto':foto}))
            with self.assertRaises(ValueError):leer()
            cerrar();proceso.terminate.assert_called_once()
    def test_aviso_termico_conserva_solo_metadatos(self):
        import control_recursos as R,cliente_ollama as O
        foto={'ram':{'usada':R.GIB,'tope':8*R.GIB},'gpu':{'ok':True,'gpu':[{'libre_mib':7000}]},'termica':{'temperatura':81,'cpu_c':62}}
        cliente=Mock();cliente.ErrorOllama=O.ErrorOllama;cliente.solicitar.return_value={'models':[]}
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(R,'instantanea',return_value=foto),patch.object(R,'estimar',return_value={'vram':R.GIB,'ram':R.GIB}),patch.object(R,'_ULTIMO_AVISO',None),patch.object(R,'_VACIANDO_HASTA',0):
            with self.assertRaises(O.ErrorOllama):R.comprobar(cliente,{'model':'qwen3:8b'})
            self.assertEqual(R._ULTIMO_AVISO['gpu_c'],81);self.assertEqual(set(R._ULTIMO_AVISO),{'fecha','gpu_c','cpu_c','motivos'})
if __name__=='__main__':unittest.main()
