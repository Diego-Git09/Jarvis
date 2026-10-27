"""Contrato común del chat: reintentos, contexto y límites sin efectos externos."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jarvis_agente as J
import hilo_conversacion as H
import contexto_jarvis as C
import interfaz_jarvis as I
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        patch.object(H,'CARPETA',self.base/'hilos').start()
        patch.object(J.IA.P,'opciones',return_value={'configurado':False,'automatico':False,'timeout_local':35,'preferido':''}).start()
        self.addCleanup(patch.stopall)

    def test_reintenta_recupera_pedido_y_tanda_sin_cambiar_mensaje_visible(self):
        pedido='Explica el anexo tres del caso adjunto';e={'_tanda_documentos':'a'*32};h=[{'role':'user','content':pedido}]
        with patch.object(J,'ejecutar_turno',side_effect=ConnectionError('timeout sintético')):
            self.assertIn('reintenta',J.responder_con_respaldo(h,None,lambda _:False,e))
        self.assertEqual(e['_hilo_conversacion']['fallido']['pedido'],pedido)
        self.assertFalse(I.comando('reintenta',h,e,lambda *_:self.fail('No herramientas'),'reglas')[0])
        h.append({'role':'user','content':'reintenta'})
        def responder(hist,*args):
            self.assertEqual(hist[-1]['content'],pedido);self.assertEqual(e['_tanda_documentos'],'a'*32)
            return 'Texto explicado con el anexo tres.'
        with patch.object(J,'ejecutar_turno',side_effect=responder):
            texto=J.responder_con_respaldo(h,None,lambda _:False,e)
        self.assertEqual(h[-2],{'role':'user','content':'reintenta'});self.assertEqual(h[-1]['content'],texto)
        self.assertIsNone(e['_hilo_conversacion']['fallido'])

    def test_tras_accion_posible_no_repite_por_un_reintento(self):
        e={};h=[{'role':'user','content':'edita a.py'}]
        def fallo(hist,*args):
            H.marcar_accion(e,'aplicar_edicion')
            hist.append({'role':'assistant','content':'','tool_calls':[{'function':{'name':'aplicar_edicion','arguments':{'id_propuesta':'x'}}}]})
            raise ConnectionError('Conexión perdida después de la acción')
        with patch.object(J,'ejecutar_turno',side_effect=fallo):J.responder_con_respaldo(h,None,lambda _:False,e)
        manejado,texto=I.comando('reintenta',h,e,lambda *_:self.fail('No repetir acción'),'reglas')
        self.assertTrue(manejado);self.assertIn('/cambios',texto)

    def test_sigue_con_propuesta_no_abre_paginacion_de_memorias(self):
        e={};h=[{'role':'user','content':'Ayúdame con el caso Kotlin Android Studio'},
                   {'role':'assistant','content':'Propongo:\n1. Explicar proyecto.\n2. Pantalla.\n¿Empezamos?'}]
        manejado,_=I.comando('sigue',h,e,lambda *_:self.fail('No es un recuerdo'),'reglas')
        self.assertFalse(manejado);self.assertTrue(e['_resolucion_hilo']['aceptada'])

    def test_continuar_lee_ultimo_puntero_antes_de_crear_otro_hilo(self):
        e={};H.iniciar_turno(e,'Decidimos nombre "TIENDA_ALFA".');H.terminar_turno(e,'Decidimos nombre "TIENDA_ALFA".','Queda como dato de la conversación.')
        ident=e['_id_hilo'];nuevo={'_memorias':{1:'No restaurar'}};h=[{'role':'system','content':'reglas'}]
        local=lambda p,h,s:comando_local(p,h,s,lambda _:False,J.AJUSTES,lambda:None,None)
        ok,texto=I.comando('/continuar',h,nuevo,lambda *_:self.fail('Sin herramientas'),'reglas',local=local)
        self.assertTrue(ok);self.assertIn('recuperado',texto);self.assertEqual(nuevo['_id_hilo'],ident)
        self.assertNotIn('_memorias',nuevo);self.assertEqual(len(h),1)

    def test_nuevo_limpia_referencias_y_permiso(self):
        e={'_tanda_documentos':'a'*32,'id_propuesta':'anterior'};h=[{'role':'system','content':'reglas'},{'role':'user','content':'viejo'}]
        self.assertTrue(I.comando('/nuevo',h,e,lambda *_:None,'reglas')[0]);self.assertEqual(e,{})

    def test_presupuesto_insuficiente_no_inventa_espacio_minimo(self):
        h=[{'role':'system','content':'x'*40000},{'role':'user','content':'hola'}]
        with patch.object(J.O,'solicitar') as enviar,self.assertRaises(ConnectionError):J.enviar_a_ollama(h)
        enviar.assert_not_called();self.assertEqual(h[1]['content'],'hola')

    def test_actual_gigante_no_se_trunca_para_hacerlo_caber(self):
        h=[{'role':'system','content':'reglas'},{'role':'user','content':'CASO_ACTUAL '+('dato '*8000)}];antes=copy.deepcopy(h)
        with patch.object(J.O,'solicitar') as enviar,self.assertRaises(ConnectionError):J.enviar_a_ollama(h)
        self.assertEqual(h,antes);enviar.assert_not_called()

    def test_contexto_rechazado_reduce_adjuntos_y_conserva_pedido(self):
        h=[{'role':'system','content':'reglas'},{'role':'user','content':'Explica el caso adjunto'}];cuerpos=[]
        def enviar(ruta,cuerpo,**kwargs):
            cuerpos.append(cuerpo)
            if len(cuerpos)==1:raise J.O.ErrorOllama('context length',tipo='contexto')
            return {'message':{'content':json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'Resumen generado acotado.'})},'prompt_eval_count':321}
        with patch.object(J.TIEMPO_MODELO,'tanda','FUENTE_PARCIAL '*100,create=True),patch.object(J.O,'solicitar',side_effect=enviar):
            r=J.enviar_a_ollama(h)
        self.assertEqual(len(cuerpos),2);self.assertIn('Se redujeron',cuerpos[1]['messages'][-1]['content'])
        self.assertIn('Explica el caso adjunto',cuerpos[1]['messages'][-1]['content']);self.assertEqual(h[-1]['content'],'Explica el caso adjunto')
        self.assertTrue(J.ESTADISTICAS['adjuntos_reducidos']);self.assertEqual(J.ESTADISTICAS['tokens_entrada'],321)

    def test_cambio_de_tema_saca_fuentes_antiguas_de_la_peticion(self):
        e={};h=[{'role':'system','content':'reglas'}]
        H.iniciar_turno(e,'Caso TIENDA_PRIVADA',h);h.extend([{'role':'user','content':'Caso TIENDA_PRIVADA'},{'role':'assistant','content':'DOCUMENTO_ANTIGUO_EXCLUSIVO'}]);H.terminar_turno(e,'Caso TIENDA_PRIVADA','DOCUMENTO_ANTIGUO_EXCLUSIVO')
        p='Otro tema: cocina arroz; no uses el documento';H.iniciar_turno(e,p,h);h.append({'role':'user','content':p})
        vista=C.historial_activo(h,e)
        self.assertNotIn('DOCUMENTO_ANTIGUO_EXCLUSIVO',json.dumps(vista));self.assertIn(p,json.dumps(vista))

    def test_decisiones_intermedias_no_borran_el_arranque_android(self):
        e={};h=[{'role':'user','content':'Ayúdame con el caso de la tienda Kotlin Android Studio'},
             {'role':'assistant','content':'Propongo:\n1. Iniciar proyecto.\n2. Funciones.\n3. Carpetas.\n4. Pantalla.\n¿Empezamos?'}]
        H.iniciar_turno(e,'Decidimos nombre literal "LAPIZ_32", paquete "cl.ejemplo.lapiz".',h)
        h.extend([{'role':'user','content':'Decidimos nombre literal "LAPIZ_32", paquete "cl.ejemplo.lapiz".'},{'role':'assistant','content':'Conservé los datos.'}])
        H.terminar_turno(e,h[-2]['content'],h[-1]['content'])
        self.assertFalse(I.comando('SI te confirmo empecemos',h,e,lambda *_:None,'reglas')[0])
        h.append({'role':'user','content':'SI te confirmo empecemos'})
        with patch.object(J,'_ejecutar_turno',side_effect=AssertionError('El primer paso concreto ya está resuelto')),patch.object(J.CODIGO,'contexto',return_value=''):
            texto=J.responder_con_respaldo(h,None,lambda _:False,e)
        self.assertIn('New Project',texto);self.assertNotIn('¿Qué opción',texto)
        self.assertFalse(I.comando('empecemos a hacer el caso',h,e,lambda *_:None,'reglas')[0])
        h.append({'role':'user','content':'empecemos a hacer el caso'})
        with patch.object(J,'_ejecutar_turno',side_effect=AssertionError('Los datos ya están disponibles')),patch.object(J.CODIGO,'contexto',return_value=''):
            texto=J.responder_con_respaldo(h,None,lambda _:False,e)
        self.assertIn('LAPIZ_32',texto);self.assertIn('cl.ejemplo.lapiz',texto);self.assertIn('¿Qué carpeta',texto)

if __name__=='__main__':unittest.main()
