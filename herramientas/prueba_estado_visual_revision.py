"""Avisos de servicio legibles en Tk real, sin modelos ni datos de usuario."""
import copy,os,tkinter as tk,unittest
from unittest.mock import patch
from interfaz_grafica import Aplicacion

class Instancia:
 def cerrar(self):pass

@unittest.skipUnless(os.environ.get('JARVIS_UI_REAL')=='1','Requiere Tk real')
class Pruebas(unittest.TestCase):
 def setUp(self):
  self.root=tk.Tk();self.root.withdraw();self.root.attributes('-alpha',0)
  with patch.object(Aplicacion,'_inicializar_estado',return_value=None):self.app=Aplicacion(self.root,Instancia())
  self.root.deiconify();self.root.geometry('760x560');self.root.update()
 def tearDown(self):
  self.app._cerrando.set()
  for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
  self.root.destroy()
 def test_estado_largo_tiene_fila_propia_y_no_tapa_la_entrada(self):
  self.app.status.configure(text='Ollama está iniciando y la pregunta sigue conservada. '*4)
  self.root.update()
  self.assertGreater(self.app.status.winfo_width(),self.root.winfo_width()*.75)
  for w in (self.app.composer,self.app.boton_enviar):
   self.assertGreater(w.winfo_height(),15)
   self.assertLessEqual(w.winfo_rooty()-self.root.winfo_rooty()+w.winfo_height(),self.root.winfo_height()+1)
 def test_aviso_de_servicio_se_ve_y_no_contamina_historial_del_modelo(self):
  h=copy.deepcopy(self.app.historial)
  self.app.eventos.put(('servicio_ollama','Aviso sintético: servidor propio listo.'))
  self.app._procesar_eventos();self.root.update()
  self.assertIn('servidor propio listo',self.app.chat.get('1.0','end-1c'))
  self.assertEqual(self.app.historial,h)
 def test_procesamiento_de_eventos_no_accede_a_tk_despues_de_cerrar(self):
  self.app._cerrando.set()
  with patch.object(self.root,'after') as despues:self.app._procesar_eventos()
  despues.assert_not_called()

if __name__=='__main__':unittest.main()
