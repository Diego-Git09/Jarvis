"""Un registro dañado no debe apagar las sesiones sanas ni atascar el cierre."""
import json,os,tempfile,time,unittest
from pathlib import Path
from servicio_ollama import SesionOllama,clientes_vivos,guardar_json,identidad,leer_json
from salud_ollama import comprobar
from soporte_pruebas_servicio import ejecutable,puerto_libre,esperar

class Pruebas(unittest.TestCase):
 def test_directorio_en_lugar_de_json_no_filtra_descriptores(self):
  with tempfile.TemporaryDirectory() as t:
   antes=len(list(Path('/proc/self/fd').iterdir()))
   for _ in range(20):
    with self.assertRaises((OSError,ValueError)):leer_json(Path(t))
   self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),antes)
 def test_lease_invalido_no_apaga_un_cliente_sano(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=SesionOllama('http://127.0.0.1:'+str(puerto_libre()),raiz=r/'control',ejecutable=ejecutable(r),permitir_pruebas=True)
   try:
    self.assertTrue(s.asegurar(timeout=4)['ok'])
    f=s.raiz/'cliente-danado.json';f.write_text('{');f.chmod(0o600)
    time.sleep(.45)
    self.assertTrue(comprobar(s.url)['ok'],'Un lease dañado apagó el servidor de la sesión sana')
    self.assertTrue(f.exists(),'El contenido inválido se conserva para revisión')
   finally:
    s.cerrar();esperar(lambda:not comprobar(s.url,.1)['ok'],timeout=5)
    p=getattr(s,'_supervisor',None)
    if p is not None:p.wait(timeout=5)
 def test_variantes_de_metadata_invalida_se_ignoran_sin_borrar(self):
  for i,raw in enumerate(('{','[]','null','true','""','{"pid":true}','{"pid":"1"}','{"pid":-1}','{"pid":1,"nacimiento":false}','['*1500)):
   with self.subTest(i=i),tempfile.TemporaryDirectory() as t:
    root=Path(t);f=root/'cliente-invalido.json';f.write_text(raw);f.chmod(0o600)
    # Los JSON que son diccionarios pero no identifican un proceso se retiran;
    # los que ni siquiera se pueden interpretar permanecen intactos.
    self.assertEqual(clientes_vivos(root),[])
 def test_lease_valido_tiene_prioridad_sobre_archivos_rotos(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);sano=r/'cliente-sano.json'
   guardar_json(sano,{'pid':os.getpid(),'nacimiento':identidad(os.getpid())})
   malo=r/'cliente-malo.json';malo.write_text('{');malo.chmod(0o600)
   self.assertEqual(clientes_vivos(r),[sano])

if __name__=='__main__':unittest.main()
