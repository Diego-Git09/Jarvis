"""Referencias con diez formas por caso, sin datos reales ni inferencia."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import hilo_conversacion as H,interfaz_jarvis as I,jarvis_agente as J
OPCIONES=('la segunda opcion','la segunda opción','LA SEGUNDA OPCION','la 2da opcion','opcion 2','la opcion 2','la alternativa 2','segunda opcion','segunda opción','el segundo')
RECUERDO=('que te pedi antes?','q te pedi antes','QUE TE PEDI ANTES','que te pregunté antes','cual fue la tarea te pedi','que tarea te pedi antes','que te solicite antes','que te dije antes','que te pedi recien','que te pregunte anteriormente')
class Pruebas(unittest.TestCase):
 def test_diez_opciones_ausentes_no_se_inventan(self):
  for p in OPCIONES:
   with self.subTest(p=p):
    h=[{'role':'user','content':'que es Docker'},{'role':'assistant','content':'Docker agrupa aplicaciones en contenedores.'}]
    ok,t=I.comando(p,h,{},lambda *_:self.fail('No hay acciones'),J.SISTEMA,confirmar_plan=lambda _:self.fail('No hay permisos'))
    self.assertTrue(ok);self.assertIn('?',t)
 def test_diez_recuperaciones_omiten_confirmacion_sin_contenido(self):
  for p in RECUERDO:
   with self.subTest(p=p):
    h=[{'role':'user','content':'Explícame Docker.'},{'role':'assistant','content':'Explicación anterior.'},{'role':'user','content':'listo'},{'role':'assistant','content':'De acuerdo.'},{'role':'user','content':p}]
    t=H.recordar_peticion(h,p);self.assertIsNotNone(t);self.assertIn('Explícame Docker.',t);self.assertNotIn('«listo»',t)
 def test_ordinales_usan_manifiesto_y_contenidos_distintos(self):
  import tandas_documentales as T
  from referencias_adjuntas import atender
  with tempfile.TemporaryDirectory(dir=T.L.RAIZ) as tmp,patch.object(T,'RAIZ',Path(tmp)/'indice'):
   a=Path(tmp)/'alfa.txt';b=Path(tmp)/'beta.txt';a.write_text('LUNA: astronomía y cráteres');b.write_text('PLANTA: botánica y raíces')
   d=T.indexar(T.crear([a,b])['id'],False);e={'_tanda_documentos':d['id']}
   for p in ('la primera habla de q y la segunda?','de que trata la primera y la segunda','resume ambos archivos','resumeme los dos','resumen de la primera','contenido del segundo','que dice el segundo documento','muestrame la primera fuente','resume el primer archivo','QUE DICE LA SEGUNDA'):
    with self.subTest(p=p):
     t=atender(p,e);self.assertIsNotNone(t)
     if 'primera' in p or 'primer archivo' in p:self.assertIn('alfa.txt',t);self.assertIn('LUNA',t)
     if 'segunda' in p.casefold() or 'segundo' in p:self.assertIn('beta.txt',t);self.assertIn('PLANTA',t)
 def test_posicion_ausente_pide_nombre(self):
  from referencias_adjuntas import atender
  import tandas_documentales as T
  with patch.object(T,'cargar',return_value={'archivos':[{'nombre':'solo.txt'}]}):
   t=atender('contenido del segundo',{'_tanda_documentos':'a'*32});self.assertIn('?',t);self.assertIn('solo.txt',t)
if __name__=='__main__':unittest.main()
