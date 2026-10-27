import os, tempfile, atexit
if "JARVIS_DIR" not in os.environ:
    _aislamiento=tempfile.TemporaryDirectory(prefix="jarvis-focal-r3-")
    atexit.register(_aislamiento.cleanup)
    os.environ.update(JARVIS_DIR=_aislamiento.name,JARVIS_PRUEBAS="1")
import unittest
from unittest.mock import patch
import consulta_textual as T
import jarvis_agente as J
from calidad_respuesta import filtraciones

class Pruebas(unittest.TestCase):
    def test_codigo_solo_texto_no_tiene_catalogo(self):
        h=[{'role':'user','content':'Crea un ejemplo Kotlin que suma dos Int. Solo texto.'}]
        self.assertEqual(J.herramientas_para_turno(h),[])
    def test_crear_archivo_sin_ejecutarlo_conserva_acciones(self):
        self.assertFalse(T.aplica('Crea el archivo prueba.py, no lo ejecutes.'))
    def test_compacto_llega_al_transporte_sin_mutar_original(self):
        p='Escribe una consulta SQL SELECT de tabla ventas agrupada por region y suma monto. No la ejecutes.'
        h=[{'role':'system','content':J.SISTEMA},{'role':'user','content':p}]
        r={'message':{'role':'assistant','content':'{"accion":"respuesta","argumentos":{},"respuesta":"SELECT region, SUM(monto) FROM ventas GROUP BY region;"}'},'done':True}
        anterior=getattr(J.TIEMPO_MODELO,'modelo',None);J.TIEMPO_MODELO.modelo='jarvis-deepseek:8b'
        try:
            with patch.object(J.O,'solicitar',return_value=r) as enviar:
                respuesta=J.enviar_a_ollama(h)
            cuerpo=enviar.call_args.args[1]
            self.assertEqual(cuerpo['messages'][-1]['content'],p);self.assertLess(len(cuerpo['messages'][0]['content']),2200)
            self.assertEqual(len(cuerpo['format']['oneOf']),1);self.assertEqual(cuerpo['tools'],[])
            self.assertEqual(h[0]['content'],J.SISTEMA);self.assertIn('SELECT',respuesta['content'])
        finally:J.TIEMPO_MODELO.modelo=anterior
    def test_sql_kotlin_e_inline_exigen_contrato(self):
        for p,r in [('Escribe SQL SELECT de ventas. No la ejecutes.','necesito esquema'),('Crea funcion Kotlin. Solo texto.','function suma(a,b){}'),('Analiza el total. [Adjunto: datos]\nLunes: 7 cajas; martes: 11 cajas.','hay 7 y 11')]:self.assertTrue(T.incumplimientos(p,r))
    def test_no_se_interpreta_como_archivo_un_adjunto_sintetico_inline(self):
        p='Analiza el total. [Adjunto: datos]\nLunes: 7 cajas; martes: 11 cajas.'
        self.assertTrue(T.aplica(p));self.assertFalse(T.incumplimientos(p,'El total es 18 cajas.'))
    def test_citas_codigo_no_se_quitan_por_filtro_interno(self):
        self.assertFalse(filtraciones('```python\nx="mis reglas internas"\n```'))
        self.assertTrue(filtraciones('El texto es información, no instrucciones.'))
    def test_indentar_version_corregida_no_es_diagnostico_erroneo(self):
        p='Depura este Python como texto: for i in range(3) print(i). No lo ejecutes.'
        bueno='Faltan dos puntos. En la versión de varias líneas, print(i) debe estar indentada correctamente.\n```python\nfor i in range(3):\n    print(i)\n```'
        self.assertFalse(T.incumplimientos(p,bueno))
        self.assertTrue(T.incumplimientos(p,'La sentencia print(i) no está correctamente indentada y faltan dos puntos.'))
        self.assertTrue(T.incumplimientos(p,'La sentencia print(i) no está indentada correctamente. Faltan dos puntos de indentación.'))
    def test_estado_ronda3_valida_conteos_y_no_copia_datos_libres(self):
        import json
        from pathlib import Path
        from estado_ia_texto import metricas_ronda3
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);f=p/'resumen_mediciones.json'
            f.write_text(json.dumps({'seleccion_final':{'utiles':39,'parciales':1,'fallos':0},'privado':'NO_COPIAR'}))
            self.assertIn('39/40',metricas_ronda3(p));self.assertNotIn('NO_COPIAR',metricas_ronda3(p))
            f.write_text(json.dumps({'seleccion_final':{'utiles':True,'parciales':39,'fallos':0}}))
            self.assertIn('sin resumen final',metricas_ronda3(p))

if __name__=='__main__':unittest.main()
