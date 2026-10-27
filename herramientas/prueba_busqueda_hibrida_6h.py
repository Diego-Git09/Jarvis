"""Recuperación: archivo nombrado, vectores compatibles, controles y cupos."""
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        for k,v in [('RAIZ',self.base/'indice'),('CONFIG',self.base/'limites.json'),('RECURSOS',self.base/'recursos.json')]:patch.object(T,k,v).start()

    def tanda(self,nombre='fuente_a.txt'):
        a=self.base/nombre;a.write_text('DATO_A. Cantidad 713.')
        b=self.base/'fuente_b.txt';b.write_text('DATO_B. Explicación de Android y sus pantallas.')
        d=T.indexar(T.crear([a,b])['id'],True,embedding=lambda t,m:[0.,1.] if 'DATO_A' in t else [1.,0.])
        return d,a,b

    def buscar(self,d,p,**kw):return T.buscar(d['id'],p,embedding=lambda *_:[1.,0.],**kw)

    def test_archivo_nombrado_precede_a_otro_tema_mas_parecido(self):
        d,_,_=self.tanda();r=self.buscar(d,'La respuesta debe salir de fuente_a.txt, aunque otro documento hable de Android.')
        self.assertIn('DATO_A',r['trozos'][0]['texto'])

    def test_nombre_con_espacios_y_tildes_se_conserva(self):
        d,_,_=self.tanda('Resumen Ñ final.txt');r=self.buscar(d,'Consulta "Resumen Ñ final.txt" para el caso Android.')
        self.assertTrue(r['trozos'][0]['referencia'].startswith('Resumen Ñ final.txt'))

    def test_ruta_absoluta_exacta_es_un_dato_de_busqueda(self):
        d,a,_=self.tanda();r=self.buscar(d,f'Consulta "{a}" sobre Android.')
        self.assertIn('DATO_A',r['trozos'][0]['texto'])

    def test_ruta_distinta_con_igual_basename_no_da_prioridad(self):
        d,_,_=self.tanda();r=self.buscar(d,'Consulta /ruta/ajena/fuente_a.txt para Android.')
        self.assertIn('DATO_B',r['trozos'][0]['texto'])

    def test_negativa_no_promueve_el_archivo(self):
        d,_,_=self.tanda();r=self.buscar(d,'No uses fuente_a.txt; necesito Android.')
        self.assertIn('DATO_B',r['trozos'][0]['texto'])

    def test_ultima_mencion_negada_prevalece_para_prioridad(self):
        d,_,_=self.tanda();r=self.buscar(d,'Revisa fuente_a.txt, pero finalmente no uses fuente_a.txt; necesito Android.')
        self.assertIn('DATO_B',r['trozos'][0]['texto'])

    def test_negativa_a_otro_archivo_no_anula_mencion_positiva(self):
        d,_,_=self.tanda();r=self.buscar(d,'No uses fuente_b.txt, consulta fuente_a.txt para Android.')
        self.assertIn('DATO_A',r['trozos'][0]['texto'])

    def test_nombre_parcial_no_se_iguala_a_otro(self):
        d,_,_=self.tanda();r=self.buscar(d,'Consulta prefijo_fuente_a.txt para Android.')
        self.assertIn('DATO_B',r['trozos'][0]['texto'])

    def test_exclusion_explicita_retira_la_fuente_del_contexto(self):
        d,_,_=self.tanda();r=self.buscar(d,'No uses fuente_a.txt; necesito Android.')
        self.assertFalse(any('DATO_A' in x['texto'] for x in r['trozos']));self.assertIn('excluida',r['aviso'])

    def test_negativa_coordinada_con_ni_retira_ambas(self):
        d,_,_=self.tanda();r=self.buscar(d,'No uses fuente_a.txt ni fuente_b.txt; necesito Android.')
        self.assertEqual(r['trozos'],[])

    def test_negativa_coordinada_con_y_retira_ambas(self):
        d,_,_=self.tanda();r=self.buscar(d,'No uses fuente_b.txt y fuente_a.txt; necesito Android.')
        self.assertEqual(r['trozos'],[])

    def test_tampoco_mantiene_exclusion_despues_de_coma(self):
        d,_,_=self.tanda();r=self.buscar(d,'No uses fuente_a.txt, tampoco fuente_b.txt; necesito Android.')
        self.assertEqual(r['trozos'],[])

    def test_orden_citada_como_ejemplo_no_excluye_una_fuente(self):
        d,_,_=self.tanda();r=self.buscar(d,'El ejemplo dice "no uses fuente_a.txt"; explícame Android.')
        self.assertTrue(any('DATO_A' in x['texto'] for x in r['trozos']))

    def test_nombres_iguales_conservan_ambas_referencias_autorizadas(self):
        uno=self.base/'uno';dos=self.base/'dos';uno.mkdir();dos.mkdir()
        a=uno/'igual.txt';b=dos/'igual.txt';a.write_text('DATO_DUP_A');b.write_text('DATO_DUP_B')
        d=T.indexar(T.crear([a,b])['id'],True,embedding=lambda *_:[1.,0.]);r=self.buscar(d,'Consulta igual.txt')
        self.assertTrue(any('DATO_DUP_A' in x['texto'] for x in r['trozos']));self.assertTrue(any('DATO_DUP_B' in x['texto'] for x in r['trozos']))

    def test_fuente_cambiada_no_vuelve_por_prioridad(self):
        d,a,_=self.tanda();s=a.stat();a.write_text('DATO_C. Cantidad 999.');os.utime(a,ns=(s.st_atime_ns,s.st_mtime_ns))
        r=self.buscar(d,'Consulta fuente_a.txt para Android.')
        self.assertFalse(any('DATO_A' in x['texto'] or 'DATO_C' in x['texto'] for x in r['trozos']))

    def test_revocacion_de_ruta_se_aplica_antes_de_fusionar(self):
        d,a,_=self.tanda();real=T.L._resolver
        def resolver(p):
            if str(p)==str(a):raise T.L.FueraDeAlcance('Acceso ficticio revocado')
            return real(p)
        with patch.object(T.L,'_resolver',side_effect=resolver):r=self.buscar(d,'Consulta fuente_a.txt para Android.')
        self.assertFalse(any('DATO_A' in x['texto'] for x in r['trozos']))

    def test_presupuesto_no_aumenta_por_mencionar_un_archivo(self):
        d,_,_=self.tanda();r=self.buscar(d,'Consulta fuente_a.txt',presupuesto=10)
        self.assertEqual(r['trozos'],[]);self.assertLessEqual(r['caracteres'],10)

    def test_documento_y_consulta_tienen_preparaciones_distintas(self):
        a=self.base/'dato.txt';a.write_text('DATO_DOCUMENTO')
        llamadas=[]
        def vector(t,m):llamadas.append(t);return [1.,0.]
        d=T.indexar(T.crear([a])['id'],True,embedding=vector)
        T.buscar(d['id'],'PREGUNTA',embedding=vector)
        self.assertTrue(llamadas[0].startswith('search_document: '));self.assertEqual(llamadas[-1],'search_query: PREGUNTA')

    def test_cambio_de_preparacion_invalida_cache_semantica(self):
        d,_,_=self.tanda();llamadas=[]
        with patch.object(T,'EMBEDDING_VERSION',99,create=True):
            nuevo=T.indexar(d['id'],True,embedding=lambda t,m:llamadas.append(t) or [1.,0.])
        self.assertTrue(llamadas);self.assertNotEqual(d['archivos'][0]['clave'],nuevo['archivos'][0]['clave'])

    def test_vector_antiguo_no_se_compara_con_nueva_preparacion(self):
        d,_,_=self.tanda();d.pop('version_embeddings',None);T._atomic(T._ruta(d['id']),d)
        with patch.object(T,'_vector',side_effect=AssertionError('No consultar un vector incompatible')):
            r=T.buscar(d['id'],'DATO_A')
        self.assertTrue(r['trozos']);self.assertIn('/indexar',r['aviso'])

    def test_fusion_incluye_fts_y_vectores(self):
        d,_,_=self.tanda();r=self.buscar(d,'Android')
        self.assertIn('FTS5',r['metodo']);self.assertIn('vector',r['metodo']);self.assertIn('RRF',r['metodo'])

    def test_vector_no_finito_cacheado_no_produce_puntuacion_nan(self):
        d,_,_=self.tanda()
        with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:db.execute('UPDATE trozos SET vector=?',(json.dumps([float('nan'),0.]),));db.commit()
        r=self.buscar(d,'DATO_A')
        self.assertTrue(all(math.isfinite(x['score']) for x in r['trozos']));self.assertIn('vector',r['aviso'].casefold())

    def test_booleanos_y_cadenas_no_se_aceptan_como_coordenadas(self):
        d,_,_=self.tanda()
        for vector in ([True,0.],[1.,'dato']):
            with self.subTest(vector=vector):
                with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:db.execute('UPDATE trozos SET vector=?',(json.dumps(vector),));db.commit()
                r=self.buscar(d,'DATO_A');self.assertIn('vector',r['aviso'].casefold());self.assertTrue(all(math.isfinite(x['score']) for x in r['trozos']))

    def test_vector_de_magnitud_extrema_conserva_coseno_y_puntuaciones_finitas(self):
        import recuperacion_hibrida as H
        for factor in (1e-308,1.,1e200):
            with self.subTest(factor=factor):
                self.assertAlmostEqual(H._similitud_cache(json.dumps([factor,factor]),[1.,0.]),math.sqrt(.5))

    def test_archivo_nombrado_con_vector_ausente_no_se_pierde_entre_muchos_candidatos(self):
        a=self.base/'origen.txt';b=self.base/'preferido.txt';a.write_text('FOCO_REPETIDO. Inventario local.');b.write_bytes(a.read_bytes());paths=[a,b]
        for i in range(80):p=self.base/f'ruido{i:03d}.txt';p.write_text(f'RUIDO_{i}. Android y sus pantallas.');paths.append(p)
        d=T.indexar(T.crear(paths)['id'],True,embedding=lambda *_:[1.,0.])
        with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:db.execute('UPDATE trozos SET vector=NULL WHERE clave=?',(d['archivos'][0]['clave'],));db.commit()
        r=self.buscar(d,'Consulta preferido.txt sobre Android.')
        self.assertTrue(r['trozos'][0]['referencia'].startswith('preferido.txt'));self.assertIn('FOCO_REPETIDO',r['trozos'][0]['texto'])

    def test_candidatos_de_fusion_se_mantienen_acotados(self):
        T.configurar(dict(T.DEFAULT,trozo=400));a=self.base/'muchos.txt';a.write_text('\n'.join('DATO_FUSION '+str(i)+' '+('texto '*60) for i in range(150)))
        d=T.indexar(T.crear([a])['id'],True,embedding=lambda *_:[1.,0.]);r=self.buscar(d,'DATO_FUSION',presupuesto=6000)
        e=r['estadisticas_busqueda'];self.assertLessEqual(e['candidatos_semanticos'],80);self.assertLessEqual(e['candidatos_lexicos'],80);self.assertLessEqual(e['candidatos_fusion'],160)
        self.assertLessEqual(len(r['trozos']),8)

    def test_fallo_embedding_conserva_texto_sin_repetir_fallo_por_trozo(self):
        a=self.base/'primero.txt';b=self.base/'segundo.txt';a.write_text('DATO_A '+('detalle '*500));b.write_text('DATO_B '+('otro '*500));llamadas=[]
        def caido(*args):llamadas.append(args);raise ConnectionError('Modelo ficticio no disponible')
        d=T.indexar(T.crear([a,b])['id'],True,embedding=caido)
        self.assertEqual(len(llamadas),1);self.assertTrue(all(x.get('caracteres_indexados',0)>0 for x in d['archivos']))
        self.assertTrue(all(x['estado']=='parcial' and 'vector' in x['aviso'].casefold() for x in d['archivos']))
        with patch.object(T,'_vector',side_effect=AssertionError('No repetir consulta al modelo caído')):
            r=T.buscar(d['id'],'DATO_B',presupuesto=6000)
        self.assertTrue(any('DATO_B' in x['texto'] for x in r['trozos']))

    def test_reindexar_completa_vectores_pendientes_sin_duplicar_textos(self):
        p=self.base/'reanudar.txt';p.write_text('DATO_REANUDAR '+('detalle '*500))
        d=T.indexar(T.crear([p])['id'],True,embedding=lambda *_:(_ for _ in ()).throw(ConnectionError('Caído ficticio')))
        with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:antes=db.execute('SELECT count(*) FROM trozos').fetchone()[0]
        self.assertGreater(antes,0);llamadas=[]
        final=T.indexar(d['id'],True,embedding=lambda t,m:llamadas.append(t) or [1.,0.])
        with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:
            despues=db.execute('SELECT count(*) FROM trozos').fetchone()[0];sin_vector=db.execute('SELECT count(*) FROM trozos WHERE vector IS NULL').fetchone()[0]
        self.assertEqual(antes,despues);self.assertEqual(sin_vector,0);self.assertTrue(llamadas)
        self.assertEqual(final['estado'],'indexado');self.assertTrue(final['modelo_embeddings'])

    def test_fallo_embedding_no_finge_lectura_incompleta_del_texto_plano(self):
        p=self.base/'plano.txt';p.write_text('DATO_PLANO disponible completo.')
        d=T.indexar(T.crear([p])['id'],True,embedding=lambda *_:(_ for _ in ()).throw(ValueError('Vector ficticio inválido')))
        self.assertTrue(d['archivos'][0]['cobertura']['lectura_completa']);self.assertFalse(d['archivos'][0]['embeddings_completos'])

    def test_embedding_tiene_espera_menor_que_la_inferencia_larga(self):
        import cliente_ollama as O
        with patch.object(O,'solicitar',return_value={'embeddings':[[1.,0.]]}) as llamar:T._vector('Dato ficticio','nomic-embed-text:latest')
        self.assertLessEqual(llamar.call_args.kwargs['timeout'],5)


if __name__=='__main__':unittest.main()
