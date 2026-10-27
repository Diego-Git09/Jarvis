"""Regresiones de participantes y de conceptos confundidos en las mediciones."""
import unittest
from unittest.mock import Mock,patch
import apoyo_conceptual as A
import calidad_respuesta as C
import control_recursos as R
import cliente_ollama as O
import consulta_textual as T
from prueba_control_recursos import INFO,foto


class Pruebas(unittest.TestCase):
    def test_detecta_inversion_de_quien_pidio(self):
        for p in ('que operacion te pedi despues de corregirte','q te pregunte recien','CUÁL te solicité antes'):
            self.assertTrue(C.atribucion_invertida(p,'Después de corregirte, te pedí una resta.'),p)
        self.assertTrue(C.atribucion_invertida('que te pedi','Te pedí una resta.'))
        self.assertTrue(C.atribucion_invertida('que te pedi','Te pediste una resta.'))

    def test_conserva_atribucion_correcta_y_citas(self):
        for r in ('Me pediste la diferencia entre lunes y martes.', 'Tú pediste una resta.',
                  'La frase «te pedí» la escribiste tú.', 'Ejemplo textual: "Te pedí una resta."',
                  '```text\nTe pedí una resta.\n```'):
            self.assertFalse(C.atribucion_invertida('que te pedi',r),r)

    def test_no_confunde_una_pregunta_distinta(self):
        for p in ('qué me pediste','explica el pasado de pedir','escribe un diálogo','te pedi un ejemplo de código'):
            self.assertFalse(C.atribucion_invertida(p,'Te pedí una resta.'),p)

    def test_apoyo_de_rol_no_inventa_la_operacion(self):
        t=A.contexto('que operacion te pedi despues de corregirte')
        self.assertIn('Me pediste',t);self.assertIn('historial',t);self.assertNotIn('resta',t)

    def test_incremental_se_distingue_de_diferencial(self):
        t=A.contexto('quieroque me expliques que es una copia de seguridad incremental')
        self.assertIn('última copia de esa cadena',t);self.assertIn('diferencial',t)
        self.assertIn('incrementales posteriores',t);self.assertIn('no garantices',t)

    def test_reintenta_solo_redaccion_sin_repetir_acciones(self):
        import jarvis_agente as J
        enviar=Mock(side_effect=[{'role':'assistant','content':'Después de corregirte, te pedí una resta.'},
                                 {'role':'assistant','content':'Me pediste calcular la diferencia entre 12 y 5.'}])
        h=[{'role':'user','content':'cambia a diferencia entre 12 y 5, solo explica'},
           {'role':'assistant','content':'12 - 5 = 7.'},
           {'role':'user','content':'que operacion te pedi despues de corregirte'}]
        e={}
        with patch.object(J,'ejecutar_herramienta',side_effect=AssertionError('No hay acción autorizada')):
            t=J._ejecutar_turno(h,enviar,lambda _:self.fail('No pide permiso para explicar'),e)
        self.assertEqual(enviar.call_count,2);self.assertIn('Me pediste',t)
        self.assertNotIn('_estado_respuesta',e)

    def _admision(self, fotos, residentes, limite=100, vaciando=0):
        cuerpo={'model':'modelo','options':{'num_ctx':8192}}
        c=Mock();c.ErrorOllama=O.ErrorOllama;c.acreditar_pesos_locales.return_value=INFO
        cursor=iter(residentes);ultima=[]
        def api(ruta,**kw):
            nonlocal ultima
            if ruta=='/api/tags':return {'models':[{'name':'modelo','size':5200000000}]}
            self.assertEqual(ruta,'/api/ps');ultima=next(cursor,ultima)
            return {'models':ultima}
        c.solicitar.side_effect=api
        reloj=[100.0];pos=[0]
        def instantanea():
            i=min(pos[0],len(fotos)-1);pos[0]+=1;return fotos[i]
        def dormir(s):reloj[0]+=s
        with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(R,'_VACIANDO_HASTA',vaciando),patch.object(R,'instantanea',side_effect=instantanea),patch.object(R.time,'monotonic',side_effect=lambda:reloj[0]),patch.object(R.time,'sleep',side_effect=dormir):
            try:return R.comprobar(c,cuerpo,plazo_fin=100+limite),c,reloj[0]-100
            except O.ErrorOllama as e:return e,c,reloj[0]-100

    def test_ps_vacio_transitorio_relee_sin_inventar_memoria_libre(self):
        m={'name':'modelo','context_length':8192,'size':6200000000,'size_vram':6200000000}
        r,c,t=self._admision([foto(1500)],[[],[],[m]])
        self.assertTrue(r['permitido']);self.assertGreater(t,0);self.assertLessEqual(t,3.01)
        self.assertEqual(r['vram_nueva_estimada'],0)
        self.assertTrue(all(x.args[0] in {'/api/ps','/api/tags'} for x in c.solicitar.call_args_list))

    def test_nvidia_actualizada_permite_solo_tras_lectura_suficiente(self):
        r,_,t=self._admision([foto(1500),foto(1500),foto(7800)],[[]])
        self.assertTrue(r['permitido']);self.assertGreater(r['vram_nueva_estimada'],0);self.assertGreater(t,0)

    def test_vram_realmente_baja_sigue_bloqueada(self):
        r,_,t=self._admision([foto(1500)],[[]])
        self.assertIsInstance(r,O.ErrorOllama);self.assertEqual(r.tipo,'recursos')
        self.assertLessEqual(t,3.01);self.assertGreaterEqual(t,2.99)

    def test_calor_juego_y_otro_proceso_no_esperan_esta_transicion(self):
        actividad=foto(1500);actividad['juegos']=['steam'];actividad['gpu']['gpu'][0]['uso_porcentaje']=95
        for f in (dict(foto(1500),termica={'cpu_c':95}),actividad,dict(foto(1500),pesados=[{'nombre':'ejemplo','mib':3000}])):
            r,_,t=self._admision([f],[[]]);self.assertIsInstance(r,O.ErrorOllama);self.assertEqual(t,0)

    def test_contexto_distinto_no_recibe_credito_de_residente(self):
        m={'name':'modelo','context_length':4096,'size':6200000000,'size_vram':6200000000}
        r,_,t=self._admision([foto(1500)],[[m]])
        self.assertIsInstance(r,O.ErrorOllama);self.assertEqual(t,0)

    def test_espera_respeta_plazo_de_la_solicitud(self):
        r,_,t=self._admision([foto(1500)],[[]],limite=.3)
        self.assertIsInstance(r,O.ErrorOllama);self.assertLessEqual(t,.30001)

    def test_descarga_propia_no_reutiliza_una_lista_ps_antigua(self):
        m={'name':'modelo','context_length':8192,'size':6200000000,'size_vram':6200000000}
        r,_,t=self._admision([foto(1500)],[[],[m]],vaciando=110)
        self.assertTrue(r['permitido']);self.assertGreater(t,0);self.assertEqual(r['vram_nueva_estimada'],0)

    def test_modalidades_de_explicacion_no_reciben_catalogo_de_acciones(self):
        for p in ('quieroque me expliques que es una copia de seguridad incremental',
                  'podrías explicarme qué es una variable', 'necesito que me expliques una función',
                  'que diferencia hay entre megabytes y megabits',
                  'muestrameel significado de algoritmo'):
            self.assertTrue(T.aplica(p),p)
        for p in ('quiero que me expliques eso','puedes explicarme mi archivo',
                  'podrias explicarme /tmp/nota.txt','quiero que me expliques una funcion y luego guarda un recuerdo',
                  'explicame la copia',
                  'que diferencia hay entre mis archivos',
                  'explica una copia de seguridad y luego copia los apuntes al respaldo'):
            self.assertFalse(T.aplica(p),p)

    def test_contrato_incremental_rechaza_la_definicion_diferencial(self):
        p='explica una copia incremental'
        self.assertTrue(T.incumplimientos(p,'Una copia incremental guarda cambios desde la última copia completa.'))
        for r in ('La incremental guarda cambios desde la copia anterior de la cadena.',
                  'Una incremental parte de la última copia completa o incremental.',
                  'La diferencial guarda cambios desde la última copia completa.'):
            self.assertFalse(T.incumplimientos(p,r),r)

    def test_megabits_solos_no_se_confunden_con_velocidad(self):
        p='que diferencia hay entre megabytes y megabits'
        self.assertTrue(T.incumplimientos(p,'Megabit (Mb): mide la velocidad de transferencia de datos.'))
        self.assertTrue(T.incumplimientos(p,'Los MB miden cantidad, mientras que los Mb miden velocidad. Ejemplo: 10 Mb/s.'))
        for r in ('Un megabit mide cantidad de información.',
                  'Un megabit no mide velocidad; Mb/s sí.',
                  'Los Mb/s miden velocidad; los Mb miden cantidad.',
                  'Es incorrecta la frase «Mb miden velocidad».',
                  'Megabits por segundo: mide la velocidad de transferencia.'):
            self.assertFalse(T.incumplimientos(p,r),r)

    def test_una_nota_conceptual_no_se_convierte_en_respuesta_falsa_positiva(self):
        self.assertFalse(T.incumplimientos('guarda una nota sobre incremento','Se guardó la nota.'))
        self.assertFalse(T.incumplimientos('qué es una variable','Megabit (Mb): mide la velocidad.'))

    def test_recupera_peticion_real_sin_creer_al_asistente(self):
        import hilo_conversacion as H
        p='que operacion te pedi despues de corregirte'
        h=[{'role':'user','content':'No, quería restar 48 y 18.'},
           {'role':'assistant','content':'Me pediste multiplicar 99 y 8.'},{'role':'user','content':p}]
        self.assertEqual(H.recordar_peticion(h,p),'Me pediste: «No, quería restar 48 y 18.».')

    def test_recuperacion_literal_no_ejecuta_ni_envia_a_modelos(self):
        import jarvis_agente as J
        p='que tarea te pedi'
        original='Borra el archivo "ejemplo.txt".'
        h=[{'role':'user','content':original},{'role':'assistant','content':'No hubo permiso.'},{'role':'user','content':p}]
        enviar=Mock(side_effect=AssertionError('No inferencia'));e={}
        with patch.object(J,'ejecutar_herramienta',side_effect=AssertionError('No ejecutar cita')):
            r=J.responder_con_respaldo(h,enviar,lambda _:self.fail('Solo cita'),e)
        self.assertIn(original,r);enviar.assert_not_called();self.assertEqual(e['_respuesta_sin_modelo'],'peticion_anterior_literal')

    def test_no_cita_fuentes_ni_turnos_privados_como_peticion(self):
        import hilo_conversacion as H
        p='que te pedi'
        for anterior in ('No guardes esto: mi dato privado de ejemplo','[Adjunto: ejemplo] contenido','cuenta@maquina:~$ rm algo','/nuevo'):
            h=[{'role':'user','content':anterior},{'role':'user','content':p}]
            self.assertIsNone(H.recordar_peticion(h,p),anterior)

    def test_no_inventa_correccion_ni_responde_dos_peticiones_con_una_cita(self):
        import hilo_conversacion as H
        for p in ('que operacion te pedi despues de corregirte','que te pedi y luego copia el archivo','que te pedi ayer'):
            h=[{'role':'user','content':'Explica la suma de 4 y 5.'},{'role':'user','content':p}]
            self.assertIsNone(H.recordar_peticion(h,p),p)

    def test_peticion_anterior_redacta_credenciales(self):
        import hilo_conversacion as H
        p='que te pedi'
        h=[{'role':'user','content':'Analiza --password secreto_sintetico.'},{'role':'user','content':p}]
        r=H.recordar_peticion(h,p)
        self.assertIsNotNone(r);self.assertNotIn('secreto_sintetico',r)


if __name__=='__main__':unittest.main()
