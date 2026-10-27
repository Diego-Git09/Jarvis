"""Simulación explícita: admisión, límites, CPU y avisos comprobados de reposo."""
import unittest
from unittest.mock import patch,Mock
import control_recursos as R
import configuracion_jarvis as C
import cliente_ollama as O

INFO={'model_info':{'general.architecture':'qwen3','general.parameter_count':8200000000,'qwen3.block_count':36,'qwen3.embedding_length':4096,'qwen3.attention.head_count':32,'qwen3.attention.head_count_kv':8},'details':{'quantization_level':'Q4_K_M'}}

def foto(libre=7800,usada=10):
    return {'ram':{'total':32*R.GIB,'usada':usada*R.GIB,'disponible':(32-usada)*R.GIB,'tope':int(32*R.GIB*.8)},'gpu':{'ok':True,'gpu':[{'libre_mib':libre}]},'juegos':[],'pesados':[]}

class Pruebas(unittest.TestCase):
    def test_poca_vram_ofrece_tres_opciones_sin_matar_procesos(self):
        e=R.estimar(INFO,{'num_ctx':8192},5200000000);r=R.evaluar(foto(200),e)
        self.assertFalse(r['permitido'])
        for t in ['esperar','/gpu cpu','/liberar','No cerré otros programas']:self.assertIn(t,r['aviso'])
    def test_cpu_sigue_comprobando_ram(self):
        e=R.estimar(INFO,{'num_ctx':32768,'num_gpu':0},5200000000)
        self.assertFalse(R.evaluar(foto(0,24),e)['permitido']);self.assertEqual(e['vram'],0)
    def test_actividad_real_u_otro_proceso_bloquea_gpu_pero_no_cpu(self):
        for campo,dato in [('juegos',['steam']),('pesados',[{'nombre':'render','mib':3000}])]:
            f=foto();f[campo]=dato
            if campo=='juegos':f['gpu']['gpu'][0]['uso_porcentaje']=95
            self.assertFalse(R.evaluar(f,R.estimar(INFO,{},5200000000))['permitido'])
            self.assertTrue(R.evaluar(f,R.estimar(INFO,{'num_gpu':0},5200000000))['permitido'])
    def test_capas_no_inventadas_ni_excesivas(self):
        for n in [-3,38,'12',True]:
            with self.assertRaises(ValueError):R.estimar(INFO,{'num_gpu':n})
        a=R.estimar(INFO,{'num_gpu':12},5200000000);b=R.estimar(INFO,{'num_gpu':24},5200000000)
        self.assertLess(a['vram'],b['vram']);self.assertGreater(a['ram'],b['ram'])
    def test_reposo_no_anuncia_descarga_antes_de_api_ps(self):
        c=Mock();c.solicitar.return_value={'models':[{'name':'modelo'}]}
        with patch.object(R,'_REGISTRO',{'modelo':10}):
            self.assertFalse(R.comprobar_reposo(c,11));c.solicitar.return_value={'models':[]}
            self.assertEqual(len(R.comprobar_reposo(c,11)),1);self.assertFalse(R.comprobar_reposo(c,12))
        R.consumir_avisos()
    def test_config_mixta_valida_estrictamente(self):
        self.assertEqual(C.validar({'modo_gpu':'mixto','capas_gpu':12})['capas_gpu'],12)
        for n in [0,-1,True,999]:
            with self.assertRaises(ValueError):C.validar({'modo_gpu':'mixto','capas_gpu':n})
    def test_cliente_aplica_mixto_sin_mutar_cuerpo_original(self):
        cuerpo={'model':'modelo','messages':[{'role':'user','content':'hola'}]}
        with patch.object(O,'leer',return_value=(C.validar({'modo_gpu':'mixto','capas_gpu':12}),'') ),patch('entorno_jarvis.en_pruebas',return_value=True):
            r=O.preparar_cuerpo('/api/chat',cuerpo,10**15)
        self.assertEqual(r['options']['num_gpu'],12);self.assertNotIn('options',cuerpo)
    def test_descarga_sigue_disponible_con_poca_memoria(self):
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(R,'instantanea',side_effect=AssertionError('Descargar nunca requiere reservar RAM')):
            self.assertIsNone(R.comprobar(O,{'model':'modelo','keep_alive':0}))

    def test_mixto_no_infla_contexto_ni_inventa_capas_del_embedding(self):
        info={'model_info':{'general.architecture':'bert','bert.block_count':12}}
        ajustes=C.validar({'modo_gpu':'mixto','capas_gpu':24,'num_ctx':32768})
        with patch.object(O,'leer',return_value=(ajustes,'')),patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'acreditar_pesos_locales',return_value=info):
            cuerpo=O.preparar_cuerpo('/api/embed',{'model':'auxiliar-local','input':'dato sintético'},10**15)
        self.assertEqual(cuerpo['options']['num_gpu'],13);self.assertNotIn('num_ctx',cuerpo['options'])

    def test_mixto_reutiliza_su_carga_verificada_sin_pedir_memoria_doble(self):
        cuerpo={'model':'modelo','options':{'num_ctx':32768,'num_gpu':24}}
        e=R.estimar(INFO,cuerpo['options'],5200000000)
        m={'name':'modelo','context_length':32768,'size':10000000000,'size_vram':6500000000}
        f=foto(700)
        with patch.object(R,'_CONFIGURACIONES',{'modelo':(32768,24)}):
            self.assertTrue(R.residente_reutilizable(m,cuerpo,e));self.assertTrue(R.evaluar(f,e,[m])['permitido'])
            self.assertFalse(R.residente_reutilizable(m,dict(cuerpo,options={'num_ctx':32768,'num_gpu':12}),e))
        with patch.object(R,'_CONFIGURACIONES',{}):self.assertFalse(R.residente_reutilizable(m,cuerpo,e))

    def test_liberar_manual_no_repite_un_aviso_de_reposo(self):
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(R,'_REGISTRO',{'modelo':1}),patch.object(R,'_CONFIGURACIONES',{'modelo':(8192,24)}),patch.object(R,'_VACIANDO_HASTA',0):
            R.registrar(Mock(),{'model':'modelo','keep_alive':0})
            self.assertFalse(R._REGISTRO);self.assertFalse(R._CONFIGURACIONES);self.assertGreater(R._VACIANDO_HASTA,0)

    def test_gpu_ya_residente_no_reserva_otra_vez_pesos_y_kv(self):
        cuerpo={'model':'modelo','options':{'num_ctx':16384,'num_gpu':37}}
        e=R.estimar(INFO,cuerpo['options'],5225376595)
        m={'name':'modelo','context_length':16384,'size':7402726358,'size_vram':7402726358}
        self.assertTrue(R.residente_reutilizable(m,cuerpo,e))
        for campo in ('size','size_vram'):
            incompleto=dict(m);incompleto.pop(campo)
            self.assertFalse(R.residente_reutilizable(incompleto,cuerpo,e))
        self.assertTrue(R.evaluar(foto(396),e,[m])['permitido'])
        self.assertFalse(R.evaluar(foto(100),e,[m])['permitido'])
        self.assertFalse(R.evaluar(foto(396),e)['permitido'])

if __name__=='__main__':unittest.main()
