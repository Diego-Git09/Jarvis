"""Contratos de API, unidades medidas y fuentes; no acredita corrección universal."""
import unittest
from unittest.mock import Mock
import fiabilidad_tecnica as F,consultas_equipo as E
class Pruebas(unittest.TestCase):
 def test_anotacion_inventada_y_herencia_invalida_se_detectan(self):
  for t in ('```kotlin\n@DatabaseBuilder class Base {}\n```','```kotlin\nabstract class Base : RoomDatabase { }\n```','```kotlin\nRoom.databaseBuilder(ctx,Base::class.java,"x").allowMainThreadQueries().build()\n```'):
   self.assertTrue(F.incumplimientos('como guardo datos con room en kotlin',t))
 def test_herencia_correcta_no_se_marca(self):
  self.assertFalse(F.incumplimientos('room kotlin','```kotlin\n@Database(entities=[Persona::class],version=1)\nabstract class Base : RoomDatabase() { }\n```'))
 def test_script_sin_evidencia_se_detecta(self):
  self.assertTrue(F.incumplimientos('instalar apex','```sql\n@swddo.sql\n```'))
 def test_guia_directa_no_interpreta_orden_de_escritura(self):
  self.assertIsNone(F.guia_directa('crea un archivo con los pasos de room'))
  self.assertIsNotNone(F.guia_directa('como guardo datos con room en kotlin'))
 def test_vram_usa_size_vram_no_el_nombre(self):
  c=Mock();c.solicitar.return_value={'models':[{'name':'qwen3:8b','size':6*1024**3,'size_vram':5*1024**3,'context_length':8192}]}
  t=E.modelos_memoria('al tiro dime cuanto pesa un modelo de 8b en la vram',c)
  self.assertIn('5120 MiB',t);self.assertIn('5.00 GiB',t);self.assertIn('bytes por peso',t);c.solicitar.assert_called_once_with('/api/ps',timeout=3)
 def test_sin_lectura_no_se_inventa_consumo(self):
  c=Mock();c.solicitar.side_effect=ConnectionError('Fallo');t=E.modelos_memoria('cuanto ocupa un modelo 8b en vram',c);self.assertIn('no es una medición',t)
 def test_guia_conceptual_lleva_fuente_y_limites_en_prompt_reducido(self):
  import consulta_textual as T
  t=T.sistema('que es Docker');self.assertIn('Base documental local verificada',t);self.assertIn('sin verificar',t)
 def test_herencia_sin_cerca_de_codigo_tambien_se_verifica(self):
  self.assertTrue(F.incumplimientos('RoomDatabase lleva parentesis al heredar en Kotlin?','abstract class Base : RoomDatabase { }'))
  self.assertFalse(F.incumplimientos('RoomDatabase en Kotlin','abstract class Base : RoomDatabase() { }'))
  self.assertIn('RoomDatabase()',F.guia_directa('RoomDatabase lleva parentesis al heredar en Kotlin?'))
 def test_sqlplus_sin_clave_no_recibe_credenciales_en_argumentos(self):
  p='Como me conecto a SQLPlus sin escribir la clave en el comando?'
  self.assertTrue(F.incumplimientos(p,'sqlplus ejemplo/VALOR_FICTICIO@SERVICIO'))
  t=F.guia_directa(p);self.assertIn('sqlplus /nolog',t);self.assertIn('CONNECT USUARIO@SERVICIO',t);self.assertIn('sin mostrarla',t)
 def test_guias_distinguen_configuracion_minimo_y_ejecucion(self):
  t=F.guia_directa('Que debo comprobar antes de elegir la version de Java de Spring?')
  self.assertIn('mínimo Java17',t);self.assertIn('ejemplo local usa Java21',t)
  self.assertIn('No acredita',F.guia_directa('Que prueba la compilacion de un APK de Compose y Room?'))
  self.assertIn('clase',F.guia_directa('Un ViewModel es una opcion de la plantilla New Project?'))
 def test_endpoint_documentado_no_inventa_repositorios(self):
  t=F.guia_directa('como hago un endpoint rest en spring boot q devuelva una lista de productos')
  self.assertIn('List<Map<String, Object>>',t);self.assertNotIn('Productero',t);self.assertNotIn('productoRepository.findAll',t)
 def test_cuantizacion_tambien_dispara_formula_y_lectura(self):
  c=Mock();c.solicitar.return_value={'models':[]}
  t=E.modelos_memoria('Por que un modelo Q4 de 8B no ocupa necesariamente 16 GB de VRAM?',c)
  self.assertIn('bytes por peso',t);c.solicitar.assert_called_once_with('/api/ps',timeout=3)
if __name__=='__main__':unittest.main()
