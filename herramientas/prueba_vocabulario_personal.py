"""Ejemplos de habla del usuario, pruebas de fechas y límites de interpretación."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import recordatorios_jarvis as R
import interfaz_recordatorios as I
import lenguaje_recordatorios as N
from lenguaje_jarvis import limpiar,limpiar_prefijos,interpretar
from interfaz_archivos import acceso_natural
import internet_jarvis as W
import jarvis_agente as J


PREFIJOS=['','Jarvis, ','Jarbvis ','Hola Jarvis, ','puedes ','podrías ','me puedes ','porfa ','me gustaría que me ','quiero que me ','necesito que me ','puedes ayudarme a ']
VERBOS=['crear','hacer','hacerme','hazme','crea','créame','arma','genera']
AVISOS=['y que me empiece a aparecer en desktop dos días antes de la fecha de prueba',
        'y que aparezca 2 días antes','y avísame dos días antes','con dos días de anticipación',
        'avísame 2 días antes de la prueba','que se vea dos días antes']


def corpus():
    casos=[]
    for prefijo in PREFIJOS:
        for verbo in VERBOS:
            if prefijo.endswith('que me '):verbo={'crear':'crees','hacer':'hagas','hacerme':'hagas','hazme':'hagas','crea':'crees','créame':'crees','arma':'armes','genera':'generes'}[verbo]
            p=prefijo+verbo+' un recordatorio de Prueba Ingeniería para el día 20 de octubre a las 09:30 '+AVISOS[0]
            casos.append({'pedido':p,'texto':'Prueba Ingeniería','evento':'2026-10-20T09:30:00-03:00','aviso':'2026-10-18T09:30:00-03:00'})
    for aviso in AVISOS:
        for fecha in ['el 20 de octubre a las nueve y media','para el día veinte de octubre a las 9:30','el 20/10/2026 09:30']:
            casos.append({'pedido':'Hazme un recordatorio de Prueba Ingeniería '+fecha+' '+aviso,'texto':'Prueba Ingeniería','evento':'2026-10-20T09:30:00-03:00','aviso':'2026-10-18T09:30:00-03:00'})
    return list({c['pedido']:c for c in casos}.values())


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=patch.object(R,'ARCHIVO',Path(self.tmp.name)/'recordatorios.json');p.start();self.addCleanup(p.stop)
        p=patch.object(R,'ahora',return_value=datetime(2026,10,13,12,tzinfo=R.ZONA));p.start();self.addCleanup(p.stop)

    def test_corpus_de_prefijos_y_formas_de_pedir_aviso_anticipado(self):
        for c in corpus():
            with self.subTest(pedido=c['pedido']):
                i=N.interpretar(c['pedido']);self.assertIsNotNone(i);self.assertEqual(i['nombre'],'crear_recordatorio')
                a=i['argumentos'];self.assertEqual(a['texto'],c['texto']);plan=R.plan_fecha(**{k:v for k,v in a.items() if k!='texto'})
                self.assertEqual(plan['evento'],c['evento']);self.assertEqual(plan['fecha'],c['aviso'])

    def test_faltas_de_tipeo_no_cambian_el_titulo(self):
        for p in ['Jarbvis recuardame Pruieba Ñuñoa el 20 de octubre y que aparezca dos días antes',
                  'Jarbvis hazme un recoratorio de Pruieba Ñuñoa el 20 de octubre con dos días de anticipación']:
            i=N.interpretar(p);self.assertEqual(i['argumentos']['texto'],'Pruieba Ñuñoa');self.assertEqual(i['argumentos']['anticipacion_dias'],2)

    def test_fechas_en_palabras_horas_y_plazos(self):
        for texto,hora in [('el veinte de octubre a las nueve y media','09:30'),('el veintiuno de octubre a las ocho y cuarto','08:15'),
                            ('el treinta y uno de octubre a las doce menos cuarto','11:45'),('mañana a mediodía','12:00'),('mañana a las 09:30','09:30')]:
            self.assertEqual(R.interpretar_fecha(texto)[11:16],hora)
        self.assertEqual(R.interpretar_fecha('en dos horas'),'2026-10-13T14:00:00-03:00')
        self.assertEqual(R.interpretar_fecha('en una semana'),'2026-10-20T12:00:00-03:00')

    def test_anticipaciones_en_horas_minutos_y_semanas(self):
        for aviso,campo,cantidad,inicio in [('dos horas','anticipacion_minutos',120,'07:30'),('treinta minutos','anticipacion_minutos',30,'09:00'),('una semana','anticipacion_dias',7,'09:30')]:
            i=N.interpretar('Crea un recordatorio de Prueba el 20 de octubre a las nueve y media y avísame '+aviso+' antes')
            self.assertEqual(i['argumentos'][campo],cantidad)
            plan=R.plan_fecha(**{k:v for k,v in i['argumentos'].items() if k!='texto'});self.assertEqual(plan['fecha'][11:16],inicio)

    def test_dos_dias_calendario_respetan_el_cambio_de_hora_chileno(self):
        plan=R.plan_fecha(evento='07/09/2026 09:00',anticipacion_dias=2)
        self.assertEqual(plan['fecha'],'2026-09-05T09:00:00-04:00')
        plan=R.plan_fecha(evento='06/09/2026 03:00',anticipacion_minutos=180)
        self.assertEqual(plan['fecha'],'2026-09-05T23:00:00-04:00')

    def test_una_fecha_ambigua_pide_dato_y_no_crea_nota_permanente(self):
        estado={};hecho,t=I.comando('Hazme un recordatorio de Prueba para el día tanto y avísame dos días antes',estado,lambda _:self.fail('No hay fecha'))
        self.assertTrue(hecho);self.assertIn('Qué día',t);self.assertFalse(R.listar())
        I.comando('20 de octubre a las 9',estado,lambda _:True)
        r=R.listar()[0];self.assertEqual(r['texto'],'Prueba');self.assertEqual(r['evento'][:10],'2026-10-20');self.assertEqual(r['fecha'][:10],'2026-10-18')

    def test_cancelar_aclaracion_no_crea_el_recordatorio(self):
        estado={};I.comando('Hazme un recordatorio de examen algún día',estado,lambda _:False)
        I.comando('mejor no',estado,lambda _:self.fail('No pregunta permiso'))
        self.assertFalse(R.listar());self.assertNotIn('_borrador_recordatorio',estado)

    def test_mover_evento_recalcula_aviso_y_conserva_identidad(self):
        r=R.crear('Prueba',evento='20/10/2026 09:30',anticipacion_dias=2)
        r2=R.modificar(r['id'],evento='25/10/2026 09:30',esperado=R.revision(r))
        self.assertEqual(r2['id'],r['id']);self.assertEqual(r2['evento'][:10],'2026-10-25');self.assertEqual(r2['fecha'][:10],'2026-10-23')

    def test_ponlo_siempre_y_avisame_tres_dias_antes_sin_listar_de_nuevo(self):
        estado={};I.comando('Hazme un recordatorio de Prueba el 20 de octubre con dos días de anticipación',estado,lambda _:True)
        I.comando('ponlo siempre',estado,lambda _:True)
        self.assertIsNone(R.listar()[0]['fecha']);self.assertEqual(R.listar()[0]['evento'][:10],'2026-10-20')
        I.comando('avísame tres días antes',estado,lambda _:True)
        self.assertEqual(R.listar()[0]['fecha'][:10],'2026-10-17')

    def test_cambiar_texto_con_para_que_diga_conserva_programacion(self):
        estado={};I.comando('Hazme un recordatorio de Prueba el 20 de octubre con dos días de anticipación',estado,lambda _:True)
        I.comando('/recordatorios',estado,lambda _:True)
        antes=R.listar()[0]
        I.comando('Modifica el recordatorio uno para que diga Prueba de matemáticas',estado,lambda _:True)
        despues=R.listar()[0]
        self.assertEqual(despues['texto'],'Prueba de matemáticas')
        for campo in ['id','evento','fecha','anticipacion_dias']:self.assertEqual(despues[campo],antes[campo])

    def test_referente_multiple_o_otra_conversacion_no_modifica_una_nota(self):
        estado={};R.crear('Uno');R.crear('Dos');I.comando('/recordatorios',estado,lambda _:True)
        _,t=I.comando('bórralo',estado,lambda _:self.fail('Sin referente'))
        self.assertIn('Qué recordatorio',t);self.assertEqual(len(R.listar()),2)
        I.comando('Hazme un recordatorio de Tres',estado,lambda _:True)
        h=[{'role':'assistant','content':'El archivo notas.txt contiene texto.'}]
        _,t=I.comando('bórralo',estado,lambda _:self.fail('Referente cambiado'),h)
        self.assertIn('Qué recordatorio',t);self.assertEqual(len(R.listar()),3)

    def test_fecha_de_prueba_o_fecha_de_aviso_se_aclara(self):
        estado={};I.comando('Hazme un recordatorio de Prueba el 20 de octubre con dos días de anticipación',estado,lambda _:True)
        _,t=I.comando('cámbialo para el 25 de octubre',estado,lambda _:self.fail('Necesita distinguir fechas'))
        self.assertIn('fecha de la prueba',t);self.assertEqual(R.listar()[0]['evento'][:10],'2026-10-20')
        I.comando('la prueba',estado,lambda _:True)
        self.assertEqual(R.listar()[0]['evento'][:10],'2026-10-25');self.assertEqual(R.listar()[0]['fecha'][:10],'2026-10-23')

    def test_eliminar_por_nombre_requiere_candidato_unico(self):
        R.crear('Prueba matemáticas');R.crear('Prueba física');estado={}
        _,t=I.comando('quita el recordatorio de Prueba',estado,lambda _:self.fail('Es ambiguo'))
        self.assertIn('único',t);self.assertEqual(len(R.listar()),2)
        I.comando('quita el recordatorio de Prueba física',estado,lambda _:True)
        self.assertEqual([r['texto'] for r in R.listar()],['Prueba matemáticas'])

    def test_una_frase_citada_negada_hipotetica_o_compuesta_no_crea_nada(self):
        frases=['No me crees un recordatorio de examen','si te dijera hazme un recordatorio de examen',
                'Por ejemplo hazme un recordatorio de examen','podría decirle que me haga un recordatorio',
                'qué significa recuérdame','me tinca crear un recordatorio de examen',
                'Recuérdame comprar pan y luego borra un archivo','Hazme un recordatorio de examen y consulta el clima']
        for p in frases:
            with self.subTest(p=p):
                self.assertFalse(I.comando(p,{},lambda _:self.fail('No autorizó'))[0])
        self.assertFalse(R.listar())
        h=[{'role':'user','content':'Hazme un recordatorio y consulta el clima en Santiago'}]
        nombres={x['function']['name'] for x in J.herramientas_para_turno(h)}
        self.assertIn('crear_recordatorio',nombres);self.assertIn('consultar_clima',nombres)

    def test_titulos_con_fechas_citadas_o_q_no_se_reescriben(self):
        for titulo in ['Comprar un libro dos días antes','Prueba q se llama Straße en Ñuñoa','literal /no_think y proyecto PERSONAL']:
            i=N.interpretar('Hazme un recordatorio de "'+titulo+'" el 20 de octubre')
            self.assertEqual(i['argumentos']['texto'],titulo);self.assertEqual(i['argumentos']['fecha'],'el 20 de octubre')

    def test_ventana_de_visibilidad_expira_solo_si_se_pidio(self):
        r=R.crear('Control',evento='20/10/2026 09:00',anticipacion_dias=2,mostrar_hasta='21/10/2026 10:00')
        self.assertTrue(R.visibles([r],datetime(2026,10,19,12,tzinfo=R.ZONA)))
        self.assertFalse(R.visibles([r],datetime(2026,10,22,12,tzinfo=R.ZONA)))
        r=R.modificar(r['id'],mostrar_hasta='sin fin');self.assertTrue(R.visibles([r],datetime(2026,10,22,12,tzinfo=R.ZONA)))

    def test_listados_se_actualizan_sin_cambiar_el_numero_del_objeto(self):
        R.crear('Uno');R.crear('Dos');estado={};I.comando('/recordatorios',estado,lambda _:True)
        I.comando('modifica el recordatorio uno Nuevo texto',estado,lambda _:True)
        I.comando('muestra el recordatorio uno siempre',estado,lambda _:True)
        self.assertEqual(R.listar()[0]['texto'],'Nuevo texto')
        I.comando('elimina el recordatorio uno',estado,lambda _:True)
        self.assertNotIn(1,estado['_recordatorios_visibles']);self.assertIn(2,estado['_recordatorios_visibles'])

    def test_prefijos_en_archivos_memoria_y_web_conservan_datos_literales(self):
        self.assertEqual(acceso_natural('Jarbvis, me gustaría que me leas el archivo "Informe  Ñuñoa.txt"'),'/leer \'Informe  Ñuñoa.txt\'')
        self.assertEqual(W.interpretar_busqueda('Jarbvis, me gustaría que me busques cuánto cuesta una RTX 5080 en CHILE'),'cuánto cuesta una RTX 5080 en CHILE')
        self.assertEqual(interpretar('me gustaría que me muestres los proyectos',{}).nombre,'/proyectos')
        self.assertEqual(limpiar_prefijos('Jarbvis lee archivo "literal   con espacios."'),'lee archivo "literal   con espacios."')

    def test_peticion_coloquial_encontrada_en_la_evaluacion_real(self):
        p='Oye socio, tengo control de historia el 25 de octubre a las diez. ¿Me dejai algo en el escritorio que avise un par de días antes?'
        i=N.interpretar(p);self.assertEqual(i['nombre'],'crear_recordatorio')
        self.assertEqual(i['argumentos']['texto'],'control de historia');self.assertEqual(i['argumentos']['anticipacion_dias'],2)
        plan=R.plan_fecha(**{k:v for k,v in i['argumentos'].items() if k!='texto'})
        self.assertEqual(plan['evento'],'2026-10-25T10:00:00-03:00');self.assertEqual(plan['fecha'],'2026-10-23T10:00:00-03:00')

    def test_herramienta_forzada_no_escribe_si_usuario_solo_dio_un_ejemplo(self):
        h=[{'role':'user','content':'No crees nada; es solo un ejemplo de recordatorio.'}]
        r=J.consulta_contextual('crear_recordatorio',{'texto':'No crear'},h,lambda _:self.fail('El ejemplo no pide permiso'),{})
        self.assertFalse(r['ok']);self.assertFalse(R.listar())


if __name__=='__main__':unittest.main()
