"""Persistencia, alcance y comandos de práctica por contexto."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import mejoras_jarvis as M
import desarrollo_jarvis as D
import jarvis_agente as J
from interfaz_local import comando_local

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.anterior=M.ARCHIVO;M.ARCHIVO=Path(self.tmp.name)/'preferencias.json'
        self.estado={}
    def tearDown(self):M.ARCHIVO=self.anterior;self.tmp.cleanup()
    def comando(self,p,si=True):return comando_local(p,[],self.estado,lambda _:si,J.AJUSTES,lambda:None,None)
    def test_temas_reales_y_alias_android(self):
        self.assertEqual(D.temas('Andorid Studio Kotlin'),['android']);self.assertEqual(D.temas('revisa este .java'),['java'])
        self.assertEqual(D.temas('Python con SQL'),['python','sql']);self.assertEqual(D.temas('hola Diego'),[])
        self.assertEqual(D.temas('pyton'),['python']);self.assertEqual(D.temas('anroid Studio'),['android']);self.assertEqual(D.temas('journalctl'),['ubuntu'])
        self.assertEqual(D.temas('JavaScript'),[])
    def test_comandos_por_tema_y_correspondencia(self):
        for tema in M.CASOS:
            ok,texto=self.comando('/entrenamiento '+tema)
            self.assertTrue(ok);self.assertIn('Tema: '+tema,texto);self.assertIn('Caso:',texto)
            self.assertEqual(self.estado['_entrenamiento_tema'],tema);self.comando('/cancelar')
    def test_natural_y_mejoras_contextuales(self):
        self.assertTrue(self.comando('entrenemos sobre Python')[0]);self.comando('/cancelar')
        for tema in D.TEMAS:self.assertIn(D.TEMAS[tema][0],self.comando('/mejoras '+tema)[1])
    def test_no_guardar_sin_confirmacion(self):
        self.comando('/entrenamiento sql');self.assertIn('No guardé',self.comando('Primero pregunta por el motor.',False)[1]);self.assertFalse(M.ARCHIVO.exists())
    def test_no_contamina_otros_contextos(self):
        self.comando('/entrenamiento sql');self.comando('En SQL usa etiqueta MOTOR_42.')
        self.assertIn('MOTOR_42',M.contexto(pedido='SQL con tablas'));self.assertNotIn('MOTOR_42',M.contexto(pedido='Java con clases'))
        self.assertNotIn('MOTOR_42',J.prompt_para_turno('hola'));self.assertIn('MOTOR_42',J.prompt_para_turno('SQL'))
    def test_archivo_corrupto_se_conserva_y_se_informa(self):
        M.ARCHIVO.write_text('{roto');self.assertIn('Conservé',self.comando('/entrenamiento python')[1])
        with self.assertRaises(ValueError):M.registrar({'situacion':'x','preferencia':'y'})
        self.assertEqual(M.ARCHIVO.read_text(),'{roto');self.assertIn('no están disponibles',M.contexto())
    def test_guardado_fallido_no_pierde_practica(self):
        self.comando('/entrenamiento java')
        with patch.object(M,'guardar',side_effect=OSError('falló el disco')):self.assertIn('sigue abierta',self.comando('Lee la firma antes.')[1])
        self.assertTrue(self.estado['_entrenamiento_pendiente'])
    def test_cancelar_limpia_todo_y_no_escribe(self):
        self.comando('/entrenamiento ubuntu');self.comando('/cancelar');self.assertEqual(self.estado,{})
        self.assertFalse(M.ARCHIVO.exists())
    def test_estado_no_inventa_puntuacion(self):
        texto=self.comando('/entrenamiento estado')[1];self.assertIn('sin ejemplos',texto);self.assertIn('no una puntuación',texto)
    def test_no_cambia_tema_mientras_hay_practica(self):
        self.comando('/entrenamiento python');self.assertIn('abierta',self.comando('/entrenamiento sql')[1]);self.assertEqual(self.estado['_entrenamiento_tema'],'python')
    def test_registro_concurrente_no_pierde_correcciones(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as exe:list(exe.map(lambda i:M.registrar({'situacion':str(i),'preferencia':'Verifica '+str(i),'tema':'python'}),range(20)))
        self.assertEqual(M.leer()['sesiones'],20);self.assertEqual(len(M.leer()['preferencias']),20);self.assertEqual(M.ARCHIVO.stat().st_mode&0o777,0o600)
    def test_rechaza_preferencia_vacia(self):
        with self.assertRaises(ValueError):M.registrar({'situacion':'x','preferencia':' '})
        self.comando('/entrenamiento python');self.assertIsNone(M.proponer(self.estado,'  '));self.assertFalse(M.ARCHIVO.exists())
    def test_esquema_de_contadores_roto_no_se_sobrescribe(self):
        texto=json.dumps({'preferencias':[],'sesiones':0,'totales_por_tema':[]});M.ARCHIVO.write_text(texto)
        self.assertIn('Conservé',self.comando('/entrenamiento python')[1]);self.assertEqual(M.ARCHIVO.read_text(),texto)
    def test_rotacion_no_se_estanca_al_superar_40_preferencias(self):
        casos=[]
        for _ in range(46):
            M.iniciar(self.estado,'python');casos.append(self.estado['_entrenamiento_situacion']);M.registrar(M.proponer(self.estado,'Comprueba el código.'));M.cancelar(self.estado)
        self.assertNotEqual(casos[44],casos[45]);self.assertEqual(len(M.leer()['preferencias']),40)
    def test_metricas_sql_no_confunden_dinero_y_filas(self):
        self.assertIn('COUNT(*)',D.aclaracion_sql('cantidad por zona de ventas monto >= 1'))
        self.assertIn('COUNT(*)',D.aclaracion_sql('número de registros'))
        self.assertIn('SUM',D.aclaracion_sql('suma de importes por zona'))
        self.assertEqual(D.aclaracion_sql('cantidad de dinero'), '');self.assertEqual(D.aclaracion_sql('cantidad de productos disponibles'),'')
        self.assertNotIn('COUNT',D.aclaracion_sql('no contar ventas, sumar importes'))
        self.assertNotIn('COUNT',D.aclaracion_sql('cantidad por zona de ventas; por cantidad me refiero a la suma de montos'))
    def test_no_guardes_cancela_sin_otro_permiso(self):
        self.comando('/entrenamiento sql')
        with patch.object(M,'registrar',side_effect=AssertionError('No guardar')):
            self.assertIn('cancelada',self.comando('no guardes esto')[1])
        self.assertFalse(M.ARCHIVO.exists());self.assertFalse(self.estado.get('_entrenamiento_pendiente'))
    def test_valores_unicos_filtrados_preservan_umbral_explicito(self):
        t=D.aclaracion_colecciones('Java contar valores únicos >= 5')
        self.assertIn('valor >= 5',t);self.assertIn('una vez',t)
        self.assertEqual(D.aclaracion_colecciones('valores únicos >= 5 y <= 10'),'')
        self.assertEqual(D.aclaracion_colecciones('valores repetidos >= 5'),'')
        self.assertEqual(D.aclaracion_colecciones('palabras únicas de longitud >= 5'),'')

if __name__=='__main__':unittest.main()
