"""Una respuesta de embeddings inválida no debe perder el texto de una tanda."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cliente_ollama as O
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        for k,v in [('RAIZ',self.base/'indice'),('CONFIG',self.base/'limites.json'),('RECURSOS',self.base/'recursos.json')]:patch.object(T,k,v).start()

    def conserva_textos(self,respuesta):
        a=self.base/'primero.txt';b=self.base/'segundo.txt'
        a.write_text('ORIGEN_UNO. Se conservan 713 unidades.');b.write_text('ORIGEN_DOS. Se conservan 419 unidades.')
        with patch.object(O,'solicitar',return_value=respuesta) as peticion:
            d=T.indexar(T.crear([a,b])['id'],True)
        self.assertEqual(peticion.call_count,1,'Una respuesta inválida no se repite por cada fuente.')
        self.assertEqual(d['modelo_embeddings'],'')
        self.assertTrue(all(f['caracteres_indexados']>0 and not f['embeddings_completos'] for f in d['archivos']))
        with patch.object(O,'solicitar',side_effect=AssertionError('La consulta debe usar el texto ya conservado.')):
            r=T.buscar(d['id'],'ORIGEN_DOS',presupuesto=5000)
        self.assertTrue(any('419' in t['texto'] for t in r['trozos']))

    def test_lista_de_embeddings_vacia_conserva_la_tanda(self):
        self.conserva_textos({'embeddings':[]})

    def test_campo_embeddings_nulo_conserva_la_tanda(self):
        self.conserva_textos({'embeddings':None})

    def test_campo_embeddings_de_tipo_distinto_conserva_la_tanda(self):
        self.conserva_textos({'embeddings':'no es una matriz'})

    def test_raiz_inesperada_conserva_la_tanda(self):
        self.conserva_textos([])

    def test_entero_demasiado_grande_conserva_la_tanda(self):
        self.conserva_textos({'embeddings':[[10**500,1]]})

    def test_segundo_vector_inesperado_no_se_ignora_como_si_fuera_respuesta_valida(self):
        self.conserva_textos({'embeddings':[[1.,0.],[0.,1.]]})

    def test_vector_valido_se_normaliza_sin_cambiar_el_contrato(self):
        with patch.object(O,'solicitar',return_value={'embeddings':[[3.,4.]]}):v=T._vector('dato ficticio','modelo:ficticio')
        self.assertEqual(v,[.6,.8])


if __name__=='__main__':unittest.main()
