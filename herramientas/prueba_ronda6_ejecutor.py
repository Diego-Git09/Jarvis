"""El ejecutor debe separar raíces por archivo y admitir procesos concurrentes."""
import tempfile,unittest,sys,subprocess
from pathlib import Path
from unittest.mock import patch
import ejecutar_pruebas as R

class Pruebas(unittest.TestCase):
 def escenario(self,args):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'prueba_uno.py').write_text('');(d/'prueba_dos.py').write_text('')
   raices=[]
   def correr(cmd,**kw):
    raiz=Path(kw['env']['JARVIS_DIR']);self.assertTrue((raiz/'trabajo/prueba.txt').exists());raices.append(str(raiz))
    return subprocess.CompletedProcess(cmd,0,'','Ran 1 test in 0.001s\nOK\n')
   with patch.object(R,'__file__',str(d/'ejecutar_pruebas.py')),patch.object(sys,'argv',['runner']+args),patch.object(R.subprocess,'run',side_effect=correr):
    self.assertEqual(R.main(),0)
   self.assertEqual(len(raices),2);self.assertEqual(len(set(raices)),2,'Cada archivo necesita su propia raíz')
 def test_raiz_temporal_por_archivo(self):self.escenario([])
 def test_procesos_configurables(self):self.escenario(['--procesos','2'])
if __name__=='__main__':unittest.main()
