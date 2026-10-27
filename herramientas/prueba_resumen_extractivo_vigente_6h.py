"""Los extractos guardados conservan las comprobaciones de versión/ruta/huella."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tandas_documentales as T
import resumen_documental as R


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        patch.object(T,'RAIZ',self.base/'indice').start()

    def tanda(self,version=None):
        p=self.base/'fuente.txt';p.write_text('EXTRACTO_ORO_FICTICIO_73. Cantidad 731.')
        if version is None:d=T.indexar(T.crear([p])['id'],False)
        else:
            with patch.object(T,'LECTOR_VERSION',version):d=T.indexar(T.crear([p])['id'],False)
        return d,p

    def resumen(self,d):return T.comando('/resumir tanda',{'_tanda_documentos':d['id']})[1]

    def test_fuente_actual_conserva_el_extracto(self):
        d,p=self.tanda();antes=p.read_bytes();r=self.resumen(d)
        self.assertIn('EXTRACTO_ORO_FICTICIO_73',r);self.assertIn('extractivos',r);self.assertEqual(p.read_bytes(),antes)

    def test_indice_anterior_no_devuelve_el_extracto(self):
        d,_=self.tanda(9);r=self.resumen(d)
        self.assertFalse('EXTRACTO_ORO_FICTICIO_73' in r);self.assertIn('/indexar',r)

    def test_original_borrado_no_devuelve_copia_de_contenido(self):
        d,p=self.tanda();p.unlink();r=self.resumen(d)
        self.assertFalse('EXTRACTO_ORO_FICTICIO_73' in r);self.assertIn('/indexar',r)

    def test_original_cambiado_con_igual_firma_no_devuelve_el_extracto(self):
        d,p=self.tanda();st=p.stat();p.write_text(p.read_text().replace('731','419'));os.utime(p,ns=(st.st_atime_ns,st.st_mtime_ns));r=self.resumen(d)
        self.assertFalse('EXTRACTO_ORO_FICTICIO_73' in r);self.assertIn('/indexar',r)

    def test_original_revocado_no_devuelve_el_extracto(self):
        d,p=self.tanda();original=T.L._resolver
        def resolver(ruta):
            if str(ruta)==str(p):raise T.L.FueraDeAlcance('Revocación sintética')
            return original(ruta)
        with patch.object(T.L,'_resolver',side_effect=resolver):r=self.resumen(d)
        self.assertFalse('EXTRACTO_ORO_FICTICIO_73' in r);self.assertIn('/indexar',r)

    def test_otro_original_vigente_sigue_disponible(self):
        a=self.base/'a.txt';b=self.base/'b.txt';a.write_text('ORO_NO_VIGENTE_71');b.write_text('ORO_VIGENTE_49')
        d=T.indexar(T.crear([a,b])['id'],False);a.unlink();r=self.resumen(d)
        self.assertFalse('ORO_NO_VIGENTE_71' in r);self.assertIn('ORO_VIGENTE_49',r)

    def test_manifiesto_anterior_no_repite_avisos_derivados_del_contenido(self):
        d,_=self.tanda(9);d['archivos'][0]['aviso']='CONTENIDO_ANTIGUO_FICTICIO_73'
        r=T.manifiesto(d);self.assertFalse('CONTENIDO_ANTIGUO_FICTICIO_73' in r);self.assertIn('/indexar',r)

    def test_resumen_generado_tambien_rechaza_indice_anterior_antes_del_modelo(self):
        d,_=self.tanda(9)
        def prohibido(*_a,**_k):raise AssertionError('No consultar modelo con índice anterior.')
        r=R.resumir(d['id'],solicitar=prohibido)
        self.assertFalse(r['ok']);self.assertFalse('EXTRACTO_ORO_FICTICIO_73' in r['texto'])


if __name__=='__main__':unittest.main()
