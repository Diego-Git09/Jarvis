"""Texto con caracteres no ASCII: evidencia real de codificación y del IPC."""
import codecs
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lectores_adjuntos as L
import tandas_documentales as T

PUBLICO='Revisión del café de mañana: número 731, pingüino y año.\n'


class Pruebas(unittest.TestCase):
    def leer(self,raw):
        item={'nombre':'fuente.txt'};texto=''.join(t for _,t in L.bloques_texto(io.BytesIO(raw),item,300000));return texto,item

    def test_utf8_con_acentos(self):self.assertEqual(self.leer(PUBLICO.encode())[0],PUBLICO)
    def test_utf8_con_bom(self):self.assertEqual(self.leer(codecs.BOM_UTF8+PUBLICO.encode())[0],PUBLICO)
    def test_utf16_little_endian_con_bom(self):self.assertEqual(self.leer(codecs.BOM_UTF16_LE+PUBLICO.encode('utf-16-le'))[0],PUBLICO)
    def test_utf16_big_endian_con_bom(self):self.assertEqual(self.leer(codecs.BOM_UTF16_BE+PUBLICO.encode('utf-16-be'))[0],PUBLICO)
    def test_utf16_little_endian_sin_bom(self):self.assertEqual(self.leer(PUBLICO.encode('utf-16-le'))[0],PUBLICO)
    def test_utf16_big_endian_sin_bom(self):self.assertEqual(self.leer(PUBLICO.encode('utf-16-be'))[0],PUBLICO)

    def test_cp1252_con_comillas_y_euro_que_no_son_ascii(self):
        contenido='“Revisión” — costo 731 €; mañana café.\n';texto,item=self.leer(contenido.encode('cp1252'))
        self.assertEqual(texto,contenido);self.assertEqual(item['codificacion'],'cp1252')

    def test_latin1_con_byte_no_decodificable_como_cp1252(self):
        contenido=PUBLICO+'Control C1 sintético: \x81\n';texto,item=self.leer(contenido.encode('latin-1'))
        self.assertEqual(texto,contenido);self.assertEqual(item['codificacion'],'latin-1')

    def test_caracter_utf8_partido_entre_dos_lecturas(self):
        contenido='A'*8191+'ñ'+PUBLICO
        self.assertEqual(self.leer(contenido.encode())[0],contenido)

    def test_etiqueta_de_campo_sensible_con_enie(self):
        privado='VALOR_FICTICIO_NO_VALIDO_73';contenido='contraseña='+privado+'\n'+PUBLICO
        texto,_=self.leer(contenido.encode('latin-1'));self.assertFalse(privado in texto);self.assertIn('[REDACTADO]',texto);self.assertIn(PUBLICO,texto)

    def test_nulos_sin_patron_utf16_se_rechazan_como_binario(self):
        with self.assertRaises(ValueError):self.leer(b'ab\x00cd\xff\x00efgh\x01')

    def test_worker_no_rompe_unicode_al_limitar_bytes_del_ipc(self):
        with tempfile.TemporaryDirectory(dir=T.L.RAIZ) as tmp:
            base=Path(tmp);p=base/'acentos.txt';contenido=(PUBLICO*4000)+'MARCA_FINAL_UNICODE_73\n';p.write_text(contenido)
            with patch.object(T,'RAIZ',base/'indice'):
                d=T.indexar(T.crear([p])['id'],False);r=T.buscar(d['id'],'MARCA_FINAL_UNICODE_73',presupuesto=5000)
                self.assertTrue(any('MARCA_FINAL_UNICODE_73' in x['texto'] for x in r['trozos']))
                self.assertFalse(any('\ufffd' in x['texto'] for x in r['trozos']));self.assertEqual(d['archivos'][0]['estado'],'indexado')
            self.assertEqual(p.read_text(),contenido)


if __name__=='__main__':unittest.main()
