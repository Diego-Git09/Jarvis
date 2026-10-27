"""Regresiones halladas al repetir la sesión completa, no solo casos sueltos."""
import unittest
from unittest.mock import Mock,patch
import hilo_conversacion as H
import interfaz_archivos as A
import interfaz_jarvis as I
import jarvis_agente as J

class Pruebas(unittest.TestCase):
    def test_correcciones_breves_con_puntuacion_no_son_el_pedido(self):
        for p in ('no, era otra cosa','no era otra cosa','NO, ERA OTRA COSA','no; era otra cosa','no: era otra cosa','no  era otra cosa','no, eso no','listo','ok','de acuerdo'):
            h=[{'role':'user','content':'Explícame Docker.'},{'role':'assistant','content':'Explicación.'},{'role':'user','content':p},{'role':'assistant','content':'De acuerdo.'},{'role':'user','content':'que te pedi antes?'}]
            with self.subTest(p=p):self.assertIn('Explícame Docker.',H.recordar_peticion(h,'que te pedi antes?'))

    def test_comparacion_con_archivo_ausente_es_comprensible(self):
        for e in ('FileNotFoundError: notas.txt no es un archivo','PermissionError: denegado','FileExistsError: ya existe'):
            with self.subTest(error=e):
                t=A.renderizar_archivos('comparar_archivos',{'ok':False,'error':e})
                self.assertNotIn('Error:',t);self.assertTrue('/' in t or 'nombre' in t)

    def test_un_comando_nuevo_no_hereda_la_marca_de_fallo(self):
        e={'_estado_respuesta':'fallida'}
        ok,t=I.comando('/ayuda',[],e,Mock(),J.SISTEMA)
        self.assertTrue(ok);self.assertNotIn('_estado_respuesta',e)

    def test_sistema_se_basa_en_lectura_y_no_supone_windows(self):
        import guias_contexto_r3 as G
        with patch('platform.freedesktop_os_release',return_value={'PRETTY_NAME':'Ubuntu de prueba'}):
            self.assertIn('Ubuntu de prueba',G.sistema_detectado())
        with patch('platform.freedesktop_os_release',side_effect=OSError):
            self.assertIn('no tiene una lectura',G.sistema_detectado())

    def test_resumen_no_repite_carga_tras_rechazo_de_recursos(self):
        import resumen_mensaje as R,mensajes_largos as M,configuracion_jarvis as C,cliente_ollama as O
        e={};M.preparar('Texto. '*3000,e)
        api=Mock(side_effect=O.ErrorOllama('Espera por recursos',tipo='recursos'))
        t=R.resumir(e,C.DEFAULT,api)
        self.assertEqual(api.call_count,1);self.assertIn('Pendientes:',t);self.assertFalse(e['_ultimo_resumen_mensaje']['completo'])

    def test_resumen_espera_calor_sin_rebajar_el_umbral(self):
        import resumen_mensaje as R,control_recursos as C
        with patch.object(C,'termica',side_effect=[{'cpu_c':92},{'cpu_c':84}]),patch('politica_termica.leer',return_value={'cpu':90,'gpu':80}),patch.object(R.time,'sleep') as dormir:
            self.assertTrue(R.esperar_temperatura(R.time.monotonic()+10))
        dormir.assert_called_once()

    def test_abre_no_separa_texto_entre_comillas_ni_ejemplos(self):
        from ordenes_compuestas import separar
        self.assertEqual(separar('lee "a y luego abre b.txt"'),[])
        self.assertEqual(separar('por ejemplo lista los archivos y luego abre prueba.txt'),[])

    def test_q_de_pregunta_no_es_identificador_y_no_cambia_codigo(self):
        from consulta_textual import incumplimientos
        self.assertTrue(incumplimientos('q es una variable','q es una variable que almacena datos'))
        self.assertFalse(incumplimientos('explica la variable q en este codigo','q es una variable que almacena datos'))

    def test_guia_continua_tema_inequivoco_sin_suponer_otro_sistema(self):
        from fiabilidad_tecnica import guia_directa
        h=[{'role':'user','content':'que es Docker'},{'role':'assistant','content':'Un contenedor.'},{'role':'user','content':'y para que sirve eso'}]
        self.assertIn('En Ubuntu empieza por lecturas',guia_directa('haceme una guia de como usarlo',h))
        h.append({'role':'user','content':'tambien quiero saber de Oracle'})
        self.assertIsNone(guia_directa('haceme una guia de como usarlo',h))

    def test_comparacion_y_modelo_actual_responden_ambas_partes(self):
        import interfaz_local as L,configuracion_jarvis as C
        with patch.object(L.O,'diagnostico',return_value={'ok':True,'version':'prueba','modelos':['jarvis-deepseek:8b']}):
            ok,t=L.comando_local('oye una cosa q diferencia hay entre qwen y deepseek tmb cual usas tu ahora',[],{},lambda _:self.fail('Solo lectura'),dict(C.DEFAULT),lambda:None,Mock())
        self.assertTrue(ok);self.assertIn('1.',t);self.assertIn('2.',t);self.assertIn('regla del enrutador',t);self.assertIn('modelo configurado',t)

    def test_qwen_no_vuelve_a_inferir_para_explicar_un_permiso_denegado(self):
        enviar=Mock(side_effect=[{'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{'ruta':'ejemplo.txt','contenido':'hola'}}}]},AssertionError('No debe inferir otra vez')])
        with patch.object(J,'modelo_del_turno',return_value='qwen3:8b'),patch.object(J,'consulta_contextual',return_value={'ok':False,'error':'El usuario no autorizó esta acción. No se hizo nada.'}):
            t=J._ejecutar_turno([{'role':'user','content':'crea ejemplo.txt con hola'}],enviar,lambda _:False,{},mostrar=lambda _:None)
        self.assertEqual(enviar.call_count,1);self.assertIn('no autorizó',t)

if __name__=='__main__':unittest.main()
