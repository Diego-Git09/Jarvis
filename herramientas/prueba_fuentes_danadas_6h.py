"""Protección y daños reales en fuentes sintéticas; las demás continúan."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import secrets
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import tandas_documentales as T
from medir_adjuntos_pesados_6h import pdf
PYPDF=importlib.util.find_spec('pypdf') is not None
AES=importlib.util.find_spec('cryptography') is not None


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        patch.object(T,'RAIZ',self.base/'indice').start();patch.object(T,'CONFIG',self.base/'limites.json').start();patch.object(T,'RECURSOS',self.base/'recursos.json').start()
        self.bien=self.base/'legible.md';self.bien.write_text('ANCLA_LEGIBLE_POSTERIOR_73')

    def indexar(self,p):
        antes=hashlib.sha256(p.read_bytes()).hexdigest()
        d=T.indexar(T.crear([p,self.bien])['id'],False)
        r=T.buscar(d['id'],'ANCLA_LEGIBLE_POSTERIOR_73')
        self.assertTrue(any('ANCLA_LEGIBLE_POSTERIOR_73' in x['texto'] for x in r['trozos']))
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),antes)
        return d

    @unittest.skipUnless(shutil.which('pdfinfo') and shutil.which('pdftotext') and PYPDF and AES,'La fixture cifrada requiere Poppler, pypdf y cryptography')
    def test_pdf_cifrado_real_identifica_necesidad_de_contrasena(self):
        from pypdf import PdfWriter,PdfReader
        p=self.base/'cifrado.pdf';w=PdfWriter();w.add_blank_page(width=72,height=72)
        w.encrypt(secrets.token_urlsafe(24),algorithm='AES-256');w.write(p)
        self.assertTrue(PdfReader(p).is_encrypted)
        d=self.indexar(p);a=d['archivos'][0]
        self.assertEqual(a['estado'],'ilegible');self.assertIn('contraseña',a['aviso'])

    @unittest.skipUnless(shutil.which('pdfinfo') and shutil.which('pdftotext'),'Requiere Poppler local')
    def test_pdf_truncado_no_se_confunde_con_contrasena(self):
        p=self.base/'truncado.pdf';pdf(p,1);p.write_bytes(p.read_bytes()[:100])
        a=self.indexar(p)['archivos'][0]
        self.assertEqual(a['estado'],'ilegible');self.assertIn('dañado',a['aviso']);self.assertNotIn('contraseña',a['aviso'])

    @unittest.skipUnless(shutil.which('pdfinfo') and shutil.which('pdftotext') and PYPDF,'La fixture sin texto requiere Poppler y pypdf')
    def test_pagina_sin_texto_informa_ocr_y_no_exige_clave(self):
        from pypdf import PdfWriter
        p=self.base/'sin_texto.pdf';w=PdfWriter();w.add_blank_page(width=72,height=72);w.write(p)
        a=self.indexar(p)['archivos'][0]
        self.assertIn('sin texto',a['aviso']);self.assertIn('OCR',a['aviso']);self.assertNotIn('contraseña',a['aviso'])

    def test_zip_danado_excluido_sin_rechazar_la_tanda(self):
        p=self.base/'danado.zip';p.write_bytes(b'PK\x03\x04incompleto')
        d=self.indexar(p);self.assertEqual(len(d['archivos']),1);self.assertIn('ZIP',d['excluidas'][0]['motivo'])

    def test_tar_danado_informa_en_espanol_y_continua(self):
        p=self.base/'danado.tar';p.write_bytes(b'no es un tar'*60)
        d=self.indexar(p);self.assertEqual(len(d['archivos']),1)
        self.assertIn('TAR',d['excluidas'][0]['motivo']);self.assertIn('dañado',d['excluidas'][0]['motivo'])

    def test_gzip_truncado_declara_que_no_esta_completo(self):
        p=self.base/'truncado.gz';p.write_bytes(gzip.compress(b'Contenido sinteticamente repetido\n'*3000)[:-6])
        a=self.indexar(p)['archivos'][0]
        self.assertIn(a['estado'],{'ilegible','parcial'});self.assertIn('truncado',a['aviso'])

    def test_sqlite_danado_no_bloquea_otra_fuente(self):
        p=self.base/'danado.sqlite';p.write_bytes(b'no es una base SQLite')
        a=self.indexar(p)['archivos'][0]
        self.assertEqual(a['estado'],'ilegible');self.assertIn('SQLite',a['aviso']);self.assertIn('dañad',a['aviso'])

    def test_xlsx_con_componentes_faltantes_da_motivo_legible(self):
        p=self.base/'incompleto.xlsx'
        with zipfile.ZipFile(p,'w') as z:z.writestr('xl/workbook.xml','<workbook/>')
        a=self.indexar(p)['archivos'][0]
        self.assertEqual(a['estado'],'ilegible');self.assertIn('componente',a['aviso']);self.assertIn('incompleto',a['aviso'])

    def test_xml_docx_truncado_se_informa_y_continua(self):
        p=self.base/'truncado.docx'
        with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<document><p>sin cerrar')
        a=self.indexar(p)['archivos'][0]
        self.assertIn(a['estado'],{'ilegible','parcial'});self.assertIn('XML',a['aviso']);self.assertIn('dañado',a['aviso'])

    def test_unico_tar_danado_tambien_tiene_un_error_legible(self):
        p=self.base/'unico.tar';p.write_bytes(b'no es un tar'*60)
        with self.assertRaises((ValueError,tarfile.TarError)) as e:T.crear([p])
        self.assertIn('TAR',str(e.exception));self.assertIn('dañado',str(e.exception))

    def test_nombre_password_no_inventa_proteccion_por_contrasena(self):
        import documentos_jarvis as D
        aviso=D._error_pdf("I/O Error: Couldn't open file '/tmp/password.pdf': Permission denied")
        self.assertNotIn('contraseña',aviso);self.assertIn('permisos',aviso)

    def test_diagnostico_pdf_no_muestra_fragmentos_del_error_interno(self):
        import documentos_jarvis as D
        aviso=D._error_pdf('Syntax Error: api_key=SECRETO_FICTICIO_73')
        self.assertNotIn('SECRETO_FICTICIO_73',aviso)
        self.assertIn('dañado',aviso)

    def test_error_interno_desconocido_no_se_atribuye_a_un_componente_faltante(self):
        from errores_adjuntos import explicar
        aviso=explicar(KeyError('fallo_interno api_key=SECRETO_FICTICIO_73'),'.xlsx')
        self.assertNotIn('componente',aviso);self.assertNotIn('SECRETO_FICTICIO_73',aviso)
        self.assertIn('fallo_interno',aviso)


if __name__=='__main__':unittest.main()
