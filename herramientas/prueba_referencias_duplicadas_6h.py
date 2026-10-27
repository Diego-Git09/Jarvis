"""Dos archivos con igual nombre deben conservar una procedencia distinguible."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tandas_documentales as T
import resumen_documental as R


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        for k,v in [('RAIZ',self.base/'indice'),('CONFIG',self.base/'limites.json'),('RECURSOS',self.base/'recursos.json')]:patch.object(T,k,v).start()
        patch.object(R,'CARPETA',self.base/'resumenes').start()
        self.paths=[]
        for nombre,texto in [('uno','DUP_A. Cantidad 713.'),('dos','DUP_B. Android y sus pantallas.')]:
            p=self.base/nombre;p.mkdir();p=p/'igual.txt';p.write_text(texto);self.paths.append(p)

    def test_busqueda_distingue_dos_procedencias_con_nombre_igual(self):
        d=T.indexar(T.crear(self.paths)['id'],False);r=T.buscar(d['id'],'DUP',presupuesto=6000)
        refs=[x['referencia'] for x in r['trozos']]
        self.assertEqual(len(refs),2);self.assertEqual(len(set(refs)),2)
        self.assertTrue(any('uno/igual.txt' in x for x in refs));self.assertTrue(any('dos/igual.txt' in x for x in refs))

    def test_resumen_distingue_la_procedencia_ademas_del_id(self):
        d=T.indexar(T.crear(self.paths)['id'],False)
        r=R.resumir(d['id'],solicitar=lambda *_a,**_k:{'models':[]})
        self.assertTrue(r['ok']);self.assertEqual(len(set(x['referencia'] for x in r['refs'])),2)
        self.assertIn('uno/igual.txt',r['texto']);self.assertIn('dos/igual.txt',r['texto'])

    def test_ruta_relativa_mostrada_sirve_como_referencia_de_seguimiento(self):
        d=T.indexar(T.crear(self.paths)['id'],True,embedding=lambda t,m:[0.,1.] if 'DUP_A' in t else [1.,0.])
        relativa=self.paths[0].relative_to(T.L.RAIZ)
        r=T.buscar(d['id'],f'Consulta "{relativa}" aunque el otro documento hable de Android.',embedding=lambda *_:[1.,0.])
        self.assertIn('DUP_A',r['trozos'][0]['texto'])


if __name__=='__main__':unittest.main()
