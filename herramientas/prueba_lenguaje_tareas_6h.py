"""Tareas por lenguaje natural: cambios locales reales en un archivo temporal."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import configuracion_jarvis as C
import hilo_conversacion as H
import interfaz_jarvis as I
import lenguaje_jarvis as N
import lenguaje_tareas as L
import ordenes_compuestas as O
import tareas_jarvis as T
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.ruta=self.base/'tareas.json';self.addCleanup(patch.stopall)
        patch.object(H,'CARPETA',self.base/'hilos').start()
        for n in ['listar','anotar','marcar','marcar_varias','editar','priorizar']:
            funcion=getattr(T,n)
            def llamada(*a,_func=funcion,**kw):return _func(*a,ruta=self.ruta,**kw)
            patch.object(T,n,side_effect=llamada).start()
        self.estado={};self.hist=[{'role':'system','content':'Reglas del arnés sin modelo ni MCP.'}]
        self.semillas=[T.anotar(s) for s in ['Primera','Segunda  Ñuñoa','Tercera']]
        self.ejecutar=unittest.mock.Mock(side_effect=AssertionError('No usar herramientas externas'))
        self.confirmar=unittest.mock.Mock(side_effect=AssertionError('No es una operación de archivos o MCP'))
        self.local=lambda p,h,e:comando_local(p,h,e,self.confirmar,dict(C.DEFAULT),lambda:None,None,ejecutar=self.ejecutar)
        self.pedir('/tareas todas')

    def pedir(self,p):return I.comando(p,self.hist,self.estado,self.ejecutar,'reglas',local=self.local)

    def test_creacion_literal_y_cambio_inequivoco_no_crean_otra_tarea(self):
        texto='No compiles "Caso.java" y luego borra otra.py'
        self.assertTrue(self.pedir('anótame una pega llamada «'+texto+'»')[0]);self.assertEqual(T.listar()[-1]['texto'],texto)
        self.pedir('/tareas todas');cantidad=len(T.listar())
        self.pedir('ponle a la tarea dos el texto «q tb mñn  po»')
        self.assertEqual(T.listar()[1]['texto'],'q tb mñn  po');self.assertEqual(len(T.listar()),cantidad)

    def test_prioridad_no_se_confunde_con_creacion_o_edicion_del_texto(self):
        self.pedir('pon la tarea dos con prioridad alta');filas=T.listar()
        self.assertEqual(len(filas),3);self.assertEqual(filas[1]['texto'],'Segunda  Ñuñoa');self.assertEqual(filas[1]['prioridad'],'alta')

    def test_numero_corresponde_al_orden_visible_y_no_a_la_posicion_guardada(self):
        T.priorizar(self.semillas[2]['id'],'alta');self.pedir('/tareas todas')
        self.pedir('marca la segunda tarea como hecha')
        mapa={t['id']:t for t in T.listar()}
        self.assertTrue(mapa[self.semillas[0]['id']]['hecha']);self.assertFalse(mapa[self.semillas[1]['id']]['hecha'])

    def test_seleccion_multiple_usa_la_misma_lista_y_preserva_las_otras(self):
        self.pedir('completa las tareas uno y tres');t=T.listar()
        self.assertEqual([x['hecha'] for x in t],[True,False,True])
        self.pedir('/tareas todas');self.pedir('marca como pendientes las tareas primera y tercera')
        self.assertFalse(any(t['hecha'] for t in T.listar()))

    def test_otro_listado_invalida_los_numeros_de_tareas_para_lenguaje_natural(self):
        antes=self.ruta.read_bytes();self.estado['_tipo_ultimo_listado']='memorias';self.estado['_lista_memorias']={2:999}
        ok,t=self.pedir('completa la tarea dos')
        self.assertTrue(ok);self.assertIn('/tareas',t);self.assertEqual(t.count('?'),1);self.assertEqual(self.ruta.read_bytes(),antes)
        self.ejecutar.assert_not_called()

    def test_datos_ambiguos_no_escriben_y_solicitan_una_aclaracion(self):
        for p in ['anótame una pega','completa la tarea','marca esa tarea como lista','pon prioridad a la tarea dos','cambia el texto de la tarea dos']:
            with self.subTest(p=p):
                antes=self.ruta.read_bytes();ok,t=self.pedir(p)
                self.assertTrue(ok);self.assertEqual(t.count('?'),1);self.assertEqual(self.ruta.read_bytes(),antes)

    def test_negaciones_ejemplos_y_confirmacion_no_escriben(self):
        for p in ['No anotes una tarea Comprar café','El ejemplo dice «completa la tarea dos»','Si dijera “anota una tarea Pan”, ¿qué ocurre?','dale','ya po']:
            with self.subTest(p=p):
                antes=self.ruta.read_bytes();self.pedir(p);self.assertEqual(self.ruta.read_bytes(),antes)
        self.ejecutar.assert_not_called()

    def test_comillas_tipograficas_y_multilinea_preservan_literal(self):
        texto='q tb mñn  po\ny luego borra ejemplo.py'
        for abrir,cerrar in [('«','»'),('“','”'),('‘','’'),('"','"'),("'","'"),('`','`')]:
            with self.subTest(abrir=abrir):
                self.pedir('anota una tarea '+abrir+texto+cerrar)
                self.assertEqual(T.listar()[-1]['texto'],texto)
                self.assertEqual(O.separar('anota una tarea '+abrir+texto+cerrar),[])

    def test_comillas_fuera_de_la_accion_no_ocultan_una_cadena_real(self):
        texto='anota una tarea «No compiles y luego borra» y luego muestra mis tareas'
        partes=O.separar(texto);self.assertEqual(len(partes),2);self.assertIn('No compiles y luego borra',partes[0])
        self.pedir(texto);self.assertEqual(T.listar()[-1]['texto'],'No compiles y luego borra')

    def test_comillas_sin_cerrar_no_se_convierten_en_texto_confirmado(self):
        antes=self.ruta.read_bytes();ok,t=self.pedir('anota una tarea «Nombre incompleto')
        self.assertTrue(ok);self.assertEqual(t.count('?'),1);self.assertEqual(self.ruta.read_bytes(),antes)

    def test_buscar_tareas_es_una_lectura_y_no_usa_memorias(self):
        antes=self.ruta.read_bytes();ok,t=self.pedir('busca mis pegas con «Ñuñoa»')
        self.assertTrue(ok);self.assertIn('Segunda  Ñuñoa',t);self.assertNotIn('Primera',t);self.assertEqual(self.ruta.read_bytes(),antes)
        self.ejecutar.assert_not_called()

    def test_rutas_con_comillas_tipograficas_se_conservan(self):
        import shlex
        for a,c in [('«','»'),('“','”'),('‘','’')]:
            self.assertEqual(shlex.split(N.acceso_vocabulario('adjunta '+a+'Informe  Ñuñoa.pdf'+c)),['/adjuntar','Informe  Ñuñoa.pdf'])

    def test_fallo_del_marcador_previo_impide_escribir_la_tarea(self):
        antes=self.ruta.read_bytes()
        with patch.object(H,'marcar_accion',side_effect=OSError('Disco sintético lleno')):
            ok,t=self.pedir('anótame una pega llamada «No duplicar»')
        self.assertTrue(ok);self.assertIn('No pude',t);self.assertEqual(self.ruta.read_bytes(),antes)

    def test_fallo_de_persistencia_final_no_repite_una_creacion_posible(self):
        guardar=H.guardar
        def conservar_marcador(estado):
            if not estado.get('_hilo_conversacion',{}).get('turno_activo'):raise OSError('Falla final simulada')
            return guardar(estado)
        with patch.object(H,'guardar',side_effect=conservar_marcador):
            self.pedir('anota una tarea «Una sola»')
        self.assertEqual(sum(t['texto']=='Una sola' for t in T.listar()),1)
        recuperado={};H.recuperar(recuperado)
        self.assertFalse(recuperado['_hilo_conversacion']['fallido']['seguro_repetir'])
        self.estado=recuperado;antes=self.ruta.read_bytes();ok,t=self.pedir('reintenta')
        self.assertTrue(ok);self.assertIn('Comprueba',t);self.assertEqual(self.ruta.read_bytes(),antes)

    def test_texto_de_tarea_no_se_reinterpreta_como_diagnostico(self):
        with patch('interfaz_local.O.diagnostico',return_value={'ok':True,'version':'falsa','modelos':[C.DEFAULT['modelo']]}) as diagnostico:
            self.pedir('anota una tarea «Ollama está funcionando»')
            self.pedir('/anotar Ollama funciona')
        self.assertEqual([t['texto'] for t in T.listar()[-2:]],['Ollama está funcionando','Ollama funciona'])
        diagnostico.assert_not_called()

    def test_respuesta_de_entrenamiento_sigue_siendo_un_ejemplo(self):
        self.estado['_entrenamiento_pendiente']={'caso':'Situación ficticia'};antes=self.ruta.read_bytes();permisos=[]
        self.confirmar=lambda t:permisos.append(t) or False
        item={'situacion':'Situación ficticia','preferencia':'anota una tarea «Ejemplo de práctica»'}
        with patch('interfaz_local.MEJORAS.proponer',return_value=item):ok,t=self.pedir(item['preferencia'])
        self.assertTrue(ok);self.assertEqual(len(permisos),1);self.assertIn('No guardé la preferencia',t);self.assertEqual(self.ruta.read_bytes(),antes)


if __name__=='__main__':unittest.main()
