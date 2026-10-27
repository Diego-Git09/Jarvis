"""Lecturas públicas aisladas y acotadas; archivos ficticios en la raíz temporal."""
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import adjuntos_jarvis as A
import documentos_jarvis as D
import herramientas_lectura as L
from prueba_documentos_rutas import pdf_prueba


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)

    def docx(self,textos):
        p=self.base/'fuente.docx'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('word/document.xml','<document>'+''.join('<p>'+t+'</p>' for t in textos)+'</document>')
        return p

    def test_texto_publico_no_lee_bytes_y_oculta_secreto(self):
        p=self.base/'fuente.py';p.write_text('print("NO EJECUTAR")\napi_key=valor_ficticio_privado\n')
        with patch.object(Path,'read_bytes',side_effect=AssertionError('No debe cargar el archivo en el padre')):
            r=A.leer_adjunto(p)
        self.assertIn('NO EJECUTAR',r['texto']);self.assertNotIn('valor_ficticio_privado',r['texto']);self.assertIn('[REDACTADO]',r['texto'])

    def test_adjunto_solo_acumula_diez_mil_caracteres(self):
        p=self.base/'fuente.txt';p.write_text('dato publico\n'*2000)
        r=A.leer_adjunto(p);self.assertEqual(len(r['texto']),A.MAX_TEXTO);self.assertTrue(r['cortado'])

    def test_adjunto_docx_no_usa_lector_dom_heredado(self):
        p=self.docx(['DATO_DOCUMENTO','Otro párrafo'])
        with patch.object(Path,'read_bytes',side_effect=AssertionError('No debe cargar el archivo en el padre')),patch.object(A,'_texto_docx',side_effect=AssertionError('No debe usar DOM heredado')):
            r=A.leer_adjunto(p)
        self.assertEqual(r['texto'],'DATO_DOCUMENTO\nOtro párrafo')

    def test_documento_por_tramos_conserva_final(self):
        p=self.docx(['DATO_INICIAL '+('palabra '*800),'DATO_FINAL'])
        with patch.object(Path,'read_bytes',side_effect=AssertionError('No debe cargar el archivo en el padre')):
            a=D.leer(p);b=D.leer(p,**a['siguiente_documento'])
        self.assertIn('DATO_INICIAL',a['contenido']);self.assertIn('DATO_FINAL',b['contenido']);self.assertIsNone(b['siguiente_documento'])

    @unittest.skipUnless(shutil.which('pdftotext') and shutil.which('pdfinfo'),'Requiere Poppler local')
    def test_documento_pdf_pagina_dos_mediante_worker(self):
        p=self.base/'fuente.pdf';pdf_prueba(p)
        with patch.object(D,'_pdf',side_effect=AssertionError('La extracción debe ocurrir en el worker')):
            r=D.leer(p,inicio=2)
        self.assertEqual(r['total_paginas'],2);self.assertIn('Segunda pagina',r['contenido']);self.assertNotIn('Primera pagina',r['contenido'])

    def test_adaptador_privado_bytes_tiene_limite_expandido(self):
        datos=io.BytesIO()
        with zipfile.ZipFile(datos,'w') as z:z.writestr('word/document.xml','<document><p>'+'x'*(1024**2)+'</p></document>')
        with self.assertRaisesRegex(ValueError,'1 MiB expandido'):A._texto_docx(datos.getvalue())

    def test_imagen_acotada_no_usa_read_bytes(self):
        p=self.base/'fuente.png';p.write_bytes(b'contenido ficticio')
        with patch.object(Path,'read_bytes',side_effect=AssertionError('La imagen usa lectura acotada')):r=A.leer_adjunto(p,'llava:7b')
        self.assertTrue(r['imagen'])

    def test_documento_no_acumula_mas_de_quinientos_mil(self):
        p=self.docx(['dato']);cerrados=[]
        def unidades(*args,**kw):
            try:
                for i in range(150):yield 'fuente.docx · párrafo '+str(i),'x'*4000
            finally:cerrados.append(True)
        with patch('extraccion_aislada.unidades',side_effect=unidades):
            r=D.leer(p,offset=D.MAX_EXTRAIDO-2)
        self.assertEqual(len(r['contenido']),2);self.assertTrue(r['cortado']);self.assertIsNone(r['siguiente_documento']);self.assertTrue(cerrados)


if __name__=='__main__':unittest.main()
