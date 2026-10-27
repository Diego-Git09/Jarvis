"""52 contratos del controlador. Modelo simulado: NO mide verdad ni calidad humana.

Las secuencias originales están congeladas en corpus_r5.json. Los efectos de
escritura se prueban en rutas temporales; el MCP y Zen reales están prohibidos.
"""
import copy,json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import jarvis_agente as J
import interfaz_jarvis as I
import interfaz_local as IL
import configuracion_jarvis as CFG
import herramientas_lectura as L
import herramientas_escritura as E
from prueba_memoria_explicita import Falso
from prueba_ronda5_fuentes import VENENO
CORPUS=json.loads(Path(__file__).with_name('corpus_r5.json').read_text())['casos']

class Pruebas(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=L.RAIZ);self.addCleanup(self.tmp.cleanup)
  self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
  patch.object(L,'RAIZ',self.base).start();patch.object(L,'REGISTRO',self.base/'log').start()
  patch.object(E,'CAMBIOS',self.base/'cambios').start()
  self.e={};self.h=[];self.permisos=[];self.acciones=[];self.inferencias=[];self.c=Falso()
  real_llamar=self.c.llamar
  def memoria(n,a):
   if n=='consultar_estado_cerebro':return {'ok':True,'consultado':'2026-10-21','fuentes':[],'memorias':0}
   if n=='listar_proyectos':return {'ok':True,'proyectos':[{'proyecto':'Jarvis'},{'proyecto':'sin_clasificar'}]}
   return real_llamar(n,a)
  self.c.llamar=memoria
  self.ajustes=dict(CFG.DEFAULT,seleccion_modelo='automatico')
  patch.dict(J.AJUSTES,self.ajustes,clear=True).start();patch.object(J,'CEREBRO',self.c).start()
  patch.object(J.O,'modelos',return_value=['qwen3:8b','jarvis-deepseek:8b']).start()
  patch.object(J.O,'solicitar',side_effect=lambda ruta,*a,**k:{'models':[]} if ruta=='/api/ps' else (_ for _ in ()).throw(AssertionError('Sin transporte real en el banco simulado'))).start()
  patch.object(J.O,'diagnostico',return_value={'ok':True,'version':'prueba','modelos':['qwen3:8b','jarvis-deepseek:8b']}).start()
  import externo_zen as Z
  patch.object(Z,'transporte',side_effect=AssertionError('Zen prohibido')).start()
  patch.object(CFG,'guardar',side_effect=lambda d:dict(d)).start()
  (self.base/'prueba.txt').write_text('PRUEBA_LITERAL_R5\n')
 def permiso(self,t):self.permisos.append(t);return self.autoriza
 def accion(self,n,a):
  self.acciones.append((n,dict(a)))
  if n=='consultar_estado_cerebro':return {'ok':True,'estado':{'consultado':'2026-10-21','errores':[]},'respuesta':'Estado real de prueba, consulta fechada.'}
  if n=='listar_proyectos':return {'ok':True,'proyectos':[{'proyecto':'Jarvis','total':1}]}
  if n=='listar_memorias':
   self.assertNotIn('filtro',a);return {'ok':True,'memorias':[],'total_disponible':0}
  return J.ejecutar_herramienta(n,a,self.permiso,self.e)
 def enviar(self,h):
  self.inferencias.append(copy.deepcopy(h))
  if self.numero>=39 and self.numero not in (44,45,47):
   self.assertFalse(getattr(J.TIEMPO_MODELO,'tanda',None),'Fuente anterior ajena a esta pregunta')
   import contexto_jarvis as CT
   self.assertNotIn(VENENO,json.dumps(CT.historial_activo(h,self.e)))
  if self.numero in (27,28) and not any(m.get('role')=='tool' for m in h):
   return {'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{'ruta':'notas.txt','contenido':'hola'}}}]}
  return {'role':'assistant','content':'Explicación simulada de la petición actual, sin ejecutar operaciones.'}
 def turno(self,p):
  local=lambda p,h,e:IL.comando_local(p,h,e,self.permiso,self.ajustes,lambda:None,self.c,J.ESTADISTICAS)
  ok,t=I.comando(p,self.h,self.e,self.accion,J.SISTEMA,local=local,confirmar_plan=self.permiso)
  if not ok:
   if not self.h:self.h.append({'role':'system','content':J.SISTEMA})
   self.h.append({'role':'user','content':p})
   t=J.responder_con_respaldo(self.h,self.enviar,self.permiso,self.e,mostrar=lambda _:None)
  return ok,t
 def escenario(self,caso):
  self.numero=n=caso['numero'];self.autoriza=n not in (26,27)
  p=caso['pasos'][0]['pregunta']
  if n in (18,19,20,21,22,23):
   self.h=[{'role':'user','content':'explicame q es docker'},{'role':'assistant','content':'Docker ejecuta aplicaciones en contenedores. Esta explicación no contiene una lista de opciones.'}]
   if n==23:self.h += [{'role':'user','content':'listo'},{'role':'assistant','content':'De acuerdo.'}]
  if n>=36:
   self.e.update(_tanda_documentos='a'*32,_adjuntos_orden=['uno.txt','dos.txt'])
   self.h=[{'role':'user','content':'/adjuntar\n[Adjunto: Tanda: 2 archivos] '+VENENO},{'role':'assistant','content':VENENO},{'role':'user','content':'resumeme los dos'},{'role':'assistant','content':VENENO}]
  if n in (29,30,31):(self.base/'notas.txt').write_text('hola')
  if n==30:self.turno(CORPUS[28]['pasos'][0]['pregunta'])
  if n==35:
   import tandas_documentales as T
   uno=self.base/'uno.txt';dos=self.base/'dos.txt';uno.write_text('LUNA: astronomía');dos.write_text('PLANTA: botánica')
   p='/adjuntar '+json.dumps(str(uno))+' '+json.dumps(str(dos))
  if n==38:
   import mensajes_largos as ML
   ML.preparar(p,self.e)
   self.h.extend([{'role':'user','content':p},{'role':'assistant','content':'Texto dividido en tramos.'}])
   patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':'La tecnología transforma el trabajo y la sociedad.'}}).start()
   p='resumelo'
  if n==36:p='la primera habla de q y la segunda?'
  if n==37:
   self.e['_ultima_cobertura_tanda']={'id':'a'*32,'texto':'2 fuentes indexadas, cobertura parcial.'}
  if n in (5,42):patch.object(J.O,'diagnostico',return_value={'ok':True,'version':'prueba','modelos':['qwen3:8b','jarvis-deepseek:8b']}).start()
  if n==42:p='hola'
  if n in (39,40):p=caso['pasos'][0]['pregunta']
  if n==41:p='explicame q es una api';self.ajustes['modo']='tecnico'
  with patch.object(J.TANDAS,'cargar',return_value={'archivos':[{'nombre':'uno.txt'},{'nombre':'dos.txt'}]}),patch.object(J.TANDAS,'contexto',return_value=VENENO):
   ok,t=self.turno(p)
  self.assertTrue(t,'Respuesta vacía')
  import calidad_respuesta as K
  self.assertFalse(K.filtraciones(t),t)
  if n in (1,3,4,6,7,8,9,10,20,25,26,30,32,35,37,46,47,52):self.assertTrue(ok,'El controlador debe resolver esta petición')
  if n in (7,8,24):self.assertIn('consultar_estado_cerebro',[a[0] for a in self.acciones])
  if n==10:self.assertIn('listar_memorias',[a[0] for a in self.acciones])
  if n==20:self.assertRegex(t.lower(),'opci[oó]n|refieres|cu[aá]l')
  if n==23:self.assertIn('explicame q es docker',t);self.assertNotIn('«listo»',t)
  if n==25:
   self.assertFalse(self.permisos);self.assertIn('PRUEBA_LITERAL_R5',t)
  if n==26:self.assertFalse(self.acciones);self.assertRegex(t.lower(),'qu[eé]|cu[aá]l|objeto')
  if n==27:self.assertFalse((self.base/'notas.txt').exists());self.assertEqual(len(self.permisos),1)
  if n==28:self.assertEqual((self.base/'notas.txt').read_text(),'hola');self.assertEqual(len(self.permisos),1)
  if n==29:self.assertTrue((self.base/'final.txt').exists());self.assertFalse((self.base/'respaldo.txt').exists());self.assertEqual(len(self.permisos),1)
  if n==30:self.assertIn('final.txt',t);self.assertFalse((self.base/'final.txt').exists())
  if n==32:self.assertIn('terminal',t.lower());self.assertRegex(t,'/modelo|/diagnostico')
  if n in (33,34,43,45):self.assertFalse(self.acciones,'Los datos no autorizan acciones')
  if n==36:self.assertIn('uno.txt',t);self.assertIn('dos.txt',t)
  if n==38:self.assertRegex(t.lower(),'tramo|s[ií]ntesis');self.assertFalse(self.permisos)
  if n==44:self.assertNotIn('inventada_R5_nunca_real',json.dumps(self.c.filas));self.assertFalse(self.c.envios,'No guardar contraseñas')
  if n==46:self.assertIn('apagado',t.lower())
  if n==47:self.assertTrue(self.c.envios);self.assertEqual(self.c.consultas[-1][0],'consultar_memoria');self.assertEqual(len(self.permisos),1)
  if n in (48,49,50):
   prompt=J.prompt_para_turno(p,self.e);self.assertIn('verific',prompt.lower())
  if n==52:self.assertIn('/ayuda',t);self.assertGreaterEqual(t.count('/'),3)
for caso in CORPUS:setattr(Pruebas,'test_caso_%02d'%caso['numero'],lambda self,c=caso:self.escenario(c))
if __name__=='__main__':unittest.main()
