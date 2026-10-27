"""Selección visible por fuente y lectura real de tandas mixtas, sin inferencia."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import tandas_documentales as T
import prueba_tandas_documentales as FIX


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        for k,v in [('RAIZ',self.base/'indice'),('CONFIG',self.base/'limites.json'),('RECURSOS',self.base/'recursos.json')]:patch.object(T,k,v).start()

    def archivo(self,n,t):p=self.base/n;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(t);return p

    def test_lista_exacta_de_seleccion_y_fuentes_fuera(self):
        p=self.archivo('uno.txt','CLAVE_UNO');q=self.archivo('dos.txt','CLAVE_DOS')
        d=T.indexar(T.crear([p,q])['id'],False);r=T.buscar(d['id'],'CLAVE_UNO',limite=1)
        texto=T.detalle_cobertura(d,r)
        self.assertIn('"uno.txt"',texto);self.assertIn('"dos.txt": sin trozos',texto)
        self.assertNotIn('CLAVE_UNO',texto)

    def test_nombres_duplicados_con_cobertura_separada(self):
        p=self.archivo('uno/igual.txt','CLAVE_UNO');q=self.archivo('dos/igual.txt','CLAVE_DOS')
        d=T.indexar(T.crear([p,q])['id'],False);r=T.buscar(d['id'],'CLAVE_UNO',limite=1)
        filas=r['cobertura_modelo'];self.assertEqual(len({x['archivo'] for x in filas}),2)
        self.assertGreater(filas[0]['caracteres_recibidos_modelo'],0);self.assertEqual(filas[1]['caracteres_recibidos_modelo'],0)

    def test_fuente_modificada_y_ausente_muestran_causa_sin_cache(self):
        p=self.archivo('cambio.txt','SECRETO_CACHE_SINTETICO');q=self.archivo('ausente.txt','DATO_ANTES')
        d=T.indexar(T.crear([p,q])['id'],False);p.write_text('Nuevo');q.unlink();r=T.buscar(d['id'],'dato')
        self.assertFalse(r['trozos']);self.assertEqual(len(r['fuentes_no_recuperables']),2)
        texto=T.detalle_cobertura(d,r);self.assertIn('fuente cambió',texto);self.assertIn('fuente ausente',texto);self.assertNotIn('SECRETO_CACHE',texto)

    def test_pendientes_no_se_interpreta_como_ruta(self):
        p=self.archivo('roto.docx','ZIP_INVÁLIDO');q=self.archivo('grande.txt','Texto '*3000)
        T.configurar(dict(T.DEFAULT,caracteres_archivo=1000));d=T.indexar(T.crear([p,q])['id'],False)
        with patch.object(T,'crear',side_effect=AssertionError('No adjunta otra fuente')):
            ok,t=T.comando('/adjuntos pendientes',{'_tanda_documentos':d['id']})
        self.assertTrue(ok);self.assertIn('roto.docx',t);self.assertIn('ilegible',t);self.assertIn('grande.txt',t);self.assertIn('parcial',t)

    def test_cobertura_guardada_solo_para_ultima_tanda(self):
        p=self.archivo('dato.txt','DATO_SINTETICO');d=T.indexar(T.crear([p])['id'],False);e={'_tanda_documentos':d['id']}
        T.contexto(e,'DATO_SINTETICO');ok,t=T.comando('/adjuntos cobertura',e)
        self.assertTrue(ok);self.assertIn('dato.txt',t);self.assertNotIn('DATO_SINTETICO',t)
        e['_tanda_documentos']='a'*32;self.assertIn('No hay selección',T.comando('/adjuntos cobertura',e)[1])

    def test_detalle_grande_no_se_copia_al_prompt(self):
        fuentes=[self.archivo(f'fuente_{i:03}.txt',f'DATO_SINTETICO_{i}') for i in range(20)]
        d=T.indexar(T.crear(fuentes)['id'],False);e={'_tanda_documentos':d['id']}
        texto=T.contexto(e,'DATO_SINTETICO_0',presupuesto=1200)
        self.assertNotIn('sin trozos seleccionados en esta respuesta',texto)
        self.assertIn('sin trozos seleccionados en esta respuesta',e['_ultima_cobertura_tanda']['texto'])

    @unittest.skipUnless(shutil.which('pdftotext'),'Necesita el lector PDF Poppler')
    def test_tanda_105_fuentes_mixtas_sin_ejecutar_codigo_y_originales_intactos(self):
        fuentes=[self.archivo(f'nota_{i:03}.txt',f'CLAVE_{i:03} texto sintético') for i in range(100)]
        pdf=FIX.Pruebas.pdf(self,'caso.pdf','CLAVE_PDF_921 dato sintetico');fuentes.append(pdf)
        word=self.base/'caso.docx'
        with zipfile.ZipFile(word,'w') as z:z.writestr('word/document.xml','<w:document xmlns:w="urn:w"><w:body><w:p><w:t>CLAVE_WORD_922</w:t></w:p></w:body></w:document>')
        fuentes.append(word);excel=self.base/'caso.xlsx';FIX.libro(excel,5);fuentes.append(excel)
        fuentes.append(self.archivo('script.py','raise RuntimeError("NO_EJECUTAR_CODIGO_923")'))
        fuentes.append(self.archivo('grande.txt',('linea extensa de prueba\n'*120000)+'CLAVE_FINAL_924\n'))
        antes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in fuentes}
        d=T.indexar(T.crear(fuentes)['id'],False);self.assertEqual(len(d['archivos']),105)
        self.assertEqual(d['archivos'][-1]['estado'],'parcial')
        for clave in ['CLAVE_099','CLAVE_PDF_921','CLAVE_WORD_922','fila3','NO_EJECUTAR_CODIGO_923']:
            self.assertTrue(any(clave in x['texto'] for x in T.buscar(d['id'],clave,presupuesto=6000)['trozos']),clave)
        for p in fuentes:self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),antes[str(p)])


if __name__=='__main__':unittest.main()
