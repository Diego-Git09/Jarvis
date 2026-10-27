"""Variantes de peticiones reales; solo dobles MCP y archivos temporales."""
import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
import interfaz_jarvis as I,jarvis_agente as J,memoria_explicita as M
from prueba_memoria_explicita import Falso
ESTADOS=('como esta mi segundo cerebro','estado del 2do cerebro','esta funcionando el cerebro?','COMO ESTA MI SEGUNDO CEREBRO','COnsulta el estado de segundo cerebro y dime si esta funcionando correctamente','como va el segundo cerebro','revisa el estado de mi segundo cerebro','funciona mi segundo cerebro','dime el estado del cerebro','muestrame los errores del segundo cerebro')
BORRADOS=('borra eso','elimina esto','quita eso','borra este','mueve eso','modifica eso','edita eso','BORRA ESO','borra lo anterior','elimina ese')
class Pruebas(unittest.TestCase):
 def directa(self,p):
  llamadas=[]
  def ejecutar(n,a):llamadas.append((n,a));return {'ok':True,'consultado':'2026-10-21','memorias':0,'fuentes':[]}
  ok,t=I.comando(p,[],{},ejecutar,J.SISTEMA,confirmar_plan=lambda _:self.fail('Solo lectura'))
  return ok,t,llamadas
 def test_diez_formas_de_estado_consultan_sin_modelo(self):
  for p in ESTADOS:
   with self.subTest(p=p):
    ok,t,llamadas=self.directa(p);self.assertTrue(ok);self.assertEqual(llamadas,[('consultar_estado_cerebro',{})]);self.assertIn('2026-10-21',t)
 def test_diez_objetos_vagos_no_autorizan_borrar(self):
  for p in BORRADOS:
   with self.subTest(p=p):
    ok,t,llamadas=self.directa(p);self.assertTrue(ok);self.assertFalse(llamadas);self.assertIn('?',t)
 def test_lista_plural_no_inventa_argumento_filtro(self):
  for prefijo in ('muestrame','lista','listar','muestra','dime'):
   for objeto in ('los ultimos recuerdos','las memorias'):
    with self.subTest(prefijo=prefijo,objeto=objeto):
     ok,_,llamadas=self.directa(prefijo+' '+objeto+' de jarvis');self.assertTrue(ok);self.assertEqual(llamadas[0][0],'listar_memorias');self.assertNotIn('filtro',llamadas[0][1])
 def test_error_de_esquema_no_expone_detalle_interno(self):
  r=J.ejecutar_herramienta('listar_memorias',{'filtro':'Jarvis'},lambda _:False,{})
  self.assertFalse(r['ok']);self.assertNotIn('Argumentos no permitidos',r['error']);self.assertIn('/ayuda',r['error'])
 def test_guardado_corto_muestra_texto_y_relee_con_un_permiso(self):
  import interfaz_local as IL,configuracion_jarvis as C
  with tempfile.TemporaryDirectory() as t,patch.object(M,'CARPETA',Path(t)/'recuerdos'):
   c=Falso();viejo=c.llamar
   c.llamar=lambda n,a: {'ok':True,'proyectos':[{'proyecto':'sin_clasificar'}]} if n=='listar_proyectos' else viejo(n,a)
   vistas=[]
   ok,r=IL.comando_local('guarda en el segundo cerebro q hoy probe jarvis',[],{},lambda s:vistas.append(s) or True,dict(C.DEFAULT),lambda:None,c)
   self.assertTrue(ok);self.assertIn('guardado y comprobado',r);self.assertEqual(len(vistas),1);self.assertIn('hoy probe jarvis',vistas[0]);self.assertEqual(c.consultas[-1][0],'consultar_memoria')
 def test_no_guarda_secreto_corto_ni_narra_un_plan(self):
  c=Falso();ok,t=M.comando('guarda en el segundo cerebro q mi contraseña es inventada_R5',c,lambda _:self.fail('No guardar una contraseña'),{})
  self.assertTrue(ok);self.assertFalse(c.envios);self.assertNotIn('inventada_R5',t)
 def test_shell_solo_ofrece_equivalente(self):
  for p in ('ollama ps','ollama list','nvidia-smi','NVIDIA-SMI','ollama    ps'):
   ok,t,llamadas=self.directa(p);self.assertTrue(ok);self.assertFalse(llamadas);self.assertIn('terminal',t);self.assertIn('/diagnostico',t)
 def test_desconocido_ofrece_tres_accesos(self):
  from accesos_jarvis import sugerir
  t=sugerir('/jarvis_loco');self.assertIn('/ayuda',t);self.assertGreaterEqual(t.count('/'),3)
if __name__=='__main__':unittest.main()
