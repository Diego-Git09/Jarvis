"""Rutas sensibles ficticias bajo un hogar temporal, nunca credenciales reales."""
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import acceso_archivos as A
import herramientas_lectura as L
import adjuntos_jarvis as D
import interfaz_documentos as I

PROTEGIDAS=['.netrc','.git-credentials','.docker','.kube','.config/gh','.config/google-chrome','.config/chromium','.mozilla','snap','.bash_history','.local/share/opencode','.config/jarvis']
class Pruebas(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.addCleanup(patch.stopall)
  self.base=Path(self.tmp.name);self.hogar=self.base/'hogar';self.hogar.mkdir()
  patch.object(Path,'home',return_value=self.hogar).start()
  patch.object(A,'listar',return_value=[self.hogar]).start()
  patch.object(L,'RAIZ',self.hogar).start();patch.object(L,'REGISTRO',self.base/'log').start()
 def comprobar(self,ruta):
  p=self.hogar/ruta
  if ruta in {'.netrc','.git-credentials','.bash_history'}:p.parent.mkdir(parents=True,exist_ok=True);p.write_text('R6_TEST');f=p
  else:p.mkdir(parents=True,exist_ok=True);f=p/'ejemplo.txt';f.write_text('R6_TEST')
  self.assertTrue(A.protegida(p));self.assertFalse(A.permitido(f,self.hogar))
  self.assertFalse(L.leer_archivo(str(f))['ok']);self.assertFalse(L.listar_archivos(str(p))['ok'])
  self.assertFalse(L.buscar_texto('R6_TEST',str(p))['ok'])
  with patch.object(D,'_extraer_aislado',return_value=('R6_TEST',{})) as extraer,self.assertRaises((ValueError,L.FueraDeAlcance)):
   D.leer_adjunto(f)
  extraer.assert_not_called()
 def test_hogar_completo_rechazado(self):
  with self.assertRaisesRegex(ValueError,'subcarpeta'):A.validar_carpeta(self.hogar)
  buena=self.hogar/'Documentos';buena.mkdir();self.assertEqual(A.validar_carpeta(buena),buena)
 def test_enlace_hacia_protegido_tambien_falla(self):
  p=self.hogar/'.docker';p.mkdir();f=p/'ejemplo.txt';f.write_text('R6_TEST')
  enlace=self.hogar/'enlace.txt';enlace.symlink_to(f)
  self.assertFalse(L.leer_archivo(str(enlace))['ok'])
 def test_diez_formas_de_pedir_lectura_conservan_la_barrera(self):
  p=self.hogar/'.config/jarvis';p.mkdir(parents=True);f=p/'ejemplo.txt';f.write_text('R6_TEST')
  for verbo in ['lee','leer','leeme','léeme','abre','abrir','muestra','muéstrame','lee el archivo','abre el documento']:
   def accion(n,a):return L.leer_lineas(**a) if n=='leer_lineas' else self.fail(n)
   with self.subTest(verbo=verbo):
    hecho,t=I.comando(verbo+' '+str(f),[],{},accion)
    self.assertTrue(hecho);self.assertIn('Fuera de alcance',t)

for i,ruta in enumerate(PROTEGIDAS,1):setattr(Pruebas,f'test_protegida_{i:02}',lambda self,ruta=ruta:self.comprobar(ruta))
if __name__=='__main__':unittest.main()
