"""Desarrollo persistente, archivos reales y compilación aislada."""
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import proyectos_codigo as P
import herramientas_lectura as L
import herramientas_escritura as E
import jarvis_agente as J


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.work=self.base/'trabajo';self.work.mkdir()
        for objeto,atributo,valor in [(L,'RAIZ',self.work),(E,'RAIZ',self.work),(L,'REGISTRO',self.base/'log'),(E,'CAMBIOS',self.base/'cambios'),(E,'PENDIENTES',self.base/'pendientes'),(E,'COPIAS',self.base/'copias'),(P,'ARCHIVO',self.base/'datos'/'codigo.json')]:
            p=patch.object(objeto,atributo,valor);p.start();self.addCleanup(p.stop)
        self.s={};self.permisos=[]
    def si(self,texto):self.permisos.append(texto);return True
    def iniciar(self):return P.ejecutar('iniciar_proyecto_codigo',{'nombre':'Ejemplo','ruta':'app','objetivo':'Contar compradores y tránsito por acceso'},self.si,self.s)
    def test_posponer_compilacion_escribe_sin_ejecutar(self):
        for frase in ['No compiles todavía','No ejecutes pruebas','Sin compilar']:
            with self.subTest(frase=frase):
                self.iniciar();self.plan()
                destino=self.work/'app'/'Conteo.java'
                if destino.exists():destino.unlink()
                def enviar(*args,**kw):return {'message':{'content':json.dumps({'contenido':'public class Conteo {}','explicacion':'Clase mínima'})}}
                with patch.object(P,'validar',side_effect=AssertionError('No debe ejecutar')):
                    texto=P.desarrollar('Genera Conteo.java. '+frase,{},self.si,enviar,'modelo')
                self.assertTrue(destino.is_file());self.assertIn('posponer',texto)
                self.assertFalse(P.estado(P.activo())['validacion_vigente'])
    def plan(self,archivos=None):return P.ejecutar('actualizar_plan_codigo',{'etapas_json':json.dumps([{'titulo':'Lógica','archivos':archivos or ['Conteo.java']}])},self.si,self.s)
    def escribir(self,texto,ruta='Conteo.java'):return P.ejecutar('escribir_archivo_codigo',{'ruta':ruta,'contenido':texto},self.si,self.s)

    def test_iniciar_sin_permiso_no_crea_carpeta_ni_estado(self):
        r=P.ejecutar('iniciar_proyecto_codigo',{'nombre':'No','ruta':'app','objetivo':'Ejemplo'},lambda _:False,self.s)
        self.assertFalse(r['ok']);self.assertFalse((self.work/'app').exists());self.assertIsNone(P.activo())

    def test_negacion_sobre_argumentos_no_niega_generar_archivo(self):
        self.iniciar();self.plan(['logica.py'])
        enviar=lambda *a,**kw:{'message':{'content':json.dumps({'contenido':'def resolver(datos):\n return list(datos)\n','explicacion':'Copia de entrada'})},'done_reason':'stop'}
        r=P.desarrollar('Genera logica.py: copia la lista y no modifiques los argumentos.',{},self.si,enviar,'falso')
        self.assertIsNotNone(r);self.assertTrue((self.work/'app'/'logica.py').exists())

    def test_negacion_sobre_escritura_sigue_sin_generar(self):
        self.iniciar();self.plan(['logica.py'])
        with patch.object(J.O,'solicitar',side_effect=AssertionError('No debe pedir código')) as enviar:
            r=P.desarrollar('No generes logica.py; solo explica la firma.',{},self.si,enviar,'falso')
        self.assertIsNone(r);self.assertFalse((self.work/'app'/'logica.py').exists())

    def test_proyecto_plan_y_seleccion_sobreviven_a_nuevo_estado(self):
        self.iniciar();self.plan();self.escribir('public class Conteo {}')
        texto=P.contexto('sigamos con el código',{})
        self.assertIn('Conteo.java',texto);self.assertIn('Contar compradores',texto)
        self.assertEqual(P.ARCHIVO.stat().st_mode&0o777,0o600)

    def test_archivo_faltante_no_se_marca_terminado_por_plan(self):
        self.iniciar();self.plan();r=P.estado(P.activo())
        self.assertFalse(r['etapas'][0]['confirmada']);self.assertFalse(r['validacion_vigente'])
        r=P.ejecutar('validar_proyecto_codigo',{'modo':'java'},self.si,self.s);self.assertFalse(r['ok'])

    def test_escritura_muestra_codigo_y_lee_archivo_real(self):
        self.iniciar();self.plan();r=self.escribir('public class Conteo {}')
        self.assertTrue(r['ok']);self.assertTrue(r['verificado']);self.assertIn('public class Conteo',self.permisos[-1])
        self.assertEqual((self.work/'app'/'Conteo.java').read_text(),'public class Conteo {}')
        self.assertFalse(P.estado(P.activo())['validacion_vigente'])

    def test_no_escribe_fuera_de_proyecto_o_en_otra_etapa(self):
        self.iniciar();self.plan()
        for ruta in ['../escape.java','/tmp/escape.java','Otro.java']:
            r=self.escribir('public class Otro {}',ruta);self.assertFalse(r['ok'])
        self.assertFalse((self.work/'escape.java').exists())

    def test_cercas_y_codigo_incompleto_no_llegan_a_disco(self):
        self.iniciar();self.plan()
        for texto in ['```java\npublic class Conteo {}\n```','public class Conteo {\n...\n}']:
            self.assertFalse(self.escribir(texto)['ok'])
        self.assertFalse((self.work/'app'/'Conteo.java').exists())

    def test_editar_exige_lectura_completa_y_revision_actual(self):
        self.iniciar();self.plan();self.escribir('public class Conteo {}')
        self.assertFalse(self.escribir('public class Conteo { int total; }')['ok'])
        r=J.ejecutar_herramienta('leer_archivo',{'ruta':str(self.work/'app'/'Conteo.java')},self.si,self.s);self.assertTrue(r['ok'])
        self.assertTrue(self.escribir('public class Conteo { int total; }',str(self.work/'app'/'Conteo.java'))['ok'])
        (self.work/'app'/'Conteo.java').write_text('public class Conteo { int ajeno; }')
        self.assertFalse(self.escribir('public class Conteo { int total; }')['ok'])

    def test_error_pendiente_no_se_borra_al_escribir_una_propuesta(self):
        self.iniciar();self.plan();P.ejecutar('registrar_error_codigo',{'error':'cannot find symbol'},self.si,self.s)
        self.escribir('public class Conteo {}');self.assertIn('cannot find symbol',P.estado(P.activo())['error_pendiente'])

    @unittest.skipUnless(shutil.which('javac'),'Necesita JDK local')
    def test_compila_java_detecta_error_lo_corrige_y_no_adelanta_validacion(self):
        self.iniciar();self.plan();self.escribir('public class Conteo { int total = desconocido; }')
        r=P.ejecutar('validar_proyecto_codigo',{'modo':'java'},self.si,self.s);self.assertFalse(r['ok']);self.assertIn('cannot find symbol',P.estado(P.activo())['error_pendiente'])
        J.ejecutar_herramienta('leer_archivo',{'ruta':str(self.work/'app'/'Conteo.java')},self.si,self.s)
        self.escribir('public class Conteo { int total = 0; }')
        self.assertFalse(P.estado(P.activo())['validacion_vigente'])
        r=P.ejecutar('validar_proyecto_codigo',{'modo':'java'},self.si,self.s);self.assertTrue(r['ok'])
        estado=P.estado(P.activo());self.assertTrue(estado['validacion_vigente']);self.assertTrue(estado['etapas'][0]['confirmada']);self.assertFalse(estado['error_pendiente'])

    @unittest.skipUnless(shutil.which('javac'),'Necesita JDK local')
    def test_edicion_externa_invalida_etapa_anterior_y_compilacion(self):
        self.iniciar();self.plan();self.escribir('public class Conteo {}');P.ejecutar('validar_proyecto_codigo',{'modo':'java'},self.si,self.s)
        (self.work/'app'/'Conteo.java').write_text('public class Conteo { int nuevo; }')
        estado=P.estado(P.activo());self.assertFalse(estado['validacion_vigente']);self.assertFalse(estado['etapas'][0]['confirmada']);self.assertEqual(estado['siguiente']['numero'],1)

    def test_sintaxis_no_se_hace_pasar_por_compilacion_kotlin(self):
        self.iniciar();self.plan(['Conteo.kt']);self.escribir('class Conteo','Conteo.kt')
        r=P.ejecutar('validar_proyecto_codigo',{'modo':'sintaxis'},self.si,self.s);self.assertFalse(r['ok']);self.assertIn('no valida Kotlin',r['error'])

    def test_gradle_usa_tarea_fija_offline_y_permiso(self):
        self.iniciar();self.plan();self.escribir('public class Conteo {}');(self.work/'app'/'gradlew').write_text('#!/bin/sh\nexit 0\n')
        with patch.object(P.subprocess,'Popen') as proceso:
            proceso.return_value.wait.return_value=0
            r=P.ejecutar('validar_proyecto_codigo',{'modo':'android'},self.si,self.s)
            self.assertFalse(r['ok']);self.assertIn('APK válido',r['error']);cmd=proceso.call_args.args[0];self.assertIn('--offline',cmd);self.assertIn(':app:assembleDebug',cmd)
        with patch.object(P.subprocess,'Popen') as proceso:
            r=P.ejecutar('validar_proyecto_codigo',{'modo':'android'},lambda _:False,self.s);self.assertFalse(r['ok']);proceso.assert_not_called()

    def test_nuevo_estado_retoma_y_cerrar_no_borra_proyecto(self):
        self.iniciar();self.plan();P.comando('/codigo cerrar',{},self.si);self.assertIsNone(P.activo())
        hecho,t=P.comando('/codigo retomar Ejemplo',{},self.si);self.assertTrue(hecho);self.assertIn('Conteo.java',t)

    def test_registro_corrupto_no_se_sobrescribe(self):
        self.iniciar();P.ARCHIVO.write_text('{ roto')
        with self.assertRaises(ValueError):P.leer()
        self.assertEqual(P.ARCHIVO.read_text(),'{ roto')

    def test_generacion_cortada_no_escribe_y_no_modifica_el_plan(self):
        self.iniciar();self.plan()
        resultado=P.desarrollar('Escribe Conteo.java',self.s,self.si,lambda *_a,**_k:{'done_reason':'length','message':{'content':'{"contenido":"incompleto'}},'qwen3:8b')
        self.assertIn('No escribí',resultado);self.assertFalse((self.work/'app'/'Conteo.java').exists());self.assertFalse(P.estado(P.activo())['etapas'][0]['confirmada'])

    def test_generador_no_actua_sobre_ejemplo_ni_negacion(self):
        self.iniciar();self.plan()
        with patch.object(P,'ejecutar') as escribir:
            for pedido in ['No escribas código','Solo explica cómo se genera Conteo.java','Escribe por ejemplo Conteo.java']:
                self.assertIsNone(P.desarrollar(pedido,self.s,self.si,lambda *_:self.fail('No genera'),'modelo'))
        escribir.assert_not_called()

    def test_android_online_no_descarga_sin_autorizacion(self):
        self.iniciar();self.plan();self.escribir('public class Conteo {}');(self.work/'app'/'gradlew').write_text('#!/bin/sh\nexit 0')
        permisos=[]
        with patch.object(P.subprocess,'Popen') as proceso:
            r=P.ejecutar('validar_proyecto_codigo',{'modo':'android_online'},lambda texto:permisos.append(texto) or False,self.s)
        self.assertFalse(r['ok']);proceso.assert_not_called();self.assertIn('descargar dependencias',permisos[0])

    def test_python_pruebas_reales_detectan_fallo_y_exigen_permiso(self):
        self.iniciar();self.plan(['logica.py']);self.escribir('def doble(x): return x\n','logica.py')
        (self.work/'app'/'test_logica.py').write_text('import unittest\nfrom logica import doble\nclass Caso(unittest.TestCase):\n def test_doble(self): self.assertEqual(doble(3),6)\n')
        with patch.object(P.subprocess,'Popen') as proceso:
            self.assertFalse(P.validar(P.activo(),'tests_python',lambda _:False)['ok']);proceso.assert_not_called()
        self.assertFalse(P.validar(P.activo(),'tests_python',self.si)['ok']);self.assertIn('FAILED',P.activo()['error'])
        J.ejecutar_herramienta('leer_archivo',{'ruta':str(self.work/'app'/'logica.py')},self.si,self.s)
        self.escribir('def doble(x): return 2*x\n','logica.py')
        self.assertTrue(P.validar(P.activo(),'tests_python',self.si)['ok'])

    def test_python_cero_pruebas_no_confirma(self):
        self.iniciar();self.plan(['logica.py']);self.escribir('x=1\n','logica.py');(self.work/'app'/'test_vacio.py').write_text('x=1\n')
        self.assertFalse(P.validar(P.activo(),'tests_python',self.si)['ok'])

    def test_error_sintaxis_externa_queda_pendiente(self):
        self.iniciar();self.plan(['logica.py']);(self.work/'app'/'logica.py').write_text('def rota(:\n')
        self.assertFalse(P.ejecutar('validar_proyecto_codigo',{'modo':'sintaxis'},self.si,self.s)['ok']);self.assertIn('SyntaxError',P.activo()['error'])

    def test_sql_ejecuta_contratos_y_detecta_resultados_incorrectos(self):
        self.iniciar();self.plan(['esquema.sql']);self.escribir('CREATE TABLE datos(x); INSERT INTO datos VALUES(3);','esquema.sql')
        contrato=self.work/'app'/'pruebas_sql.json';contrato.write_text(json.dumps([{'consulta':'SELECT x FROM datos','esperado':[[6]]}]))
        self.assertFalse(P.validar(P.activo(),'tests_sql',self.si)['ok']);self.assertIn('AssertionError',P.activo()['error'])
        contrato.write_text(json.dumps([{'consulta':'SELECT x FROM datos','esperado':[[3]]}]))
        self.assertTrue(P.validar(P.activo(),'tests_sql',self.si)['ok'])

    def test_sql_no_puede_abrir_archivos_ni_extension(self):
        from validacion_codigo import comprobar_sql
        f=self.work/'ataque.sql';externo=self.work/'externo.db'
        for sql in [f"ATTACH DATABASE '{externo}' AS externo;",'PRAGMA foreign_keys=OFF;',"SELECT load_extension('/tmp/desconocida');"]:
            f.write_text(sql)
            with self.assertRaises(Exception):comprobar_sql([f])
        self.assertFalse(externo.exists())

    def test_sql_no_ignora_claves_foraneas(self):
        from validacion_codigo import comprobar_sql
        f=self.work/'integridad.sql';f.write_text('CREATE TABLE padre(id INTEGER PRIMARY KEY); CREATE TABLE hijo(id INTEGER REFERENCES padre(id)); INSERT INTO hijo VALUES(99);')
        with self.assertRaises(Exception):comprobar_sql([f])

    def test_sql_respeta_orden_del_plan(self):
        self.iniciar();self.plan(['z_esquema.sql','a_datos.sql']);self.escribir('CREATE TABLE datos(x);','z_esquema.sql');self.escribir('INSERT INTO datos VALUES(5);','a_datos.sql')
        self.assertTrue(P.validar(P.activo(),'sql',self.si)['ok'])

    def test_modificar_archivo_completado_reabre_sin_perder_plan(self):
        self.iniciar();self.plan(['logica.py']);self.escribir('x=1\n','logica.py');P.validar(P.activo(),'sintaxis',self.si)
        enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'x=2\n','explicacion':'Cambio solicitado'})}}
        respuesta=P.desarrollar('Modifica logica.py para que x sea 2',{},self.si,enviar,'modelo')
        self.assertIn('Comprobación correcta',respuesta);self.assertEqual((self.work/'app'/'logica.py').read_text(),'x=2\n');self.assertEqual(len(P.activo()['etapas']),1)

    def test_dialecto_ajeno_no_se_valida_como_sqlite(self):
        self.iniciar();self.plan(['datos.sql'])
        enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'CREATE TABLE datos(id SERIAL PRIMARY KEY);','explicacion':'PostgreSQL'})}}
        with patch.object(P,'validar',side_effect=AssertionError('No comprobar PostgreSQL en SQLite')):
            respuesta=P.desarrollar('Genera datos.sql para PostgreSQL',{},self.si,enviar,'modelo')
        self.assertIn('SQLite',respuesta);self.assertIn('SERIAL',(self.work/'app'/'datos.sql').read_text());self.assertFalse(P.estado(P.activo())['validacion_vigente']);self.assertIn('postgresql',P.activo()['error'])

    def test_codigo_identico_no_reescribe_y_comprueba_contrato_nuevo(self):
        self.iniciar();self.plan(['logica.py']);self.escribir('def resolver(x): return x\n','logica.py');P.validar(P.activo(),'sintaxis',self.si)
        (self.work/'app'/'test_logica.py').write_text('import unittest\nfrom logica import resolver\nclass Caso(unittest.TestCase):\n def test_valor(self): self.assertEqual(resolver(4),4)\n')
        enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'def resolver(x): return x\n','explicacion':'El requisito ya se cumple.'})}}
        with patch.object(P.E,'proponer_edicion',side_effect=AssertionError('No crear diff idéntico')):
            respuesta=P.desarrollar('Actualiza logica.py, resolver(4) debe devolver 4',{},self.si,enviar,'modelo')
        self.assertIn('Comprobación correcta',respuesta);self.assertTrue(P.estado(P.activo())['validacion_vigente'])

    def test_revalidar_etapa_terminada_sin_reescribir(self):
        self.iniciar();self.plan(['logica.py']);self.escribir('x=1\n','logica.py')
        self.assertTrue(P.validar(P.activo(),'sintaxis',self.si)['ok']);self.assertTrue(P.validar(P.activo(),'sintaxis',self.si)['ok'])

    def test_cambio_de_proyecto_durante_generacion_no_escribe_en_otro(self):
        self.iniciar();self.plan(['logica.py'])
        def enviar(*_a,**_k):
            P.ejecutar('iniciar_proyecto_codigo',{'nombre':'Otro','ruta':str(self.work/'otro'),'objetivo':'Otro objetivo'},self.si,{})
            return {'message':{'content':json.dumps({'contenido':'x=2\n','explicacion':'Cambio'})}}
        respuesta=P.desarrollar('Genera logica.py',self.s,self.si,enviar,'modelo')
        self.assertIn('cambió',respuesta);self.assertFalse((self.work/'app'/'logica.py').exists());self.assertFalse((self.work/'otro'/'logica.py').exists());self.assertNotIn('_codigo_proyecto_id',self.s)

    def test_contexto_grande_sigue_siendo_json_completo(self):
        self.iniciar();self.plan(['logica.py']);p=P.activo();p['objetivo']='objetivo largo '*200
        with patch.object(P,'activo',return_value=p):texto=P.contexto('retomar Python',{})
        datos=json.loads(texto.split('\n',1)[0]);self.assertEqual(datos['siguiente']['archivos'][0]['ruta'],'logica.py');self.assertLessEqual(len(datos['objetivo']),700)

    def test_sintaxis_generada_invalida_reintenta_sin_escribir_incompleto(self):
        self.iniciar();self.plan(['logica.py']);vistos=[]
        def enviar(_endpoint,payload,**_kw):
            vistos.append(payload)
            codigo='def rota(:\n' if len(vistos)==1 else 'def correcta(): return 1\n'
            return {'message':{'content':json.dumps({'contenido':codigo,'explicacion':'Función'})}}
        respuesta=P.desarrollar('Escribe logica.py',{},self.si,enviar,'modelo')
        self.assertEqual(len(vistos),2);self.assertIn('SyntaxError',vistos[1]['messages'][1]['content']);self.assertIn('Comprobación correcta',respuesta)
        self.assertEqual((self.work/'app'/'logica.py').read_text(),'def correcta(): return 1\n')

    def test_no_confunde_nombre_de_archivo_con_sufijo_de_otro(self):
        self.iniciar();self.plan(['logica.py'])
        respuesta=P.desarrollar('Genera test_logica.py solo si pertenece al plan',{},self.si,lambda *_a,**_k:self.fail('No generar un archivo diferente'),'modelo')
        self.assertIn('no pertenece al plan',respuesta);self.assertFalse((self.work/'app'/'logica.py').exists())

    def test_negacion_de_optimizacion_no_modifica(self):
        self.iniciar();self.plan(['logica.py'])
        for pedido in ['No optimices logica.py, solo explica','No refactorices logica.py','Mejora la explicación sin tocar logica.py']:
            self.assertIsNone(P.desarrollar(pedido,{},self.si,lambda *_a,**_k:self.fail('No generar'),'modelo'))

    def test_peticion_ajena_al_codigo_no_modifica_proyecto_activo(self):
        self.iniciar();self.plan(['logica.py'])
        for pedido in ['Mejora tu comunicación','Crea una receta de almuerzo','Hazme un resumen del clima','Mejora el rendimiento de Ubuntu']:
            self.assertIsNone(P.desarrollar(pedido,{},self.si,lambda *_a,**_k:self.fail('No generar código'),'modelo'))

    def test_punto_final_de_frase_no_confunde_nombre(self):
        self.iniciar();self.plan(['logica.py'])
        enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'x=1\n','explicacion':'Código solicitado'})}}
        respuesta=P.desarrollar('Genera logica.py. Debe contener x igual a 1.',{},self.si,enviar,'modelo')
        self.assertIn('Comprobación correcta',respuesta);self.assertTrue((self.work/'app'/'logica.py').exists())

    def test_timeout_conserva_error_y_archivo_original(self):
        self.iniciar();self.plan(['logica.py']);self.escribir('x=1\n','logica.py');P.ejecutar('registrar_error_codigo',{'error':'Error funcional original'},self.si,{})
        with patch.object(P.MEJORAS,'contexto',return_value=''):
            respuesta=P.desarrollar('Corrige logica.py',{},self.si,lambda *_a,**_k:(_ for _ in ()).throw(ConnectionError('tiempo agotado')),'modelo')
        self.assertIn('interrumpió',respuesta);self.assertEqual((self.work/'app'/'logica.py').read_text(),'x=1\n');self.assertIn('Error funcional original',P.activo()['error']);self.assertIn('tiempo agotado',P.activo()['error'])

    def test_generador_recibe_preferencias_del_tema(self):
        self.iniciar();self.plan(['logica.py']);payload=[]
        def enviar(_e,p,**_k):payload.append(p);return {'done_reason':'length'}
        with patch.object(P.MEJORAS,'contexto',return_value='Preferencia Python: conservar firmas.') as contexto:
            P.desarrollar('Escribe logica.py',{},self.si,enviar,'modelo')
        self.assertIn('conservar firmas',payload[0]['messages'][0]['content']);self.assertIn('logica.py',contexto.call_args.kwargs['pedido'])
    def test_transporte_reducido_preserva_json_en_vez_de_cortar_rutas(self):
        texto=json.dumps({'nombre':'Proyecto','ruta':'/ruta/'+'x'*600,'objetivo':'y'*1600,'siguiente':{'archivos':['archivo.py']},'sin_plan':False})+'\nGuía'
        compacto=P.acotar_contexto(texto,500);datos=json.loads(compacto.split('\n',1)[0])
        self.assertEqual(datos['nombre'],'Proyecto');self.assertTrue(datos['resumen_reducido']);self.assertLessEqual(len(compacto),500)

    def test_requisitos_no_se_registran_si_escritura_no_autorizada(self):
        self.iniciar();self.plan(['logica.py']);enviar=lambda *_a,**_k:{'message':{'content':json.dumps({'contenido':'x=2\n','explicacion':'Cambio'})}}
        P.desarrollar('Genera logica.py',{},lambda _:False,enviar,'modelo')
        self.assertNotIn('requisitos',P.activo());self.assertFalse((self.work/'app'/'logica.py').exists())


if __name__=='__main__':unittest.main()
