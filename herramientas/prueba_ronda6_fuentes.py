"""Regresiones R6: 10 variantes por cada confusión de fuentes, sin modelo ni MCP."""
import copy
import unittest
from unittest.mock import patch
import alcance_fuentes as A
import referencias_adjuntas as R
from enrutador_modelos import clasificar_peticion

FAMILIAS={
 'ordinal_discurso':['primero explícame qué es una API','PRIMERO EXPLICAME QUE ES UNA API','primero explicame q es una api','Jarvis primero explícame qué es una API','primero dime que es una API','antes que nada primero explica una API','primero explicame que significa API','primero puedes explicarme que es una API?','primero explica para que sirve una API','primero explicame una API porfa'],
 'documento_generico':['qué es un documento','QUE ES UN DOCUMENTO','q es un documento','qué significa documento','explicame que es un documento','dime qué es un documento','como se define un documento','puedes explicar qué es un documento?','primero que es un documento','qué es un documento en informática'],
 'recuerdos':['muéstrame primero los recuerdos','MUESTRAME PRIMERO LOS RECUERDOS','muestrame primero mis recuerdos','primero muestra los recuerdos','muestra primero los recuerdos de Jarvis','quiero ver primero mis recuerdos','muéstrame primero los recuerdos guardados','puedes mostrarme primero los recuerdos?','primero dime los recuerdos disponibles','primero lista los recuerdos'],
 'docker':['resume primero el tema de Docker','RESUME PRIMERO EL TEMA DE DOCKER','resumeme primero el tema de docker','primero resume el tema de Docker','porfa resume primero Docker','puedes resumir primero el tema Docker?','resume primero lo que es Docker','primero quiero un resumen de Docker','resume primero el concepto de Docker','resume primero para que sirve Docker'],
 'paso_guia':['el segundo paso de la guía','EL SEGUNDO PASO DE LA GUIA','explica el segundo paso de la guia','muestra el segundo paso de la guía','cuál es el segundo paso de la guía?','quiero ver el segundo paso de la guia','continúa con el segundo paso de la guía','resume el segundo paso de la guia','dime el segundo paso de la guía','primero explica el segundo paso de la guía'],
}

def estado():
 return {'_tanda_documentos':'a'*32,'_fuentes_tema_activo':True,'_adjuntos_orden':[{'nombre':'uno.txt','ruta':'uno.txt'},{'nombre':'dos.txt','ruta':'dos.txt'}]}

MANIFIESTO={'id':'a'*32,'archivos':[{'nombre':'uno.txt'},{'nombre':'dos.txt'}]}

class Pruebas(unittest.TestCase):
 def negativo(self,p):
  e=estado()
  with patch('tandas_documentales.cargar',return_value=MANIFIESTO) as cargar:
   self.assertFalse(A.preparar([],p,e),'No es una referencia a adjuntos: '+p)
   self.assertIsNone(R.atender(p,e))
   self.assertNotEqual(clasificar_peticion(p,adjuntos=e['_fuentes_turno'])['regla'],'adjuntos')
   cargar.assert_not_called()
 def test_referencias_reales_siguen_disponibles(self):
  for p in ['resume el primer archivo','resume el segundo documento','muestra el tercer pdf','resume ambos archivos','muestra los dos adjuntos','resume los documentos adjuntos','que dice el documento adjunto','resume esta tanda','explicame los archivos adjuntados','resume mis adjuntos']:
   with self.subTest(p=p),patch('tandas_documentales.cargar',return_value=MANIFIESTO):
    self.assertTrue(A.preparar([],p,estado()))
 def test_ordinal_corto_exige_manifiesto_vigente(self):
  for p in ['resume el primero','resume la primera','muestra el segundo','resume la segunda','muestra el tercero','resume la tercera','resume ambos','resume los dos','de que habla la primera','que dice el segundo']:
   with self.subTest(p=p),patch('tandas_documentales.cargar',return_value=MANIFIESTO):
    self.assertTrue(A.preparar([],p,estado()))
   with patch('tandas_documentales.cargar',side_effect=ValueError('Manifiesto inválido')):
    self.assertFalse(A.preparar([],p,estado()))
    self.assertIsNone(R.atender(p,estado()))
 def test_propuesta_pendiente_gana_a_la_ordinal(self):
  for p in ['resume el primero','resume la primera','muestra el segundo','resume la segunda','muestra el tercero','resume la tercera','resume ambos','resume los dos','de que habla la primera','que dice el segundo']:
   e=estado();e['_hilo_conversacion']={'propuesta':{'opciones':['opción uno','opción dos']}}
   with self.subTest(p=p),patch('tandas_documentales.cargar') as cargar:
    self.assertFalse(A.preparar([],p,e));self.assertIsNone(R.atender(p,e));cargar.assert_not_called()

for familia,frases in FAMILIAS.items():
 for i,p in enumerate(frases,1):setattr(Pruebas,f'test_{familia}_{i:02}',lambda self,p=p:self.negativo(p))
if __name__=='__main__':unittest.main()
