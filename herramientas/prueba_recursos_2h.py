"""Recursos: pruebas sintéticas; no descargan modelos ni afectan otras apps."""
import io,json,threading,unittest
import urllib.error
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock,patch
import recursos_ollama as R
import configuracion_jarvis as C
import cliente_ollama as O
from interfaz_local import comando_local


class Cliente:
    BASE='http://127.0.0.1:11434'
    def reservar(self,timeout):return nullcontext()
    def __init__(self):self._TURNO=threading.RLock();self.modelos=[C.MODELO_PREDETERMINADO,'otro-modelo:8b'];self.llamadas=[];self.persistir=False
    def solicitar(self,ruta,cuerpo=None,**kw):
        self.llamadas.append((ruta,cuerpo))
        if ruta=='/api/ps':return {'models':[{'name':n,'size_vram':12345678} for n in self.modelos]}
        if ruta=='/api/generate':
            if not self.persistir:self.modelos.remove(cuerpo['model'])
            return {'done':True}
        raise AssertionError('Operación no admitida')


class Pruebas(unittest.TestCase):
    def test_auxiliares_no_exceden_reposo_elegido(self):
        self.assertEqual(R.limitar_reposo('30m','1m'),'1m')
        self.assertEqual(R.limitar_reposo('5s','1m'),'5s')
        self.assertEqual(R.limitar_reposo(0,'1m'),0)
        self.assertEqual(R.limitar_reposo('30m','0'),'0')
        self.assertEqual(R.limitar_reposo(None,'1m'),'1m')
        self.assertEqual(R.limitar_reposo('-1','1m'),'1m')

    def test_automatico_amplia_y_manual_prevalece(self):
        a=dict(C.DEFAULT)
        self.assertEqual(R.plazo(a,C.MODELO_PREDETERMINADO),180)
        self.assertEqual(R.plazo(a,C.MODELO_COTIDIANO),120)
        self.assertEqual(R.plazo(a,C.MODELO_COTIDIANO,9000),240)
        self.assertEqual(R.plazo(a,C.MODELO_PREDETERMINADO,codigo=True),300)
        self.assertEqual(R.plazo(dict(a,timeout_auto=False,timeout_modelo=30),C.MODELO_PREDETERMINADO,codigo=True),30)

    def test_gpu_usa_comando_fijo_y_lectura_validada(self):
        with patch.object(R.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='8192, 2000, 6192, 5\n')) as ejecutar:
            r=R.gpu()
        self.assertTrue(r['ok']);self.assertEqual(r['gpu'][0]['libre_mib'],6192)
        self.assertEqual(ejecutar.call_args.args[0][0],'nvidia-smi');self.assertEqual(ejecutar.call_args.kwargs['timeout'],3)

    def test_gpu_invalida_o_ausente_no_inventa(self):
        for texto in ['8192, XX, 0, 0','8192, 1, 8191, 101','0, 0, 0, 0']:
            with patch.object(R.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=texto)):
                self.assertFalse(R.gpu()['ok'])
        with patch.object(R.subprocess,'run',side_effect=FileNotFoundError):self.assertFalse(R.gpu()['ok'])

    def test_libera_solo_candidatos_y_comprueba_resultado(self):
        c=Cliente();t=R.liberar(c,dict(C.DEFAULT),lambda _:True)
        self.assertIn('comprobada',t);self.assertEqual(c.modelos,['otro-modelo:8b'])
        self.assertEqual([b for r,b in c.llamadas if r=='/api/generate'],[{'model':C.MODELO_PREDETERMINADO,'keep_alive':0,'stream':False}])

    def test_no_confirma_si_otra_app_lo_recarga(self):
        c=Cliente();c.persistir=True
        self.assertIn('no confirmo',R.liberar(c,dict(C.DEFAULT),lambda _:True))

    def test_denegado_no_descarga(self):
        c=Cliente();t=R.liberar(c,dict(C.DEFAULT),lambda _:False)
        self.assertIn('No descargué',t);self.assertFalse(any(r=='/api/generate' for r,b in c.llamadas))

    def test_cola_ocupada_no_lanza_consulta(self):
        c=Cliente();ocupado=threading.Event();fin=threading.Event()
        def retener():
            with c._TURNO:ocupado.set();fin.wait(2)
        h=threading.Thread(target=retener);h.start();ocupado.wait(1)
        try:
            self.assertIn('en curso',R.liberar(c,dict(C.DEFAULT),lambda _:True));self.assertFalse(c.llamadas)
        finally:fin.set();h.join()

    def test_desconocido_no_se_iguala_a_descargado(self):
        c=Cliente()
        with patch.object(c,'solicitar',return_value={}):
            with self.assertRaises(ValueError):R.cargados(c)

    def test_reposo_se_guarda_y_invalido_no_modifica(self):
        a=dict(C.DEFAULT);e={}
        with patch('interfaz_local.C.guardar',side_effect=C.validar) as guardar:
            ok,t=comando_local('/reposo 1m',[],e,lambda _:False,a,lambda:None,None)
            self.assertTrue(ok);self.assertEqual(a['keep_alive'],'1m');guardar.assert_called_once()
        antes=dict(a)
        with patch('interfaz_local.C.guardar',side_effect=C.validar):
            comando_local('/reposo -1',[],e,lambda _:False,a,lambda:None,None)
        self.assertEqual(a,antes)

    def test_timeout_manual_y_vuelta_auto(self):
        a=dict(C.DEFAULT)
        with patch('interfaz_local.C.guardar',side_effect=C.validar):
            comando_local('/timeout 40',[],{},lambda _:False,a,lambda:None,None)
            self.assertFalse(a['timeout_auto']);self.assertEqual(a['timeout_modelo'],40)
            comando_local('/timeout auto',[],{},lambda _:False,a,lambda:None,None)
            self.assertTrue(a['timeout_auto'])

    def test_config_no_admite_timeout_auto_no_booleano(self):
        with self.assertRaises(ValueError):C.validar(dict(C.DEFAULT,timeout_auto='sí'))

    def test_no_guarda_destino_externo(self):
        with patch('interfaz_local.C.guardar') as guardar:
            ok,t=comando_local('/ollama_url https://ejemplo.invalid:11434',[],{},lambda _:True,dict(C.DEFAULT),lambda:None,None)
        self.assertTrue(ok);self.assertIn('bloqueados',t);guardar.assert_not_called()

    def test_errores_memoria_modelo_y_conexion_se_distinguen(self):
        def error(codigo,detalle):return O._error(urllib.error.HTTPError('http://localhost',codigo,'',{},io.BytesIO(json.dumps({'error':detalle}).encode())))
        memoria=error(500,'runner out of memory');self.assertEqual(memoria.tipo,'memoria');self.assertFalse(memoria.reintentable)
        self.assertIn('/liberar',str(memoria));self.assertIn('/modelos',str(error(404,'not found')))
        self.assertEqual(O._error(ConnectionRefusedError()).tipo,'conexion')

    def test_diagnostico_no_asegura_ausencia_de_gpu_si_falla(self):
        c=Cliente()
        with patch.object(R,'gpu',return_value={'ok':False,'error':'Lectura no disponible'}):t='\n'.join(R.lineas_diagnostico(c,dict(C.DEFAULT)))
        self.assertIn('Lectura no disponible',t);self.assertIn('Modelos cargados',t);self.assertNotIn('sin GPU',t)


if __name__=='__main__':unittest.main()
