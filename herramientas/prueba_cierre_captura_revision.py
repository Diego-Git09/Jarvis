"""Cerrar la interfaz y fallar MCP no deben ejecutar turnos tardíos ni borrar respuestas."""
import queue,threading,time,unittest
from unittest.mock import Mock,patch
from interfaz_grafica import Aplicacion,J

class Pruebas(unittest.TestCase):
 def app(self):
  a=Aplicacion.__new__(Aplicacion);a._cerrando=threading.Event()
  a._cancelar_adjuntos=threading.Event();a._capturas_en_curso=set()
  a._capturas_lock=threading.RLock();a.estado={};a.historial=[{'role':'system','content':J.SISTEMA}]
  a.eventos=queue.Queue();a.confirmaciones=queue.Queue();a.root=Mock();a.estado_ia=Mock()
  a.pendiente_actual=False;a.instancia=Mock()
  return a
 def test_turno_que_empieza_tras_el_cierre_no_captura_ni_ejecuta(self):
  a=self.app();a._cerrando.set()
  with patch.object(J.CONVERSACIONES,'iniciar',return_value='id') as iniciar,patch.object(J,'comando',return_value=(True,'Respuesta')) as comando,patch.object(J.CONVERSACIONES,'finalizar'):
   a._turno('Petición sintética','Petición sintética',[],[])
  iniciar.assert_not_called();comando.assert_not_called()
 def test_mcp_fallido_no_reemplaza_respuesta_completa_por_error(self):
  a=self.app()
  with patch.object(J,'AJUSTES',dict(J.AJUSTES,seleccion_modelo='manual')),patch.object(J.CONVERSACIONES,'iniciar',return_value='id'),patch.object(J,'comando',return_value=(True,'Respuesta sintética completa')),patch.object(J.CONVERSACIONES,'finalizar',return_value=True) as finalizar,patch.object(J.CONVERSACIONES,'guardar_pendientes',side_effect=ConnectionError('MCP sintético caído')):
   a._turno('Petición sintética','Petición sintética',[],[])
  self.assertEqual(finalizar.call_count,1);self.assertEqual(finalizar.call_args.args[1],'Respuesta sintética completa')
  respuestas=[v for tipo,v in list(a.eventos.queue) if tipo=='respuesta']
  self.assertEqual(respuestas,['Respuesta sintética completa'])
 def test_cierre_durante_preparacion_no_despacha_acciones(self):
  a=self.app()
  with patch.object(J.CONVERSACIONES,'iniciar',return_value='id'),patch.object(J,'comando',return_value=(True,'Respuesta')) as comando,patch.object(J.CONVERSACIONES,'finalizar',return_value=True) as finalizar,patch('interfaz_grafica.ADJUNTOS.recordar_referencia',side_effect=lambda *_:a._cerrando.set()):
   a._turno('Petición sintética','Petición sintética',[],[])
  comando.assert_not_called();finalizar.assert_called_once();self.assertEqual(finalizar.call_args.args[2],'interrumpida')
 def test_captura_completada_se_retira_antes_de_sincronizar(self):
  a=self.app();observaciones=[]
  def sincronizar(_):
   observaciones.append((not a._capturas_en_curso,('respuesta','Respuesta sintética completa') in list(a.eventos.queue)))
   return {'pendientes':0}
  with patch.object(J,'AJUSTES',dict(J.AJUSTES,seleccion_modelo='manual')),patch.object(J.CONVERSACIONES,'iniciar',return_value='id'),patch.object(J,'comando',return_value=(True,'Respuesta sintética completa')),patch.object(J.CONVERSACIONES,'finalizar',return_value=True),patch.object(J.CONVERSACIONES,'guardar_pendientes',side_effect=sincronizar),patch.object(J.CONVERSACIONES,'sigue_pendiente',return_value=False):
   a._turno('Petición sintética','Petición sintética',[],[])
  self.assertIn(('respuesta','Respuesta sintética completa'),list(a.eventos.queue))
  self.assertEqual(observaciones,[(True,True)])
 def test_un_cierre_tardio_no_reescribe_una_captura_finalizada(self):
  a=self.app();a._capturas_en_curso.add('id')
  with patch.object(J.CONVERSACIONES,'finalizar',return_value=True) as finalizar:
   a._finalizar_captura('id','Respuesta completa')
   a._cerrando.set();a._finalizar_captura('id','Se cerró','interrumpida')
  finalizar.assert_called_once();self.assertEqual(finalizar.call_args.args[1],'Respuesta completa')
 def test_sincronizar_al_cerrar_no_bloquea_la_ventana_ni_se_duplica(self):
  a=self.app();entrando=threading.Event();terminar=threading.Event()
  def sincronizar(_):
   entrando.set();terminar.wait(3)
   raise ConnectionError('Fallo sintético')
  with patch.object(J.O,'cerrar_servicio') as cerrar_servicio,patch.object(J.CONVERSACIONES,'guardar_pendientes',side_effect=sincronizar) as guardar:
   try:
    inicio=time.monotonic();a.cerrar()
    self.assertLess(time.monotonic()-inicio,.7)
    self.assertTrue(entrando.wait(1));a.root.destroy.assert_called_once()
    a.cerrar();cerrar_servicio.assert_called_once();guardar.assert_called_once()
   finally:
    terminar.set()
    if hasattr(a,'_hilo_cierre_conversaciones'):a._hilo_cierre_conversaciones.join(2)
  self.assertFalse(a._hilo_cierre_conversaciones.is_alive())
 def test_inicializacion_tardia_no_consulta_servicios_despues_de_cerrar(self):
  a=self.app();a._cerrando.set()
  with patch.object(J.O,'asegurar_servicio') as servicio,patch.object(J.CONVERSACIONES,'guardar_pendientes') as guardar,patch.object(J.O,'modelos') as modelos,patch.object(a,'actualizar_estructura') as estructura,patch.object(a,'_consultar_servicios') as consultar:
   a._inicializar_estado()
  for llamada in (servicio,guardar,modelos,estructura,consultar):llamada.assert_not_called()
 def test_cierre_durante_sondeo_inicial_no_inicia_sincronizacion(self):
  a=self.app()
  with patch.object(J.O,'asegurar_servicio',side_effect=lambda **_:a._cerrando.set()),patch.object(J.CONVERSACIONES,'guardar_pendientes') as guardar,patch.object(J.O,'modelos') as modelos,patch.object(a,'actualizar_estructura') as estructura,patch.object(a,'_consultar_servicios') as consultar:
   a._inicializar_estado()
  for llamada in (guardar,modelos,estructura,consultar):llamada.assert_not_called()
 def test_cierre_durante_sincronizacion_inicial_no_consulta_catalogo(self):
  a=self.app()
  def sincronizar(_):a._cerrando.set();return {'pendientes':0}
  with patch.object(J.O,'asegurar_servicio',return_value=None),patch.object(J.CONVERSACIONES,'guardar_pendientes',side_effect=sincronizar),patch.object(J.O,'modelos') as modelos,patch.object(a,'actualizar_estructura') as estructura,patch.object(a,'_consultar_servicios') as consultar:
   a._inicializar_estado()
  for llamada in (modelos,estructura,consultar):llamada.assert_not_called()

if __name__=='__main__':unittest.main()
