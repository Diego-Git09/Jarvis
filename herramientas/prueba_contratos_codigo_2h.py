"""No escribir un sobre JSON ni una clase cuando las pruebas importan funciones."""
import unittest
import contratos_codigo as C


class Pruebas(unittest.TestCase):
    def test_imports_exactos_y_alias_de_modulo(self):
        pruebas=['from logica import resolver as calcular, etiqueta\nimport logica as L\nL.constante\nfrom otro import no_requerido']
        self.assertEqual(C.requeridos_python(pruebas,'carpeta/logica.py'),['constante','etiqueta','resolver'])

    def test_metodo_anidado_no_exporta_la_funcion(self):
        codigo='class Logica:\n def resolver(self,x):return x\n def etiqueta(self):return "SINTETICA"'
        t=C.revisar_python(codigo,['resolver','etiqueta'])
        self.assertIn('nivel del módulo',t);self.assertIn('resolver',t)

    def test_exportacion_normal_reexportacion_y_asignacion(self):
        self.assertEqual(C.revisar_python('def resolver(x):return x\netiqueta=lambda:"SINTETICA"',['resolver','etiqueta']),'')
        self.assertEqual(C.revisar_python('from soporte import resolver\netiqueta: str="SINTETICA"',['resolver','etiqueta']),'')

    def test_sobre_de_datos_no_es_una_implementacion(self):
        self.assertIn('resolver',C.revisar_python('{"codigo_actual":"texto", "archivo":"logica.py"}',['resolver']))

    def test_sin_imports_explicitos_no_inventa_interfaz(self):
        self.assertEqual(C.requeridos_python(['# resolver es un ejemplo'],'logica.py'),[])
        self.assertEqual(C.revisar_python('x=1',[]),'')

    def test_no_ejecuta_codigo_al_inspeccionar(self):
        codigo='raise RuntimeError("NO_EJECUTAR")\ndef resolver(x):return x'
        self.assertEqual(C.revisar_python(codigo,['resolver']),'')

    def test_no_acepta_json_ambiguo_o_de_tipo_incorrecto(self):
        for texto in ['{"contenido":"a","contenido":"b","explicacion":"x"}',
                      '{"contenido":NaN,"explicacion":"x"}',
                      '{"contenido":1,"explicacion":"x"}',
                      '{"contenido":"x","explicacion":"y","otra":"z"}']:
            with self.assertRaises(ValueError):C.importar_json(texto)

    def test_sintaxis_invalida_se_deja_al_comprobador_existente(self):
        self.assertEqual(C.revisar_python('def rota(:',['resolver']),'')

    def test_no_conserva_asignacion_simple_que_ya_dio_nameerror(self):
        actual='def resolver(x):return x\nfallo=nombre_ausente\n'
        self.assertIn('NameError',C.error_conservado_python(actual,actual,"NameError: name 'nombre_ausente' is not defined"))
        self.assertEqual(C.error_conservado_python('nombre_ausente=3\n'+actual,actual,"NameError: name 'nombre_ausente' is not defined"),'')
        self.assertEqual(C.error_conservado_python('def resolver(x):return x',actual,"NameError: name 'nombre_ausente' is not defined"),'')

    def test_sin_error_anterior_no_inventa_un_fallo(self):
        self.assertEqual(C.error_conservado_python('dato=variable','dato=variable',''), '')

    def test_causa_verificada_sigue_disponible_en_siguiente_correccion(self):
        codigo='fallo=nombre_ausente\n'
        primero=C.error_conservado_python(codigo,codigo,"NameError: name 'nombre_ausente' is not defined")
        self.assertTrue(C.error_conservado_python(codigo,codigo,primero))


if __name__=='__main__':unittest.main()
