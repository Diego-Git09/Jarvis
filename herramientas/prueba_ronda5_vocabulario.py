"""Treinta variantes de los tres fallos, sin confirmar términos por el usuario."""
import unittest
from unittest.mock import patch
import normalizacion_entrada as N
import interfaz_jarvis as I,jarvis_agente as J
class Pruebas(unittest.TestCase):
 def test_peos_observado_se_interpreta_como_malos(self):
  for p in ('estan un poquitos peos los prints de jarvis','estan peos los prints','ESTAN PEOS LOS PRINTS','los prints estan peos','los mensajes estan peos','se ven peos los prints','encuentro peos los prints','estan un poquito peos los textos','me salen peos los prints','estan muy peos los prints'):
   with self.subTest(p=p):
    ok,t=I.comando(p,[],{},lambda *_:self.fail('No modifica nada'),J.SISTEMA);self.assertTrue(ok);self.assertNotIn('inapropiad',t.lower());self.assertIn('?',t)
 def test_juego_pegado_es_congelamiento_sin_tocar_procesos(self):
  for p in ('cachai que se me pego el juego, se puede hacer algo','se me pegó el juego','SE ME PEGO EL JUEGO','se me pego el juego q hago','oye se me pego el juego','se me pego el juego otra vez','se pego el juego','se quedo pegado el juego','el juego se quedo pegado','el juego se congelo'):
   with self.subTest(p=p):
    ok,t=I.comando(p,[],{},lambda *_:self.fail('No cierra procesos'),J.SISTEMA);self.assertTrue(ok);self.assertRegex(t.lower(),'congel|inm[oó]vil|fps');self.assertNotRegex(t,'Windows|macOS')
 def test_fome_sin_confirmar_no_se_traduce_a_aburrido(self):
  with patch('confirmar_vocabulario.leer',return_value={}):
   for p in ('esta fome el rendimiento del compu q hago','esta fome el compu','ESTA FOME EL RENDIMIENTO','el rendimiento esta fome','se siente fome','encuentro fome esto','esta muy fome','que fome el rendimiento','anda fome el computador','me parece fome'):
    with self.subTest(p=p):self.assertTrue(any(x[0]=='fome' for x in N.analizar(p).dudas));self.assertNotIn(('fome','aburrido'),N.analizar(p).cambios)
 def test_confirmacion_previa_se_respeta_sin_cambiar_lexico_base(self):
  with patch('confirmar_vocabulario.leer',return_value={'fome':{'estado':'observado'}}):
   self.assertIn('aburrido',N.analizar('esta fome').vista)
 def test_literal_protegido_no_se_reescribe(self):
  for p in ('crea "peos.txt" con "esta fome"','print("se me pego el juego")','/leer "fome.txt"'):
   self.assertIn('fome' if 'fome' in p else 'se me pego el juego',N.analizar(p).vista)
if __name__=='__main__':unittest.main()
