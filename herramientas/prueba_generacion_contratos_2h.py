"""Regresiones surgidas de inferencia real: referencias copiadas y métodos anidados."""
import json,unittest
from unittest.mock import patch
import proyectos_codigo as P
import prueba_proyectos_codigo as FIX
import desarrollo_jarvis as D


class Pruebas(unittest.TestCase):
    def setUp(self):
        FIX.Pruebas.setUp(self)
        FIX.Pruebas.iniciar(self);FIX.Pruebas.plan(self,['logica.py'])
        self.destino=self.work/'app'/'logica.py'
        self.prueba=self.work/'app'/'test_logica.py'
        self.prueba.write_text('import unittest\nfrom logica import resolver, etiqueta\nclass Caso(unittest.TestCase):\n def test_resultado(self): self.assertEqual(resolver(100),103.0)\n def test_nombre(self): self.assertEqual(etiqueta(),"PRUEBA_1")\n')
        self.permisos.clear()

    def si(self,texto):self.permisos.append(texto);return True

    def test_corrige_clase_antes_de_ofrecer_escritura(self):
        vistos=[]
        def enviar(_ruta,cuerpo,**kw):
            vistos.append(cuerpo)
            contenido='class Logica:\n def resolver(self,x):return x*1.03\n' if len(vistos)==1 else 'def resolver(x):return round(x*1.03,2)\ndef etiqueta():return "PRUEBA_1"\n'
            return {'message':{'content':json.dumps({'contenido':contenido,'explicacion':'Implementación'})}}
        texto=P.desarrollar('Genera logica.py. resolver incrementa un 3 por ciento.',{},self.si,enviar,'falso')
        self.assertEqual(len(vistos),2);self.assertIn('nivel del módulo',vistos[1]['messages'][1]['content'])
        self.assertNotIn('class Logica',self.destino.read_text());self.assertIn('Comprobación correcta',texto)
        self.assertFalse(any('class Logica' in p for p in self.permisos))

    def test_fallo_persistente_no_sustituye_original_ni_pruebas(self):
        original='def resolver(x):return x\ndef etiqueta():return "PRUEBA_1"\n';self.destino.write_text(original)
        pruebas=self.prueba.read_bytes()
        enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'{"codigo_actual":"texto"}','explicacion':'Datos en vez de código'})}}
        texto=P.desarrollar('Corrige logica.py según las pruebas actuales.',{},self.si,enviar,'falso')
        self.assertEqual(self.destino.read_text(),original);self.assertEqual(self.prueba.read_bytes(),pruebas)
        self.assertIn('No escribí',texto);self.assertIn('nivel del módulo',P.activo()['error'])
        self.assertFalse(any('Crear ' in p or '---' in p for p in self.permisos))

    def test_peticion_actual_va_despues_de_referencias_antiguas(self):
        self.destino.write_text('def resolver(x):return x*1.01\ndef etiqueta():return "PRUEBA_1"\n')
        with P.transaccion():
            d=P.leer();d['proyectos'][P.activo()['id']]['requisitos']=['resolver usa 1 por ciento'];P.guardar(d)
        vistos=[]
        def enviar(_r,cuerpo,**kw):
            vistos.append(cuerpo)
            return {'message':{'content':json.dumps({'contenido':'def resolver(x):return round(x*1.03,2)\ndef etiqueta():return "PRUEBA_1"\n','explicacion':'3% actual'})}}
        P.desarrollar('Cambia logica.py: ahora aplica 3 por ciento.',{},self.si,enviar,'falso')
        mensajes=vistos[0]['messages'];self.assertIn('ahora aplica 3 por ciento',mensajes[-1]['content'])
        self.assertNotIn('requisitos_recientes',mensajes[1]['content']);self.assertIn('resolver',mensajes[0]['content'])

    def test_json_duplicado_no_escribe(self):
        enviar=lambda *_a,**_k:{'message':{'content':'{"contenido":"a","contenido":"b","explicacion":"x"}'}}
        texto=P.desarrollar('Genera logica.py.',{},self.si,enviar,'falso')
        self.assertFalse(self.destino.exists());self.assertIn('No se escribió',texto);self.assertFalse(self.permisos)

    def test_ejemplos_incluyen_resultados_actuales_y_tipos(self):
        t=D.entradas_de_pruebas([self.prueba.read_text()])
        self.assertIn('103.0',t);self.assertIn('int',t)

    def test_correccion_por_otro_local_declara_modelo_real(self):
        modelos=[];e={}
        def enviar(_ruta,cuerpo,**kw):
            modelos.append(cuerpo['model'])
            texto='class Logica:\n def resolver(self,x):return x\n' if len(modelos)==1 else 'def resolver(x):return round(x*1.03,2)\ndef etiqueta():return "PRUEBA_1"\n'
            return {'message':{'content':json.dumps({'contenido':texto,'explicacion':'Código'})}}
        t=P.desarrollar('Genera logica.py',e,self.si,enviar,'principal-local',modelo_alternativo='otro-local')
        self.assertEqual(modelos,['principal-local','otro-local']);self.assertIn('Corrección propuesta por otro modelo local',t)
        self.assertEqual(e['_codigo_estadisticas']['modelo'],'otro-local');self.assertTrue(e['_codigo_estadisticas']['correccion_local'])

    def test_timeout_sin_escritura_puede_usar_otro_local(self):
        modelos=[]
        def enviar(_ruta,cuerpo,**kw):
            modelos.append(cuerpo['model'])
            if len(modelos)==1:raise TimeoutError('Sintético')
            return {'message':{'content':json.dumps({'contenido':'def resolver(x):return round(x*1.03,2)\ndef etiqueta():return "PRUEBA_1"\n','explicacion':'Código'})}}
        t=P.desarrollar('Genera logica.py',{},self.si,enviar,'principal-local',modelo_alternativo='otro-local')
        self.assertEqual(modelos,['principal-local','otro-local']);self.assertIn('Comprobación correcta',t)

    def test_correccion_tras_test_fallido_sigue_pidiendo_permiso(self):
        modelos=[]
        def enviar(_ruta,cuerpo,**kw):
            modelos.append(cuerpo['model']);porcentaje='1.01' if len(modelos)==1 else '1.03'
            return {'message':{'content':json.dumps({'contenido':f'def resolver(x):return round(x*{porcentaje},2)\ndef etiqueta():return "PRUEBA_1"\n','explicacion':'Propuesta'})}}
        def permiso(texto):return '---' not in texto
        t=P.desarrollar('Genera logica.py',{},permiso,enviar,'principal-local',modelo_alternativo='otro-local')
        self.assertEqual(modelos,['principal-local','otro-local']);self.assertIn('1.01',self.destino.read_text());self.assertNotIn('1.03',self.destino.read_text())
        self.assertIn('No autorizaste',t);self.assertFalse(P.estado(P.activo())['validacion_vigente'])

    def test_restriccion_de_modelo_no_se_confunde_con_solo_local(self):
        import respaldo_local as R
        for p in ['solo DeepSeek','solo con Qwen','No uses otro modelo','Sin usar Qwen']:
            self.assertFalse(R.admite_otro(p))
        self.assertTrue(R.admite_otro('Solo local, sin nube'))

    def test_codigo_publica_presupuesto_y_total_real_de_su_propio_payload(self):
        e={}
        enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'def resolver(x):return round(x*1.03,2)\ndef etiqueta():return "PRUEBA_1"\n','explicacion':'Código'})},'prompt_eval_count':123}
        P.desarrollar('Genera logica.py',e,self.si,enviar,'falso')
        r=e['_presupuesto_contexto'];self.assertEqual(r['tokens_entrada_reales'],123)
        self.assertGreater(r['resultados_tokens_estimados'],0);self.assertGreater(r['herramientas_tokens_estimados'],0)
        self.assertEqual(e['_codigo_estadisticas']['presupuesto_contexto'],r)

    def test_referencias_excesivas_no_se_envian_ni_crean_archivo(self):
        self.prueba.write_text(self.prueba.read_text()+'# comentario sintético\n'*400);e={}
        with patch.object(P,'activo',wraps=P.activo),patch.object(P,'estado',wraps=P.estado):
            def enviar(*_a,**_k):self.fail('No debe enviar un contexto que excede el margen')
            t=P.desarrollar('Genera logica.py',e,self.si,enviar,'falso',num_ctx=4096)
        self.assertIn('/contexto',t);self.assertFalse(self.destino.exists());self.assertIn('_presupuesto_contexto',e)


if __name__=='__main__':unittest.main()
