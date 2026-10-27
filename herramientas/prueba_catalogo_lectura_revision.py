"""Catálogos malformados y lectura fragmentada no deben romper la interfaz."""
import io,json,time,unittest
from unittest.mock import patch
import cliente_ollama as O
from lectura_http import lineas_acotadas,leer_acotado,LimiteHTTP

class Fragmentos:
 def __init__(self,partes):self.partes=iter(partes)
 def read(self,n):return next(self.partes,b'')

class Pruebas(unittest.TestCase):
 def test_catalogo_omite_capacidades_no_validas(self):
  for capacidades in (None,'completion',{'completion':True},[7,'completion'],True):
   with self.subTest(capacidades=capacidades),patch.object(O,'solicitar',return_value={'models':[{'name':'dato:8b','capabilities':capacidades}]}):
    self.assertEqual(O.modelos(),[])
 def test_no_muestra_embedding_remoto_o_nombre_invalido(self):
  filas=[{'name':'embedding:8b','capabilities':['embedding']},{'name':'dato:cloud'},{'name':'dato:8b','remote_host':'remoto.invalid'},{'name':''},{'name':'   '},{'name':'nombre\ncontrol'},{'name':'x'*121},{'name':False},None]
  with patch.object(O,'solicitar',return_value={'models':filas}):self.assertEqual(O.modelos(),[])
 def test_chat_legacy_y_capacidades_listadas_sin_duplicados(self):
  with patch.object(O,'solicitar',return_value={'models':[{'name':'dato:8b'},{'name':'dato:8b','capabilities':['completion']},{'name':'visual:8b','capabilities':['completion','vision']}]}):
   self.assertEqual(O.modelos(),['dato:8b','visual:8b'])
 def test_formato_raiz_invalido_es_error_de_catalogo(self):
  for valor in (None,{},'datos',True):
   with self.subTest(valor=valor),patch.object(O,'solicitar',return_value={'models':valor}),self.assertRaises(O.ErrorOllama) as fallo:O.modelos()
   self.assertEqual(fallo.exception.tipo,'catalogo')
 def test_streaming_fragmentado_conserva_utf8_y_ultima_linea(self):
  raw='{"texto":"á漢字"}\n{"done":true}\nultimo'.encode()
  for ancho in (1,2,3,7,64):
   with self.subTest(ancho=ancho):
    partes=[raw[i:i+ancho] for i in range(0,len(raw),ancho)]
    lineas=list(lineas_acotadas(Fragmentos(partes),1000,time.monotonic()+2))
    self.assertEqual(b''.join(lineas),raw);self.assertEqual(len(lineas),3)
 def test_flujo_en_el_limite_no_se_rechaza_y_exceso_si(self):
  self.assertEqual(list(lineas_acotadas(io.BytesIO(b'uno\n'),4,time.monotonic()+1)),[b'uno\n'])
  with self.assertRaises(LimiteHTTP):list(lineas_acotadas(io.BytesIO(b'uno\nx'),4,time.monotonic()+1))
 def test_cuerpo_vacio_y_plazo_vencido(self):
  self.assertEqual(leer_acotado(io.BytesIO(b''),5,time.monotonic()+1),b'')
  with self.assertRaises(TimeoutError):leer_acotado(io.BytesIO(b'dato'),5,time.monotonic()-1)
 def test_invalido_binario_no_se_interpreta_como_texto(self):
  with self.assertRaises(ValueError):leer_acotado(Fragmentos(['dato']),100,time.monotonic()+1)

if __name__=='__main__':unittest.main()
