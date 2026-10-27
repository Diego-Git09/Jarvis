"""Exclusiones documentales sin invertir negativas de verbos como «ignorar»."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evaluar_referencias_fuente_6h as E
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        for k,v in [('RAIZ',self.base/'indice'),('CONFIG',self.base/'limites.json'),('RECURSOS',self.base/'recursos.json')]:patch.object(T,k,v).start()

    def buscar(self,pregunta):
        a=self.base/'anexo_a.txt';b=self.base/'anexo_b.txt'
        a.write_text('DATO_A. Inventario de 713 unidades.');b.write_text('DATO_B. Interfaz Android.')
        d=T.indexar(T.crear([a,b])['id'],True,embedding=lambda t,m:[0.,1.] if 'DATO_A' in t else [1.,0.])
        return T.buscar(d['id'],pregunta,embedding=lambda *_:[1.,0.])

    def test_corpus_congelado_de_referencias_y_negativas(self):
        for pregunta,oro in E.CASOS:
            with self.subTest(pregunta=pregunta):self.assertEqual(E.H.estado_fuente(pregunta,E.FUENTE),oro)

    def test_no_ignores_conserva_y_prioriza_la_fuente(self):
        r=self.buscar('No ignores anexo_a.txt, necesito su explicación de Android.')
        self.assertTrue(r['trozos'][0]['referencia'].startswith('anexo_a.txt'))

    def test_sin_excluir_conserva_la_fuente(self):
        r=self.buscar('Revisa todo sin excluir anexo_a.txt sobre Android.')
        self.assertTrue(any('DATO_A' in t['texto'] for t in r['trozos']))

    def test_salvo_retira_la_fuente_del_contexto(self):
        r=self.buscar('Revisa todas salvo anexo_a.txt para explicar Android.')
        self.assertFalse(any('DATO_A' in t['texto'] for t in r['trozos']))

    def test_no_omitas_no_se_convierte_en_omision(self):
        r=self.buscar('No omitas anexo_a.txt sobre Android.')
        self.assertTrue(r['trozos'][0]['referencia'].startswith('anexo_a.txt'))


if __name__=='__main__':unittest.main()
