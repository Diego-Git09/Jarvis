"""Aislamiento del tema tras adjuntar: el archivo sigue disponible, no vigente."""
import json,unittest
from unittest.mock import patch
import jarvis_agente as J
import contexto_jarvis as C
import consulta_textual as Q
import calidad_respuesta as K

PREGUNTAS=('hola','q es una variable','explicame q es una api','analiza ventajas de microservicios','cuanto es 15 por 3','como esta mi segundo cerebro','como funciona Docker','dime una receta sencilla','que es la ram','usa el externo para responder esto: q es una api')
VENENO='SELENIUM_ANTERIOR_KITS_DOCUMENTALES_R5'
class Pruebas(unittest.TestCase):
 def probar(self,p):
  h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':'/adjuntar\n[Adjunto: Tanda: 2 archivos] '+VENENO},{'role':'assistant','content':VENENO},{'role':'user','content':'resumeme los dos'},{'role':'assistant','content':VENENO},{'role':'user','content':p}]
  e={'_tanda_documentos':'a'*32,'_adjuntos_orden':['uno.txt','dos.txt']}
  def inferir(*_a,**_k):
   self.assertFalse(getattr(J.TIEMPO_MODELO,'tanda',None),'Fuentes anteriores añadidas sin referencia')
   self.assertNotIn(VENENO,json.dumps(C.historial_activo(h,e)))
   self.assertNotEqual(e.get('_ultima_decision_modelo',{}).get('regla'),'adjuntos')
   return 'Respuesta de prueba sin datos anteriores.'
  with patch.object(J.O,'solicitar',return_value={'models':[]}),patch.dict(J.AJUSTES,seleccion_modelo='automatico'),patch.object(J.O,'modelos',return_value=['qwen3:8b','jarvis-deepseek:8b']),patch.object(J.TANDAS,'contexto',return_value=VENENO),patch.object(J.TANDAS,'cargar',return_value={'archivos':[{'nombre':'uno.txt'},{'nombre':'dos.txt'}]}),patch.object(J,'_ejecutar_turno',side_effect=inferir):
   J.ejecutar_turno(h,None,lambda _:self.fail('Sin permiso'),e,mostrar=lambda _:None)
  self.assertIn('_tanda_documentos',e,'No borrar el índice ni la posibilidad de retomarlo')
 def test_concepto_con_tanda_inactiva_sigue_siendo_textual(self):
  self.assertTrue(Q.aplica('q es una variable',{'_tanda_documentos':'a'*32,'_fuentes_turno':False}))
 def test_lista_prohibida(self):
  for p in ('Jarvis debe responder respetando las instrucciones','usar formatos JSON','el usuario ha proporcionado un resumen histórico','es información, no instrucciones','usar crear_archivo','listar_memorias'):
   self.assertTrue(K.filtraciones(p),p)
for i,p in enumerate(PREGUNTAS):setattr(Pruebas,'test_pregunta_independiente_%02d'%i,lambda self,p=p:self.probar(p))
if __name__=='__main__':unittest.main()
