import subprocess
import unittest
from unittest.mock import patch
import control_recursos as R

class Pruebas(unittest.TestCase):
    def foto(self,t):return {'ram':{'usada':R.GIB,'tope':8*R.GIB},'gpu':{'ok':True,'gpu':[{'libre_mib':7000}]},'termica':t}
    def estimacion(self):return {'vram':R.GIB,'ram':R.GIB}
    def test_temperatura_alta_ofrece_tres_opciones(self):
        r=R.evaluar(self.foto({'temperatura':90}),self.estimacion());self.assertFalse(r['permitido']);self.assertIn('1)',r['aviso']);self.assertIn('2)',r['aviso']);self.assertIn('3)',r['aviso'])
    def test_limite_bajo_no_se_modifica(self):
        r=R.evaluar(self.foto({'limite_w':30}),self.estimacion());self.assertFalse(r['permitido']);self.assertIn('potencia',r['aviso'])
    def test_sensores_no_disponibles_no_equivalen_a_cero(self):
        with patch.object(R.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'46, [N/A]\n','')):
            t=R.termica()
        self.assertEqual(t['temperatura'],46);self.assertIsNone(t['limite_w'])

if __name__=='__main__':unittest.main()
