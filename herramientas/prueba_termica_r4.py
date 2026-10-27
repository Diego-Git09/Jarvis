import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import control_recursos as R
import politica_termica as P
class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=patch.object(P,'ARCHIVO',Path(self.tmp.name)/'umbrales.json');self.p.start();self.addCleanup(self.p.stop)
    def evaluar(self,t,v=1):return R.evaluar({'ram':{'usada':R.GIB,'tope':8*R.GIB},'gpu':{'ok':True,'gpu':[{'libre_mib':7000}]},'termica':t},{'vram':v*R.GIB,'ram':R.GIB})
    def test_gpu_inicial_80_y_cuatro_opciones(self):
        self.assertTrue(self.evaluar({'temperatura':79})['permitido'])
        r=self.evaluar({'temperatura':80});self.assertFalse(r['permitido'])
        for x in ('esperar','/gpu cpu','/liberar','/contexto 4096','s/n'):self.assertIn(x,r['aviso'])
    def test_cpu_alta_tambien_detiene_cpu_sin_gpu(self):self.assertFalse(self.evaluar({'cpu_c':90},v=0)['permitido'])
    def test_configura_solo_con_permiso_y_comprueba(self):
        P.comando('/temperatura gpu 75',lambda _:False);self.assertFalse(P.ARCHIVO.exists())
        P.comando('/temperatura gpu 75',lambda _:True);self.assertEqual(P.leer()['gpu'],75);self.assertEqual(P.ARCHIVO.stat().st_mode&0o777,0o600)
        self.assertFalse(self.evaluar({'temperatura':76})['permitido'])
    def test_umbral_invalido_y_archivo_danado_no_reemplazados(self):
        P.comando('/temperatura cpu 200',lambda _:self.fail('Fuera de rango'))
        P.ARCHIVO.write_text('dañado');P.comando('/temperatura gpu 75',lambda _:self.fail('No sobrescribir'))
        self.assertEqual(P.ARCHIVO.read_text(),'dañado');self.assertFalse(self.evaluar({})['permitido'])
    def test_lee_cpu_aunque_nvidia_falle_sin_inventar_potencia(self):
        def falso(args,**kw):
            if args[0]=='nvidia-smi':return subprocess.CompletedProcess(args,9,'','')
            return subprocess.CompletedProcess(args,0,json.dumps({'coretemp-isa-0000':{'Package id 0':{'temp1_input':62}},'nvme-pci':{'Composite':{'temp1_input':20}}}),'')
        with patch.object(R.subprocess,'run',side_effect=falso):t=R.termica()
        self.assertIsNone(t['temperatura']);self.assertEqual(t['cpu_c'],62);self.assertIsNone(t['cpu_w'])
    def test_lecturas_nunca_escriben_sistema(self):
        calls=[]
        def falso(args,**kw):calls.append(args);return subprocess.CompletedProcess(args,0,'42, 115, 6.4\n' if args[0]=='nvidia-smi' else '{}','')
        with patch.object(R.subprocess,'run',side_effect=falso):texto='\n'.join(R.diagnostico_termico())
        self.assertIn('42.0 °C',texto);self.assertIn('6.4 W',texto);self.assertIn('no disponible',texto)
        self.assertEqual({x[0] for x in calls},{'nvidia-smi','sensors'});self.assertFalse(P.ARCHIVO.exists())
if __name__=='__main__':unittest.main()
