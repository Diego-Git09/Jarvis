"""Rutas externas autorizadas, escritura reversible y revocación real."""
import tempfile
import errno
import unittest
from pathlib import Path
from unittest.mock import patch
import acceso_archivos as A
import herramientas_lectura as L
import herramientas_escritura as E
import inspeccion_archivos as I


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.doc=self.base/'Documentos';self.doc.mkdir()
        p=patch.object(A,'ARCHIVO',self.base/'accesos.json');p.start();self.addCleanup(p.stop)

    def test_fuera_del_trabajo_requiere_carpeta_autorizada(self):
        nota=self.doc/'nota.txt';nota.write_text('hola')
        self.assertFalse(L.leer_archivo(str(nota))['ok']);A.autorizar(str(self.doc))
        r=L.leer_archivo(str(nota));self.assertTrue(r['ok']);self.assertEqual(r['ruta'],str(nota))
        self.assertEqual(L.listar_archivos(str(self.doc))['items'][0]['nombre'],'nota.txt')
        A.revocar(str(self.doc));self.assertFalse(L.leer_archivo(str(nota))['ok'])

    def test_edicion_externa_conserva_ruta_desde_propuesta_hasta_deshacer(self):
        A.autorizar(str(self.doc));nota=self.doc/'nota.txt';nota.write_text('hola\n')
        propuesta=E.proponer_edicion(str(nota),'hola mundo\n');self.assertTrue(propuesta['ok'])
        r=E.aplicar_edicion(propuesta['id_propuesta']);self.assertTrue(r['ok']);self.assertEqual(nota.read_text(),'hola mundo\n')
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado']);self.assertEqual(nota.read_text(),'hola\n')

    def test_copiar_mover_buscar_e_informacion_no_fallan_con_ruta_absoluta(self):
        A.autorizar(str(self.doc));nota=self.doc/'nota.txt';nota.write_text('contenido\n')
        r=E.copiar_archivo(str(nota),str(self.doc/'copia.txt'));self.assertTrue(r['ok'])
        r=E.mover_archivo(str(self.doc/'copia.txt'),str(self.doc/'final.txt'));self.assertTrue(r['ok'])
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['ok'])
        self.assertTrue(I.informacion_archivo(str(nota))['ok']);self.assertTrue(I.comparar_archivos(str(nota),str(self.doc/'copia.txt'))['iguales'])
        self.assertTrue(I.encontrar_archivos('nota',str(self.doc))['archivos'])
        self.assertEqual(L.buscar_texto('contenido',str(self.doc))['resultados'][0]['archivo'],str(self.doc/'copia.txt'))

    def test_revocar_impide_aplicar_propuesta_antigua(self):
        A.autorizar(str(self.doc));nota=self.doc/'nota.txt';nota.write_text('hola')
        p=E.proponer_edicion(str(nota),'adiós');A.revocar(str(self.doc))
        self.assertFalse(E.aplicar_edicion(p['id_propuesta'])['ok']);self.assertEqual(nota.read_text(),'hola')

    def test_enlace_hacia_carpeta_no_autorizada_y_secretos_se_rechazan(self):
        A.autorizar(str(self.doc));privado=self.base/'privado.txt';privado.write_text('no leer');(self.doc/'link').symlink_to(privado)
        self.assertFalse(L.leer_archivo(str(self.doc/'link'))['ok'])
        self.assertTrue(A.protegida(Path.home()/'.ssh'/'id_rsa'))
        with self.assertRaises(ValueError):A.autorizar('/')

    def test_copia_binaria_grande_por_bloques_y_mover_entre_discos_es_reversible(self):
        A.autorizar(str(self.doc));nota=self.doc/'archivo.bin';datos=b'\x00\x01\xff'*700000;nota.write_bytes(datos)
        r=E.copiar_archivo(str(nota),str(self.doc/'copia.bin'));self.assertTrue(r['verificado']);self.assertEqual((self.doc/'copia.bin').read_bytes(),datos)
        enlace=E.os.link
        def entre_discos(a,b):
            if not Path(a).name.startswith('.jarvis-'):raise OSError(errno.EXDEV,'otro disco')
            return enlace(a,b)
        with patch.object(E.os,'link',side_effect=entre_discos):
            r=E.mover_archivo(str(nota),str(self.doc/'destino.bin'));self.assertTrue(r['verificado'])
            self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado'])
        self.assertEqual(nota.read_bytes(),datos)


if __name__=='__main__':unittest.main()
