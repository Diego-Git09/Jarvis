"""Formatos, referencias y controles con fuentes sintéticas y temporales."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import tarfile
import threading
import unittest
from unittest.mock import patch
import zipfile
import struct

import tandas_documentales as T
import lectores_adjuntos as R
from evaluar_adjuntos_6h import CORPUS,preparar

CASOS=json.loads(CORPUS.read_text())

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.addCleanup(patch.stopall);patch.object(T,'RAIZ',self.base/'indice').start();patch.object(T,'CONFIG',self.base/'limites.json').start();patch.object(T,'RECURSOS',self.base/'recursos.json').start()
    def archivo(self,n,t):p=self.base/n;p.write_text(t);return p
    def indexar(self,p,**kw):return T.indexar(T.crear([p])['id'],False,**kw)
    def caso(self,c):
        p,c=preparar(self.base,c);d=self.indexar(p);r=T.buscar(d['id'],'NOMBRE' if c['extension']=='env' else c['clave'])
        if c['extension']=='env':
            self.assertTrue(any('[REDACTADO]' in x['texto'] and p.name in x['referencia'] for x in r['trozos']));self.assertFalse(any(c['clave'] in x['texto'] or 'secreto-ficticio' in x['texto'] for x in r['trozos']))
        else:self.assertTrue(any(c['clave'] in x['texto'] and c['dato'] in x['texto'] and c['referencia'] in x['referencia'] and p.name in x['referencia'] for x in r['trozos']))
    def test_huella_corpus(self):self.assertEqual(hashlib.sha256(CORPUS.read_bytes()).hexdigest(),CORPUS.with_suffix('.sha256').read_text().strip())
    def test_formatos_sin_tanda(self):
        ok,t=T.comando('/adjuntos formatos',{});self.assertTrue(ok);self.assertIn('.xlsm',t);self.assertIn('SOLO METADATOS',t)
    def test_cancelacion_reanuda(self):
        p=self.archivo('larga.txt','dato confirmado\n'*4000);d=T.crear([p]);e=threading.Event();detalles=[]
        def callback(x):
            detalles.append(x)
            if x['unidades']>=2:e.set()
        primero=T.indexar(d['id'],False,cancelar=e,detalle_progreso=callback)
        self.assertTrue(primero.get('cancelada'));self.assertEqual(primero['estado'],'parcial');self.assertTrue(T.buscar(d['id'],'confirmado')['trozos'])
        segundo=T.indexar(d['id'],False);self.assertEqual(segundo['archivos'][0]['estado'],'indexado');self.assertIn('eta_segundos',detalles[0])
    def test_limite_tiempo_no_bloquea_otra_fuente(self):
        a=self.archivo('lento.txt','uno');b=self.archivo('bien.txt','CLAVE_BIEN');real=T._unidades
        def lectura(i,l,control=None):
            if i['nombre']=='lento.txt':raise TimeoutError('plazo sintético')
            yield from real(i,l,control)
        with patch.object(T,'_extraer_unidades',side_effect=lambda i,l,c,r:lectura(i,l,c)):d=T.indexar(T.crear([a,b])['id'],False)
        self.assertEqual(d['archivos'][0]['estado'],'ilegible');self.assertEqual(d['archivos'][1]['estado'],'indexado')
    def test_html_ignora_scripts_estilos(self):
        d=self.indexar(self.archivo('web.html','<script>NOEJECUTAR</script><style>NOESTILO</style><p>DATO_HTML</p>'));r=T.buscar(d['id'],'DATO_HTML');t=' '.join(x['texto'] for x in r['trozos']);self.assertIn('DATO_HTML',t);self.assertNotIn('NOEJECUTAR',t);self.assertNotIn('NOESTILO',t)
    def test_env_redacta_todos_valores(self):
        d=self.indexar(self.archivo('.env','NORMAL=dato privado\nPASSWORD=secreto\n'));t=' '.join(x['texto'] for x in T.buscar(d['id'],'NORMAL')['trozos']);self.assertIn('NORMAL=[REDACTADO]',t);self.assertNotIn('dato privado',t)
    def test_secreto_linea_mayor_buffer(self):
        d=self.indexar(self.archivo('grande.txt','api_key='+('s'*80000)+'\nDATO_FINAL\n'));t=' '.join(x['texto'] for x in T.buscar(d['id'],'DATO_FINAL',limite=20,presupuesto=30000)['trozos']);self.assertIn('DATO_FINAL',t);self.assertNotIn('s'*25,t)
        with T._conexion() as db:self.assertFalse(any('s'*25 in t[0] for t in db.execute('SELECT texto FROM trozos')))
    def test_clave_privada_cruza_buffer(self):
        d=self.indexar(self.archivo('clave.txt','-----BEGIN PRIVATE KEY-----\n'+('S'*80000)+'\n-----END PRIVATE KEY-----\nDATO_POSTERIOR'));r=T.buscar(d['id'],'DATO_POSTERIOR');self.assertTrue(any('DATO_POSTERIOR' in x['texto'] for x in r['trozos']))
        with T._conexion() as db:self.assertFalse(any('S'*25 in t[0] for t in db.execute('SELECT texto FROM trozos')))
    def test_tar_rechaza_enlace(self):
        p=self.base/'enlace.tar'
        with tarfile.open(p,'w') as z:
            n=tarfile.TarInfo('enlace');n.type=tarfile.SYMTYPE;n.linkname='../afuera';z.addfile(n)
        with self.assertRaises(ValueError):T.crear([p])
    def test_tar_rechaza_traversal(self):
        p=self.base/'traversal.tar'
        with tarfile.open(p,'w') as z:
            n=tarfile.TarInfo('../fuera.txt');n.size=4;z.addfile(n,io.BytesIO(b'dato'))
        with self.assertRaises(ValueError):T.crear([p])
    def test_tgz_rechaza_bomba(self):
        p=self.base/'bomba.tgz'
        with tarfile.open(p,'w:gz') as z:
            n=tarfile.TarInfo('grande.txt');n.size=1000000;z.addfile(n,io.BytesIO(b'a'*n.size))
        with self.assertRaises(ValueError):T.crear([p])
    def test_sqlite_solo_lectura_original_intacto(self):
        c=next(c for c in CASOS if c['extension']=='db');p,c=preparar(self.base,c);antes=hashlib.sha256(p.read_bytes()).hexdigest();d=self.indexar(p);self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),antes);self.assertIn('tabla inventario',T.buscar(d['id'],c['clave'])['trozos'][0]['referencia'])
    def test_binario_metadata_hash(self):
        p=self.base/'binario.exe';p.write_bytes(b'\0\1\2\3MUESTRA');d=self.indexar(p);a=d['archivos'][0];self.assertEqual(a['soporte'],'NO SOPORTADO');self.assertEqual(len(a['hash']),64);self.assertEqual(a['estado'],'ilegible')
    def test_utf16_sin_bom(self):
        p=self.base/'sinbom.txt';p.write_bytes('DATO_UTF16 Mañana'.encode('utf-16-le'));d=self.indexar(p);self.assertTrue(any('DATO_UTF16' in x['texto'] for x in T.buscar(d['id'],'DATO_UTF16')['trozos']))
    def test_extension_falsa_detecta_sqlite(self):
        c=next(c for c in CASOS if c['extension']=='db');p,c=preparar(self.base,c);q=p.with_suffix('.txt');p.rename(q);d=self.indexar(q);self.assertEqual(d['archivos'][0]['tipo_real'],'.sqlite');self.assertIn('distinta',d['archivos'][0]['aviso'])
    def test_cobertura_no_inventa_porcentaje_modelo(self):
        d=self.indexar(self.archivo('real.txt','dato de la fuente'));a=d['archivos'][0];self.assertIsNone(a['cobertura']['porcentaje_modelo']);self.assertTrue(a['cobertura']['lectura_completa'])
    def test_repositorio_respeta_ignorados(self):
        p=self.base/'repo';p.mkdir();(p/'.gitignore').write_text('*.secret\ntmp/\n');(p/'bueno.py').write_text('contenido');(p/'omitido.secret').write_text('noindexar');(p/'tmp').mkdir();(p/'tmp'/'no.txt').write_text('no');(p/'build').mkdir();(p/'build'/'no.txt').write_text('no');d=T.crear([p]);self.assertEqual({Path(a['ruta']).name for a in d['archivos']},{'.gitignore','bueno.py'})
    def test_archivo_200mb_rechazado_sin_cargar(self):
        p=self.base/'enorme.csv'
        with p.open('wb') as f:f.truncate(201*1024**2)
        with self.assertRaisesRegex(ValueError,'20 MB'):T.crear([p])
    def test_cancelar_sin_indexacion(self):
        d=T.crear([self.archivo('dato.txt','contenido')]);ok,t=T.comando('/adjuntos cancelar',{'_tanda_documentos':d['id']});self.assertTrue(ok);self.assertIn('No hay',t)
    def test_corrupto_no_bloquea_tanda(self):
        p=self.base/'mal.docx';p.write_bytes(b'noeszip');q=self.archivo('bien.md','DATO_BUENO');d=T.indexar(T.crear([p,q])['id'],False);self.assertEqual(d['archivos'][1]['estado'],'indexado')
    def test_estadisticas_csv_y_rango_sin_indexar(self):
        p=self.archivo('numeros.csv','producto,cantidad\nA,7\nB,9\n');r=R.analizar(p,desde=2,hasta=2)
        self.assertTrue(r['completo']);self.assertFalse(r['indexado']);self.assertEqual(r['lineas'],3);self.assertEqual(r['sumas_numericas_fisicas']['2'],'16');self.assertEqual(r['muestras'][0]['linea'],2)
    def test_analizar_csv_redacta_columnas_secretas(self):
        r=R.analizar(self.archivo('privado.csv','nombre,api_key\nDiego,987654321\n'))
        self.assertNotIn('987654321',json.dumps(r));self.assertNotIn('2',r['sumas_numericas_fisicas'])
    def test_jsonl_no_suma_secreto_numerico(self):
        r=R.analizar(self.archivo('privado.jsonl','{"cantidad":2,"token":987654321}\n'))
        self.assertNotIn('token',r['sumas_numericas_fisicas']);self.assertEqual(r['sumas_numericas_fisicas']['cantidad'],'2');self.assertNotIn('987654321',json.dumps(r))
    def test_analizar_texto_busqueda_literal(self):
        p=self.archivo('log.log','primera\nDATO_BUSCADO\ntercera\n');r=R.analizar(p,buscar='DATO_BUSCADO');self.assertEqual(r['coincidencias'],1);self.assertEqual(r['muestras'][0]['linea'],2)
    def test_analizar_linea_enorme_no_la_copia(self):
        p=self.archivo('larga.json','{"dato":"'+'x'*150000+'"}');r=R.analizar(p);self.assertEqual(r['lineas'],1);self.assertEqual(r['lineas_extensas_omitidas'],1);self.assertLess(len(json.dumps(r)),2000)
    def test_analizar_comando_sin_tanda(self):
        p=self.archivo('cantidad.txt','uno\ndos\n');estado={};ok,t=T.comando('/adjuntos analizar "'+str(p)+'"',estado);self.assertTrue(ok);self.assertEqual(json.loads(t)['lineas'],2);self.assertNotIn('_tanda_documentos',estado)
    def test_excel_estadisticas_formulas_omitidas(self):
        import libros_jarvis as X
        p=self.base/'formulas.xlsx'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns:r="urn:r"><sheets><sheet name="Ventas" r:id="r1"/></sheets></workbook>');z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>');z.writestr('xl/worksheets/sheet1.xml','<worksheet><sheetData><row r="1"><c r="A1"><v>7</v></c></row><row r="2"><c r="A2"><f>1000</f><v>1000</v></c></row><row r="3"><c r="A3"><v>7</v></c></row></sheetData></worksheet>')
        r=X.estadisticas(p);self.assertEqual(r['filas'],3);self.assertTrue(r['completo']);self.assertEqual(r['hojas'][0]['sumas_numericas']['A'],'14');self.assertEqual(r['hojas'][0]['formulas_omitidas'],1)
    def test_gitignore_anidado_no_afecta_otro_directorio(self):
        p=self.base/'repo';p.mkdir();a=p/'uno';b=p/'dos';a.mkdir();b.mkdir();(a/'.gitignore').write_text('*.privado\n');(a/'no.privado').write_text('no');(b/'si.privado').write_text('si');d=T.crear([p]);self.assertIn('si.privado',{x['nombre'] for x in d['archivos']});self.assertNotIn('no.privado',{x['nombre'] for x in d['archivos']})
    def test_gitignore_anclado_a_raiz(self):
        p=self.base/'repo';p.mkdir();(p/'.gitignore').write_text('/solo.txt\n');(p/'solo.txt').write_text('no');a=p/'sub';a.mkdir();(a/'solo.txt').write_text('si');d=T.crear([p]);self.assertEqual(sum(x['nombre']=='solo.txt' for x in d['archivos']),1)
    def test_repo_omite_compilados(self):
        p=self.base/'repo';p.mkdir();(p/'dato.py').write_text('codigo');(p/'binario.class').write_bytes(b'cafebabe');self.assertEqual(len(T.crear([p])['archivos']),1)
    def test_excel_columna_secreta_no_se_muestra_ni_suma(self):
        import libros_jarvis as X
        p=self.base/'claves.xlsx'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns:r="urn:r"><sheets><sheet name="Datos" r:id="r1"/></sheets></workbook>');z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>');z.writestr('xl/worksheets/sheet1.xml','<worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>api_key</t></is></c></row><row r="2"><c r="A2"><v>987654321</v></c></row></sheetData></worksheet>')
        r=X.estadisticas(p);self.assertNotIn('987654321',json.dumps(r));self.assertNotIn('A',r['hojas'][0]['sumas_numericas']);self.assertIn('[REDACTADO]',X.rango(p,'Datos','A1:A2'))
    def test_recursos_cambio_solo_con_permiso(self):
        antes=T.recursos();ok,t=T.comando('/adjuntos recursos mb_buffer=1',{},lambda _:False);self.assertEqual(T.recursos(),antes)
        ok,t=T.comando('/adjuntos recursos mb_buffer=1',{},lambda _:True);self.assertEqual(T.recursos()['mb_buffer'],1)
    def test_recursos_no_campo_desconocido(self):
        with self.assertRaises(ValueError):T.comando('/adjuntos recursos terminal=1',{},lambda _:True)
    def test_word_unidad_excesiva_continua_otro_archivo(self):
        p=self.base/'enorme.docx'
        with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<document><p>'+'x'*1100000+'</p></document>')
        T.configurar_recursos(dict(T.RECURSOS_DEFAULT,mb_buffer=1));q=self.archivo('siguiente.txt','DATO_SIGUIENTE');d=T.indexar(T.crear([p,q])['id'],False);self.assertIn('buffer',d['archivos'][0]['aviso']);self.assertEqual(d['archivos'][1]['estado'],'indexado')
    def test_epub_no_indexa_scripts(self):
        p=self.base/'seguro.epub'
        with zipfile.ZipFile(p,'w') as z:z.writestr('c.xhtml','<html><body><script>CONTENIDO_SCRIPT</script><p>DATO_LIBRO</p></body></html>')
        d=self.indexar(p);t=' '.join(x['texto'] for x in T.buscar(d['id'],'DATO_LIBRO')['trozos']);self.assertIn('DATO_LIBRO',t);self.assertNotIn('CONTENIDO_SCRIPT',t)
    def test_cp1252_euro_literal(self):
        p=self.base/'euro.txt';p.write_bytes('PRECIO_EURO 7 € mañana'.encode('cp1252'));d=self.indexar(p);self.assertEqual(d['archivos'][0]['codificacion'],'cp1252');self.assertIn('7 € mañana',T.buscar(d['id'],'PRECIO_EURO')['trozos'][0]['texto'])
    def test_latin1_no_sustituye_cadena_por_utf8(self):
        p=self.base/'latin.txt';p.write_bytes('DATO_LATIN áé ñ '.encode('latin-1')+b'\x81');d=self.indexar(p);self.assertEqual(d['archivos'][0]['codificacion'],'latin-1');self.assertIn('áé ñ',T.buscar(d['id'],'DATO_LATIN')['trozos'][0]['texto'])
    def test_sqlite_redacta_secretos_en_columnas_y_defaults(self):
        import sqlite3
        p=self.base/'privado.sqlite'
        with sqlite3.connect(p) as db:db.execute("CREATE TABLE datos(nombre TEXT, api_key TEXT DEFAULT 'clave-default-ficticia')");db.execute("INSERT INTO datos VALUES('CLAVE_PUBLICA','valor-privado-ficticio')")
        d=self.indexar(p);t=' '.join(x['texto'] for x in T.buscar(d['id'],'CLAVE_PUBLICA')['trozos']);self.assertIn('CLAVE_PUBLICA',t);self.assertIn('[REDACTADO]',t);self.assertNotIn('valor-privado-ficticio',t);self.assertNotIn('clave-default-ficticia',t)
    def test_texto_natural_con_comilla_incompleta_no_rompe_comandos(self):
        ok,t=T.comando('explicame el codigo que empieza con "print',{});self.assertFalse(ok)
    def test_control_cancelacion_se_limpia_tras_error_de_disco(self):
        d=T.crear([self.archivo('limpio.txt','dato')])
        with patch.object(T,'_atomic',side_effect=OSError('disco sintético')):
            with self.assertRaises(OSError):T.indexar(d['id'],False)
        self.assertFalse(T.cancelar_indexacion(d['id']))
    def test_indice_anterior_no_omite_protecciones_actuales(self):
        d=self.indexar(self.archivo('viejo.txt','DATO_VIEJO'));d['lector_version']=4;T._atomic(T._ruta(d['id']),d);r=T.buscar(d['id'],'DATO_VIEJO');self.assertEqual(r['trozos'],[]);self.assertIn('/indexar',r['aviso']);self.assertTrue(Path(d['archivos'][0]['ruta']).exists())
    def test_fuente_vieja_no_se_recupera_en_tanda_mixta(self):
        p=self.archivo('uno.txt','DATO_UNO');q=self.archivo('dos.txt','DATO_DOS');d=T.indexar(T.crear([p,q])['id'],False);d['archivos'][1]['lector_version']=4;T._atomic(T._ruta(d['id']),d);r=T.buscar(d['id'],'DATO_DOS');self.assertFalse(any('DATO_DOS' in x['texto'] for x in r['trozos']));self.assertIn('/indexar',r['aviso'])
    def test_fts_y_escaneo_misma_cita(self):
        p=self.archivo('fts.txt','ruido\n'*3000+'OBJETIVO_UNICO dato\n');d=self.indexar(p)
        a=T.buscar(d['id'],'OBJETIVO_UNICO',usar_fts=False);b=T.buscar(d['id'],'OBJETIVO_UNICO');self.assertEqual(a['trozos'][0]['referencia'],b['trozos'][0]['referencia']);self.assertIn('FTS5',b['metodo']);self.assertEqual(a['total_trozos'],b['total_trozos'])
    def test_cobertura_sqlite_no_promete_todas_las_filas(self):
        c=next(c for c in CASOS if c['extension']=='db');p,c=preparar(self.base,c);d=self.indexar(p);a=d['archivos'][0];self.assertFalse(a['cobertura']['lectura_completa']);self.assertIsNone(a['cobertura']['porcentaje_lectura'])
    def test_cancelacion_se_limpia_al_reanudar(self):
        p=self.archivo('retomar.txt','dato\n'*2000);d=T.crear([p]);e=threading.Event();e.set();self.assertTrue(T.indexar(d['id'],False,cancelar=e).get('cancelada'));self.assertNotIn('cancelada',T.indexar(d['id'],False))
    def test_indice_csv_redacta_columna_secreta_numerica(self):
        d=self.indexar(self.archivo('secretos.csv','nombre,api_key\nPUBLICO,987654321\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertIn('PUBLICO',contenido);self.assertIn('[REDACTADO]',contenido);self.assertNotIn('987654321',contenido)
    def test_indice_tsv_secreto_despues_de_varios_bloques(self):
        d=self.indexar(self.archivo('secretos.tsv','nombre\tpassword\n'+('PUBLICO\tsecreto ficticio\n'*2000)))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertIn('PUBLICO',contenido);self.assertNotIn('secreto ficticio',contenido)
    def test_indice_csv_multilinea_respeta_columna_sensible(self):
        d=self.indexar(self.archivo('multi.csv','nombre,token\n"dato\npublico","secreto\nmultilinea"\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertIn('publico',contenido);self.assertNotIn('secreto',contenido);self.assertNotIn('multilinea',contenido)
    def test_indice_jsonl_redacta_objetos_y_cadenas_completas(self):
        d=self.indexar(self.archivo('secretos.jsonl',json.dumps({'publico':'DATO_PUBLICO','api_key':'dos palabras ficticias','objeto':{'credentials':{'client':'valor ficticio'}}})+'\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertIn('DATO_PUBLICO',contenido);self.assertNotIn('palabras ficticias',contenido);self.assertNotIn('valor ficticio',contenido)
    def test_analizar_jsonl_redacta_objetos_y_cadenas_completas(self):
        r=R.analizar(self.archivo('muestra.jsonl',json.dumps({'publico':'DATO_PUBLICO','api_key':'dos palabras ficticias','objeto':{'credentials':{'client':'valor ficticio'}}})+'\n'))
        contenido=json.dumps(r);self.assertIn('DATO_PUBLICO',contenido);self.assertNotIn('palabras ficticias',contenido);self.assertNotIn('valor ficticio',contenido)
    def test_analizar_csv_multilinea_no_filtra_continuacion_secreta(self):
        r=R.analizar(self.archivo('muestra.csv','nombre,token\nPUBLICO,"secreto\n987654321\ncontinuacionprivada"\n'))
        contenido=json.dumps(r);self.assertNotIn('secreto',contenido);self.assertNotIn('continuacionprivada',contenido);self.assertNotIn('987654321',contenido);self.assertEqual(r['soporte'],'PARCIAL')
    def test_registro_tabular_excesivo_se_omite_sin_filtrar(self):
        d=self.indexar(self.archivo('registro.csv','nombre,token\nPUBLICO,"'+('CLAVE_FICTICIA '*10000)+'"\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertNotIn('CLAVE_FICTICIA',contenido);self.assertIn('registro',d['archivos'][0]['aviso'].casefold())
    def test_csv_clave_privada_entre_registros(self):
        d=self.indexar(self.archivo('privada.csv','etiqueta,valor\n-----BEGIN PRIVATE KEY-----\nCLAVE_FICTICIA\n-----END PRIVATE KEY-----\nDATO_PUBLICO,3\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertNotIn('CLAVE_FICTICIA',contenido);self.assertIn('DATO_PUBLICO',contenido)
    def test_jsonl_danado_con_clave_no_se_copia_sin_redactar(self):
        d=self.indexar(self.archivo('roto.jsonl','{"token": "secreto incompleto\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertNotIn('secreto incompleto',contenido);self.assertIn('JSONL',d['archivos'][0]['aviso'])
    def test_csv_etiqueta_clave_valor_se_oculta(self):
        d=self.indexar(self.archivo('etiqueta.csv','client_secret,VALOR_PRIVADO_FICTICIO\n'))
        with T._conexion() as db:contenido=' '.join(r[0] for r in db.execute('SELECT texto FROM trozos'))
        self.assertNotIn('VALOR_PRIVADO_FICTICIO',contenido);self.assertIn('[REDACTADO]',contenido)
    def zip_excesivo(self,n=1001,mentir=False):
        p=self.base/'muchos.zip'
        with zipfile.ZipFile(p,'w') as z:
            for i in range(n):z.writestr(str(i)+'.txt','')
        if mentir:
            raw=bytearray(p.read_bytes());raw[-14:-10]=struct.pack('<HH',1,1);p.write_bytes(raw)
        return p
    def test_detector_zip_rechaza_antes_de_zipfile(self):
        p=self.zip_excesivo()
        with patch.object(zipfile,'ZipFile',side_effect=AssertionError('ZipFile cargó el directorio antes del límite')):
            with self.assertRaisesRegex(ValueError,'entradas'):R.detectar(p,'.zip')
    def test_tanda_zip_rechaza_antes_de_zipfile(self):
        p=self.zip_excesivo(201)
        with patch.object(zipfile,'ZipFile',side_effect=AssertionError('ZipFile cargó el directorio antes del límite')):
            with self.assertRaisesRegex(ValueError,'entradas'):T.crear([p])
    def test_directorio_zip_con_cuenta_falsa_no_carga_zipfile(self):
        p=self.zip_excesivo(1001,True)
        with patch.object(zipfile,'ZipFile',side_effect=AssertionError('ZipFile cargó la cuenta falsa')):
            with self.assertRaisesRegex(ValueError,'entradas|directorio'):R.detectar(p,'.zip')
    def test_excel_preflight_rechaza_antes_de_zipfile(self):
        import libros_jarvis as X
        p=self.zip_excesivo()
        with patch.object(zipfile,'ZipFile',side_effect=AssertionError('ZipFile cargó el libro antes del límite')):
            with self.assertRaisesRegex(ValueError,'entradas'):X._libro(p)
    def test_preflight_directorio_mayor_limite(self):
        from zip_acotado import ZipFileAcotado,MAX_DIRECTORIO
        p=self.base/'directorio.zip';tam=MAX_DIRECTORIO+1
        with p.open('wb') as f:f.truncate(tam);f.seek(tam);f.write(struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,1,1,tam,0,0))
        with self.assertRaisesRegex(ValueError,'Directorio ZIP demasiado'):ZipFileAcotado(p)
    def test_preflight_zip64_se_rechaza_sin_cargar(self):
        from zip_acotado import ZipFileAcotado
        p=self.base/'zip64.zip';p.write_bytes(struct.pack('<4s4H2IH',b'PK\x05\x06',0,0,65535,65535,0,0,0))
        with self.assertRaisesRegex(ValueError,'ZIP64'):ZipFileAcotado(p)
    def test_preflight_comentario_con_firma_no_confunde_eocd(self):
        from zip_acotado import verificar_directorio_zip
        p=self.base/'comentado.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('dato.txt','DATO_PUBLICO');z.comment=b'comentario PK\x05\x06 firma interna'
        with p.open('rb') as f:self.assertEqual(verificar_directorio_zip(f)['entradas'],1)
    def test_preflight_falla_cuenta_falsa_aunque_debajo_limite(self):
        from zip_acotado import ZipFileAcotado
        p=self.zip_excesivo(3,True)
        with self.assertRaisesRegex(ValueError,'Cuenta de entradas'):ZipFileAcotado(p)
    def test_preflight_zip_vacio_valido(self):
        from zip_acotado import ZipFileAcotado
        p=self.base/'vacio.zip'
        with zipfile.ZipFile(p,'w'):pass
        with ZipFileAcotado(p) as z:self.assertEqual(z.namelist(),[])
    def test_preflight_libera_descriptor_tras_fallo(self):
        from zip_acotado import ZipFileAcotado
        real=open;observados=[];p=self.zip_excesivo()
        def abrir(*a,**kw):f=real(*a,**kw);observados.append(f);return f
        with patch('zip_acotado.open',side_effect=abrir):
            with self.assertRaises(ValueError):ZipFileAcotado(p)
        self.assertTrue(observados);self.assertTrue(all(f.closed for f in observados))

for c in CASOS:setattr(Pruebas,'test_'+c['id'].lower(),lambda self,c=c:self.caso(c))
if __name__=='__main__':unittest.main()
