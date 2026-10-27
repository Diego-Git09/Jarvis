"""Bytes no ASCII que aparecen después del prefijo usado para detectar texto."""
import codecs
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lectores_adjuntos as L
import tandas_documentales as T

PUBLICO='MARCA_FINAL_CODIFICACION_73'


class Pruebas(unittest.TestCase):
    def leer(self,raw,nombre='fuente.txt'):
        item={'nombre':nombre};txt=''.join(t for _,t in L.bloques_texto(io.BytesIO(raw),item,300000));return txt,item

    def parcial(self,item):
        self.assertTrue(item.get('cortado'));self.assertIn('codificación',item.get('aviso','').casefold())

    def test_latin1_tardio_conserva_la_enie_y_avisa(self):
        esperado='A'*20000+'mañana café '+PUBLICO+'\n';txt,item=self.leer(esperado.encode('latin-1'))
        self.assertTrue(txt==esperado,'No conservó el texto Latin1 posterior al prefijo ASCII.');self.parcial(item)

    def test_cp1252_tardio_conserva_comillas_y_euro(self):
        esperado='A'*20000+'“Revisión” — 731 € '+PUBLICO+'\n';txt,item=self.leer(esperado.encode('cp1252'))
        self.assertTrue(txt==esperado,'No conservó el texto CP1252 posterior al prefijo ASCII.');self.parcial(item)

    def test_mezcla_conserva_el_utf8_anterior_y_declara_parcial(self):
        antes='Revisión UTF8, café y año.\n'+'A'*20000;despues='mañana '+PUBLICO+'\n'
        txt,item=self.leer(antes.encode()+despues.encode('latin-1'))
        self.assertTrue(txt==antes+despues,'No conservó el texto previo al cambio de codificación.');self.parcial(item)

    def test_utf16_danado_se_declara_parcial_sin_perder_el_texto_previo(self):
        raw=codecs.BOM_UTF16_LE+(PUBLICO+'\n').encode('utf-16-le')+b'\x00\xd8'
        txt,item=self.leer(raw);self.assertIn(PUBLICO,txt);self.parcial(item)

    def test_jsonl_tardio_sigue_parseado_y_no_silencia_la_sustitucion(self):
        antes=(json.dumps({'dato':'PUBLICO_ASCII'})+'\n')*1000
        despues=json.dumps({'dato':'mañana '+PUBLICO},ensure_ascii=False)+'\n'
        txt,item=self.leer(antes.encode()+despues.encode('latin-1'),'fuente.jsonl')
        self.assertIn('mañana '+PUBLICO,txt);self.assertFalse('\ufffd' in txt);self.parcial(item)

    def test_etiqueta_sensible_tardia_no_pierde_la_redaccion_por_un_acento(self):
        privado='VALOR_FICTICIO_SIN_USO_73';raw=('A'*20000+'\ncontraseña='+privado+'\n'+PUBLICO+'\n').encode('latin-1')
        txt,item=self.leer(raw);self.assertFalse(privado in txt);self.assertIn(PUBLICO,txt);self.parcial(item)

    def test_worker_indexa_datos_recuperados_y_marca_la_incertidumbre(self):
        with tempfile.TemporaryDirectory(dir=T.L.RAIZ) as tmp:
            base=Path(tmp);p=base/'fuente.txt';raw=('A'*20000+'\nmañana '+PUBLICO+'\n').encode('latin-1');p.write_bytes(raw)
            with patch.object(T,'RAIZ',base/'indice'):
                d=T.indexar(T.crear([p])['id'],False);r=T.buscar(d['id'],PUBLICO,presupuesto=5000)
                self.assertTrue(any('mañana '+PUBLICO in t['texto'] for t in r['trozos']));self.assertEqual(d['archivos'][0]['estado'],'parcial')
            self.assertEqual(p.read_bytes(),raw)


if __name__=='__main__':unittest.main()
