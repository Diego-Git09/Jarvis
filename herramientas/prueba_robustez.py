import io
import unittest
from unittest.mock import patch
import jarvis_agente as J


class Pruebas(unittest.TestCase):
    def test_listado_modelos_malformado_da_error_comprensible(self):
        import cliente_ollama as O
        for lista in [None,2,'modelos',{}]:
            with patch.object(O,'solicitar',return_value={'models':lista}):
                with self.assertRaises(ConnectionError):O.modelos()

    def test_respuestas_malformadas_no_ejecutan_herramientas(self):
        for r in [None,[],{'content':2},{'content':'x','tool_calls':'x'},
                  {'content':'','tool_calls':[{'function':'x'}]},
                  {'content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':[]}}]}]:
            with patch.object(J,'ejecutar_herramienta') as ejecutar:
                with self.assertRaises(ConnectionError):J.ejecutar_turno([],lambda _:r,lambda _:True,{})
                ejecutar.assert_not_called()

    def test_toda_la_respuesta_se_valida_antes_de_ejecutar(self):
        r={'content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{'ruta':'x','contenido':'x'}}},{'function':'mal'}]}
        with patch.object(J,'ejecutar_herramienta') as ejecutar:
            with self.assertRaises(ConnectionError):J.ejecutar_turno([],lambda _:r,lambda _:True,{})
            ejecutar.assert_not_called()

    def test_permisos_denegados_no_son_exito_del_modelo(self):
        cola=iter([{'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{'ruta':'x.txt','contenido':'x'}}}]},
                   {'role':'assistant','content':'Archivo creado.'}])
        with patch.object(J.L,'_registrar'):
            r=J.ejecutar_turno([{'role':'user','content':'crea x.txt'}],lambda _:next(cola),lambda _:False,{},mostrar=lambda _:None)
        self.assertIn('no autorizó',r);self.assertNotIn('Archivo creado',r)

    def test_creacion_sin_herramienta_no_se_confirma(self):
        h=[{'role':'user','content':'crea x.txt'}]
        r=J.ejecutar_turno(h,lambda _:{'role':'assistant','content':'He creado x.txt.'},lambda _:True,{},mostrar=lambda _:None)
        self.assertIn('No ejecuté',r)

    def test_herramientas_se_reducen_solo_si_el_dominio_es_claro(self):
        files={h['function']['name'] for h in J.herramientas_para_turno([{'role':'user','content':'lee el archivo prueba.txt'}])}
        self.assertIn('leer_archivo',files);self.assertNotIn('clasificar_memoria',files)
        mem={h['function']['name'] for h in J.herramientas_para_turno([{'role':'user','content':'muestra los recuerdos de Jarvis'}])}
        self.assertIn('listar_memorias',mem);self.assertNotIn('crear_archivo',mem)
        self.assertEqual(J.herramientas_para_turno([{'role':'user','content':'hola'}]),[])
        mezcla={h['function']['name'] for h in J.herramientas_para_turno([{'role':'user','content':'guarda los recuerdos en un archivo'}])}
        self.assertIn('listar_memorias',mezcla);self.assertIn('crear_archivo',mezcla)
        self.assertNotIn('preguntar_ia_externa',mezcla)

    def test_fallo_del_log_no_oculta_una_lectura_exitosa(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'a.txt').write_text('contenido')
            bloqueo=root/'bloqueo';bloqueo.write_text('no es carpeta')
            with patch.object(J.L,'RAIZ',root),patch.object(J.L,'REGISTRO',bloqueo/'log.jsonl'):
                r=J.L.leer_archivo('a.txt')
            self.assertTrue(r['ok']);self.assertEqual(r['contenido'],'contenido')
            self.assertIn('aviso_registro',r)

    def test_indicador_no_se_usa_en_salida_redirigida(self):
        with patch.object(J.sys.stdout,'isatty',return_value=False):
            self.assertEqual(J._con_indicador(lambda _: {'content':'ok'})([]),{'content':'ok'})


if __name__=='__main__':unittest.main()
