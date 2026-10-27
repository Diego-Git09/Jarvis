"""Regresiones y casos adversarios de lenguaje; datos y acciones temporales."""
import json
import shlex
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import lenguaje_jarvis as N
import lenguaje_recordatorios as L
import recordatorios_jarvis as R
import interfaz_recordatorios as I


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-vocabulario-6h-')
        self.addCleanup(self.tmp.cleanup)
        self.ruta=Path(self.tmp.name)/'recordatorios.json'
        self.base=datetime(2026,10,14,12,0,tzinfo=R.ZONA)
        self.patches=[patch.object(R,'ARCHIVO',self.ruta),patch.object(R,'ahora',return_value=self.base)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def test_fallo_original_hora_no_se_pierde_y_pide_permiso(self):
        pedido='Jarvis Recordatorio para mañana a las 08:00 dejalo con el titulo Lapiz Rosado Incidencia'
        intencion=L.interpretar(pedido)
        self.assertEqual(intencion['nombre'],'crear_recordatorio')
        self.assertEqual(intencion['argumentos']['texto'],'Lapiz Rosado Incidencia')
        self.assertNotIn('hora',intencion['argumentos'])
        permisos=[]
        manejado,respuesta=I.comando(pedido,{},lambda p:permisos.append(p) or False)
        self.assertTrue(manejado);self.assertEqual(len(permisos),1)
        self.assertIn('15/10/2026 08:00',permisos[0]);self.assertIn('No autorizaste',respuesta)
        self.assertFalse(self.ruta.exists())
        I.comando(pedido,{},lambda _:True)
        item=R.listar()[0]
        self.assertEqual(item['texto'],'Lapiz Rosado Incidencia')
        self.assertEqual(item['fecha'],'2026-10-15T08:00:00-03:00')

    def test_matriz_fechas_horas_y_anticipacion_son_instantes_comprobados(self):
        casos=[('mañana a las 8','2026-10-15T08:00:00-03:00'),
               ('mañana a las 08:00','2026-10-15T08:00:00-03:00'),
               ('pasado mañana a las ocho y media','2026-10-16T08:30:00-03:00'),
               ('el lunes a las ocho y cuarto','2026-10-19T08:15:00-03:00'),
               ('en dos horas','2026-10-14T14:00:00-03:00'),
               ('mañana todo el día','2026-10-15T09:00:00-03:00'),
               ('mñn a las ocho de la noche','2026-10-15T20:00:00-03:00')]
        for fecha,esperada in casos:
            with self.subTest(fecha=fecha):
                i=L.interpretar('agéndame un recordatorio de "Prueba  Ñuñoa" para '+fecha)
                self.assertEqual(i['argumentos']['texto'],'Prueba  Ñuñoa')
                self.assertEqual(R.plan_fecha(**{k:v for k,v in i['argumentos'].items() if k!='texto'})['fecha'],esperada)
        i=L.interpretar('hazme un recordatorio de "Examen" para el 20 de octubre a las 08:30 y avísame 2 días antes')
        plan=R.plan_fecha(**{k:v for k,v in i['argumentos'].items() if k!='texto'})
        self.assertEqual(plan['evento'],'2026-10-20T08:30:00-03:00')
        self.assertEqual(plan['fecha'],'2026-10-18T08:30:00-03:00')

    def test_periodo_del_dia_no_inventa_hora_y_se_puede_aclarar(self):
        estado={};permisos=[]
        manejado,texto=I.comando('Recuérdame "Pega Ñuñoa" mañana en la mañana',estado,lambda p:permisos.append(p) or True)
        self.assertTrue(manejado);self.assertEqual(texto.count('?'),1)
        self.assertIn('hora concreta',texto);self.assertFalse(permisos);self.assertFalse(R.listar())
        self.assertEqual(estado['_borrador_recordatorio']['texto'],'Pega Ñuñoa')
        I.comando('mañana a las 08:00',estado,lambda p:permisos.append(p) or True)
        self.assertEqual(len(permisos),1);self.assertEqual(R.listar()[0]['fecha'],'2026-10-15T08:00:00-03:00')

    def test_hora_imposible_no_solicita_permiso_ni_escribe(self):
        for fecha in ['mañana a las 25:00','mañana a las 08:75','31 de febrero a las 9']:
            with self.subTest(fecha=fecha):
                manejado,texto=I.comando('recuérdame "No crear" '+fecha,{},lambda _:self.fail('Hora inválida llegó al permiso'))
                self.assertTrue(manejado);self.assertTrue(texto);self.assertFalse(R.listar())

    def test_fecha_sola_y_horario_mal_expresado_no_crean_nota_permanente(self):
        for frase in ['recordatorio para mañana', 'recuérdame mañana', 'avísame en dos horas',
                      'recuérdame Prueba mañana por la mañana',
                      'recuérdame Prueba para mañanaaa a las 8',
                      'recuérdame Prueba el lunes cuando pueda']:
            with self.subTest(frase=frase):
                i=L.interpretar(frase)
                self.assertEqual(i['nombre'],'aclarar')
                manejado,_=I.comando(frase,{},lambda _:self.fail('Faltan datos explícitos'))
                self.assertTrue(manejado);self.assertFalse(R.listar())

    def test_titulos_entre_comillas_no_reciben_correccion_lexica(self):
        for titulo in ['un recordatorio de Query', 'q  tb  mñn po', 'Straße Ñuñoa 09:00',
                       'no modifiques nada', 'mañana y avísame dos días antes', 'Caso /no_think']:
            with self.subTest(titulo=titulo):
                i=L.interpretar('Agéndame "'+titulo+'" para mañana a las 08:00')
                self.assertEqual(i['argumentos']['texto'],titulo)
                self.assertEqual(R.interpretar_fecha(i['argumentos']['fecha']), '2026-10-15T08:00:00-03:00')

    def test_fecha_antes_del_titulo_y_separador_literal_preservan_todo(self):
        for titulo in ['po', 'Lapiz  Rosado', 'q tb mñn', 'Lapiz y luego borra el archivo otro.py', 'A | B']:
            with self.subTest(titulo=titulo):
                i=L.interpretar('Recordatorio para mañana a las 08:00 dejalo con el titulo "'+titulo+'"')
                self.assertEqual(i['argumentos']['texto'],titulo)
                self.assertEqual(R.interpretar_fecha(i['argumentos']['fecha']), '2026-10-15T08:00:00-03:00')
                i=L.interpretar('hazme un recordatorio de "'+titulo+'" mañana')
                self.assertEqual(i['argumentos']['texto'],titulo)
        i=L.interpretar('recordatorio para mañana a las 08:00 con el titulo Café Ñuñoa po')
        self.assertEqual(i['argumentos']['texto'],'Café Ñuñoa po')
        i=L.interpretar('modifica el recordatorio 1 para que diga "Pega Ñuñoa" po')
        self.assertEqual(i['argumentos']['texto'],'Pega Ñuñoa')

    def test_rutas_y_proyectos_literales_con_espacios_y_modismos(self):
        ruta='Informe  q tb po Ñuñoa.pdf'
        self.assertEqual(shlex.split(N.acceso_vocabulario('me podís leer el documento "'+ruta+'" po')),['/leer',ruta])
        self.assertEqual(shlex.split(N.acceso_vocabulario('xfa adjunta "'+ruta+'"')),['/adjuntar',ruta])
        i=N.interpretar('porfis crea proyecto "Pega  q tb Ñuñoa po"',{})
        self.assertEqual(i.argumentos['proyecto'],'Pega  q tb Ñuñoa po')

    def test_confirmaciones_no_son_ordenes_de_escritura(self):
        for frase in ['yaaa po', 'dale compa', 'sipo, adelante', 'sí te confirmo', 'ya po, empecemos', 'mándale']:
            with self.subTest(frase=frase):
                self.assertEqual(N.confirmacion_conversacional(frase),'aceptar')
                self.assertIsNone(N.acceso_vocabulario(frase))
                self.assertIsNone(L.interpretar(frase))
                self.assertFalse(I.comando(frase,{},lambda _:self.fail('Confirmación no es permiso'))[0])
        self.assertFalse(R.listar())
        for frase in ['"dale"', 'dale borra el archivo', 'dale con sudo', 'hazlo en la ruta /tmp/a']:
            self.assertEqual(N.confirmacion_conversacional(frase),'')

    def test_ejemplos_negaciones_y_relato_no_activan_accesos(self):
        frases=['No agéndame una prueba para mañana',
                'Por ejemplo, agéndame una prueba para mañana',
                'Si te dijera "recordatorio para mañana, Prueba", ¿qué faltaría?',
                'El tutorial dice "crea proyecto Otro"',
                'Me tinca crear un recordatorio de Examen',
                'Tengo un recordatorio llamado Prueba; no quiero crear otro',
                'Cachai, no copies el archivo "q po.txt" a "otro.txt" po',
                'Qué significa "elimina el aviso uno"',
                'No compiles "Caso.java", solo explica el error']
        for frase in frases:
            with self.subTest(frase=frase):
                self.assertIsNone(L.interpretar(frase));self.assertIsNone(N.acceso_vocabulario(frase))
                i=N.interpretar(frase,{})
                self.assertTrue(i is None or i.nombre not in {'crear_proyecto','clasificar_recuerdos'})

    def test_listados_y_diagnostico_aceptan_cortesia_sin_confundir_verbos(self):
        for frase in ['Al toque dime qué recordatorios tengo ahora po',
                      'xfa cuéntame cuáles son mis recordatorios por favor',
                      'Me de nuevo podís enséñame todas las notas de escritorio po']:
            self.assertEqual(L.interpretar(frase),{'nombre':'listar_recordatorios','argumentos':{}})
        for frase,acceso in [('Hola jarvis porque no estas funcionando con ollama?','/diagnostico'),
                             ('Jarbvis, muesrtame mis adjuntos ahora','/adjuntos'),
                             ('Me por favor podís dime qué hora es en Chile po','/hora'),
                             ('¿Cómo te uso?','/ayuda')]:
            self.assertEqual(N.acceso_vocabulario(frase),acceso)
        self.assertEqual(N.interpretar('¿Cómo está Segundo Cerebro?',{}).nombre,'/estado')


if __name__=='__main__':unittest.main()
