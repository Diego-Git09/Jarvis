"""SQLite sintético: muestras, privacidad, límites y consultas del lector."""
import hashlib
from contextlib import closing,contextmanager
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import lectura_sqlite as S
import lectores_adjuntos as R
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.p=self.base/'fuente.sqlite';self.addCleanup(patch.stopall)

    def crear(self,ddl,filas=(),insert='INSERT INTO datos VALUES(?)'):
        with self.conectar() as db:
            db.execute(ddl)
            if filas:db.executemany(insert,filas)

    @contextmanager
    def conectar(self):
        with closing(sqlite3.connect(self.p)) as db,db:yield db

    def leer(self,tope=2000000):
        item={'nombre':self.p.name,'tipo':'.sqlite'}
        partes=list(R._sqlite(self.p,item,tope))
        return '\n'.join(t for _,t in partes),item,partes

    def test_esquema_y_veinte_filas_original_intacto(self):
        self.crear('CREATE TABLE datos(n INTEGER)',[(i,) for i in range(80)])
        antes=hashlib.sha256(self.p.read_bytes()).hexdigest();t,m,_=self.leer()
        self.assertIn('\n19\n',t);self.assertNotIn('\n20\n',t)
        self.assertIn('1000 caracteres',m['aviso']);self.assertEqual(hashlib.sha256(self.p.read_bytes()).hexdigest(),antes)

    def test_celda_grande_y_blob_son_muestra_equivalente(self):
        from medir_sqlite_6h import preparar,ESPECIFICACION
        preparar(self.p);t,_,_=self.leer()
        self.assertTrue(all(x in t for x in ESPECIFICACION['oro']))
        self.assertNotIn(ESPECIFICACION['prohibido'],t);self.assertLess(len(t),3000)

    def test_clave_privada_cuyo_cierre_no_cabe_no_oculta_otra_celda(self):
        secreto='-----BEGIN PRIVATE KEY-----\n'+('CUERPO_NO_PUBLICO'*10000)+'\n-----END PRIVATE KEY-----'
        self.crear('CREATE TABLE datos(texto TEXT,otro TEXT)',[(secreto,'DATO_POSTERIOR')],'INSERT INTO datos VALUES(?,?)')
        t,_,_=self.leer();self.assertNotIn('CUERPO_NO_PUBLICO',t)
        self.assertIn('[CLAVE PRIVADA REDACTADA]',t);self.assertIn('DATO_POSTERIOR',t)

    def test_texto_utf16_grande_se_decodifica_sin_perder_literales(self):
        with self.conectar() as db:
            db.execute("PRAGMA encoding='UTF-16le'")
            db.execute('CREATE TABLE datos(texto TEXT)');db.execute('INSERT INTO datos VALUES(?)',('Mañana á😀_'*30000,))
        t,_,_=self.leer();self.assertIn('Mañana á😀_',t);self.assertNotIn('\ufffd',t)

    def test_identificadores_con_comillas_no_son_sql(self):
        with self.conectar() as db:
            db.execute('CREATE TABLE "tabla "" rara"("dato "" público" TEXT,"api-key" TEXT)')
            db.execute('INSERT INTO "tabla "" rara" VALUES(?,?)',('DATO_CITADO_73','SECRETO_73'))
        t,_,_=self.leer();self.assertIn('DATO_CITADO_73',t);self.assertNotIn('SECRETO_73',t)

    def test_sin_rowid_grande_declara_omision_y_conserva_otros_campos(self):
        self.crear('CREATE TABLE datos(clave TEXT PRIMARY KEY,texto TEXT,monto INTEGER) WITHOUT ROWID',
            [('ALFA','x'*100000,473)],'INSERT INTO datos VALUES(?,?,?)')
        t,m,_=self.leer();self.assertIn('lectura por partes no disponible',t);self.assertIn('473',t);self.assertIn('se omite esa celda',m['aviso'])

    def test_sin_rowid_pequeno_conserva_la_muestra(self):
        self.crear('CREATE TABLE datos(clave TEXT PRIMARY KEY,texto TEXT) WITHOUT ROWID',
            [('ALFA','Mañana literal 73')],'INSERT INTO datos VALUES(?,?)')
        t,_,_=self.leer();self.assertIn('ALFA | Mañana literal 73',t)

    def test_alias_rowid_ocupados_no_mezclan_filas_por_indices(self):
        self.crear('CREATE TABLE datos(rowid TEXT,_rowid_ TEXT,oid TEXT,valor INTEGER)',
            [(f'a{i}',f'b{i}',f'c{i}',99-i) for i in range(25)],'INSERT INTO datos VALUES(?,?,?,?)')
        with self.conectar() as db:db.execute('CREATE INDEX orden_inverso ON datos(valor)')
        t,_,_=self.leer()
        for i in range(20):self.assertIn(f'a{i} | b{i} | c{i} | {99-i}\n',t)

    def test_columna_virtual_no_se_calcula(self):
        self.crear("CREATE TABLE datos(n INTEGER,calculada TEXT AS (printf('%10000000c',n)) VIRTUAL)",[(65,)],'INSERT INTO datos(n) VALUES(?)')
        t,m,_=self.leer();self.assertIn('\n65\n',t);self.assertNotIn('A'*1000,t)
        self.assertIn('no calculé expresiones',m['aviso'])

    def test_vistas_y_modulos_virtuales_no_se_consultan(self):
        self.crear('CREATE TABLE datos(n INTEGER)',[(73,)])
        with self.conectar() as db:
            db.execute("CREATE VIEW peligrosa AS SELECT load_extension('/tmp/NO_CARGAR')")
            db.execute('CREATE VIRTUAL TABLE busqueda USING fts5(texto)')
        t,m,_=self.leer();self.assertNotIn('NO_CARGAR',t);self.assertIn('no consulté sus filas',m['aviso']);self.assertIn('\n73\n',t)

    def test_autorizador_rechaza_escritura_adjuntar_y_extension(self):
        self.crear('CREATE TABLE datos(n INTEGER)',[(73,)])
        for sql in ['DELETE FROM datos','CREATE TABLE nueva(n)','ATTACH DATABASE ":memory:" AS otra',
                    'PRAGMA writable_schema=ON',"SELECT load_extension('/tmp/NO_CARGAR')"]:
            with self.subTest(sql=sql),S.abrir(self.p) as db,self.assertRaises(sqlite3.DatabaseError):db.execute(sql)
        with self.conectar() as db:self.assertEqual(db.execute('SELECT n FROM datos').fetchone()[0],73)

    def test_tope_global_con_muchas_celdas_no_reserva_salida_mayor(self):
        columnas=','.join('c'+str(i)+' TEXT' for i in range(60))
        with self.conectar() as db:
            db.execute('CREATE TABLE datos('+columnas+')')
            db.executemany('INSERT INTO datos VALUES('+','.join('?' for _ in range(60))+')',[tuple('x'*1500 for _ in range(60))]*20)
        t,m,_=self.leer(3000);self.assertLessEqual(len(t),3000);self.assertTrue(m['cortado'])

    def test_limite_cien_tablas_no_se_detiene_en_la_primera(self):
        with self.conectar() as db:
            for i in range(101):db.execute(f'CREATE TABLE t{i:03d}(n INTEGER)')
        _,m,partes=self.leer();self.assertEqual(len(partes),100);self.assertTrue(m['cortado'])

    def test_runtime_sin_octet_length_declara_solo_esquema_acotado(self):
        self.crear("CREATE TABLE datos(api_key TEXT DEFAULT 'SECRETO_DEFAULT_73')")
        original=sqlite3.connect
        class Antigua:
            def __init__(self,*a,**kw):self.db=original(*a,**kw)
            def __getattr__(self,n):return getattr(self.db,n)
            def execute(self,sql,*a,**kw):
                if sql=="SELECT octet_length('')":raise sqlite3.OperationalError('no such function: octet_length')
                return self.db.execute(sql,*a,**kw)
        with patch.object(S.sqlite3,'connect',Antigua):t,m,_=self.leer(300)
        self.assertLessEqual(len(t),300);self.assertIn('solo esquema',m['aviso']);self.assertNotIn('SECRETO_DEFAULT_73',t)

    def test_indices_y_worker_mantienen_cita_y_advertencia(self):
        self.crear('CREATE TABLE datos(n INTEGER,texto TEXT)',[(473,'ANCLA_SQLITE_73')],'INSERT INTO datos VALUES(?,?)')
        patch.object(T,'RAIZ',self.base/'indice').start();patch.object(T,'CONFIG',self.base/'limites.json').start();patch.object(T,'RECURSOS',self.base/'recursos.json').start()
        d=T.indexar(T.crear([self.p])['id'],False);r=T.buscar(d['id'],'ANCLA_SQLITE_73')
        self.assertEqual(d['archivos'][0]['estado'],'indexado');self.assertIn('1000 caracteres',d['archivos'][0]['aviso'])
        self.assertTrue(any('tabla datos' in x['referencia'] and '473' in x['texto'] for x in r['trozos']))

    def test_cancelacion_en_progreso_sqlite_conserva_el_tipo_de_error(self):
        self.crear('CREATE TABLE datos(n INTEGER)',[(i,) for i in range(3000)])
        for tipo in (InterruptedError,TimeoutError):
            def control():raise tipo('Interrupción sintética')
            with self.subTest(tipo=tipo),self.assertRaises(tipo),S.abrir(self.p,control) as db:
                db.execute('SELECT n FROM datos').fetchall()

    def test_nombre_extenso_declara_omision_y_continua(self):
        nombre='n'*5000
        with self.conectar() as db:
            db.execute('CREATE TABLE "'+nombre+'"(n INTEGER)')
            db.execute('CREATE TABLE z_legible(n INTEGER)');db.execute('INSERT INTO z_legible VALUES(473)')
        t,m,_=self.leer();self.assertIn('Nombre de tabla mayor de4096',m['aviso']);self.assertIn('\n473\n',t)
        self.assertNotIn(nombre,t)

    def test_fallback_antiguo_preserva_tope_global_y_redacta_default_truncado(self):
        with self.conectar() as db:
            for i in range(10):db.execute(f"CREATE TABLE t{i}(api_key TEXT DEFAULT '"+('NO_PUBLICAR_'*500)+"')")
        original=sqlite3.connect
        class Antigua:
            def __init__(self,*a,**kw):self.db=original(*a,**kw)
            def __getattr__(self,n):return getattr(self.db,n)
            def execute(self,sql,*a,**kw):
                if sql=="SELECT octet_length('')":raise sqlite3.OperationalError('no such function: octet_length')
                return self.db.execute(sql,*a,**kw)
        with patch.object(S.sqlite3,'connect',Antigua):_,m,partes=self.leer(300)
        self.assertLessEqual(sum(len(t) for _,t in partes),300)
        self.assertTrue(m['cortado']);self.assertTrue(all('NO_PUBLICAR_' not in t for _,t in partes))

    def test_default_compuesto_se_redacta_sin_ocultar_el_nombre_de_la_columna(self):
        self.crear("CREATE TABLE datos(\"default\" TEXT,api_key TEXT DEFAULT (printf('%s','NO_PUBLICAR_73')))")
        t,_,_=self.leer();self.assertIn('"default" TEXT',t)
        self.assertNotIn('NO_PUBLICAR_73',t);self.assertIn('DEFAULT [VALOR OMITIDO]',t)

    def test_default_con_comentarios_signo_y_parentesis_queda_oculto(self):
        self.crear("CREATE TABLE datos(api_key TEXT DEFAULT /* espacio */ (printf('%s',('NO_PUBLICAR_73'))), codigo INTEGER DEFAULT - 12345)")
        t,_,_=self.leer();self.assertNotIn('NO_PUBLICAR_73',t);self.assertNotIn('12345',t)
        self.assertEqual(t.count('DEFAULT [VALOR OMITIDO]'),2)


if __name__=='__main__':unittest.main()
