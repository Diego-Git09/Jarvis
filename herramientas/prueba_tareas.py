import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import tareas_jarvis as T
from interfaz_local import comando_local
import configuracion_jarvis as C


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.ruta=self.base/'tareas.json'
        self.addCleanup(self.temp.cleanup)

    def test_ciclo_reversible_y_no_duplica_otros_datos(self):
        t=T.anotar('comprar leche',self.ruta)
        self.assertEqual(T.listar(self.ruta)[0]['texto'],'comprar leche')
        self.assertTrue(T.marcar(t['id'],True,self.ruta)['hecha'])
        self.assertFalse(T.marcar(t['id'],False,self.ruta)['hecha'])
        self.assertEqual(len(T.listar(self.ruta)),1)
        self.assertEqual(self.ruta.stat().st_mode&0o777,0o600)

    def test_corrupto_no_se_sobrescribe(self):
        self.ruta.write_text('{roto')
        with self.assertRaises(ValueError):T.anotar('otra',self.ruta)
        self.assertEqual(self.ruta.read_text(),'{roto')

    def test_limites_y_id_inexistente_no_escriben(self):
        for texto in ['', 'x'*1001]:
            with self.assertRaises(ValueError):T.anotar(texto,self.ruta)
        self.assertFalse(self.ruta.exists())
        t=T.anotar('primera',self.ruta);antes=self.ruta.read_text()
        with self.assertRaises(ValueError):T.marcar('no existe',True,self.ruta)
        self.assertEqual(self.ruta.read_text(),antes)

    def test_numeros_visibles_y_no_ids_en_pantalla(self):
        t=T.anotar('Comprar leche',self.ruta)
        estado={}
        with patch('interfaz_local.T.listar',return_value=[t]),patch('interfaz_local.T.marcar',return_value=dict(t,hecha=True)) as marcar:
            _,texto=comando_local('/tareas',[],estado,lambda _:True,dict(C.DEFAULT),lambda:None,None)
            self.assertNotIn(t['id'],texto)
            _,texto=comando_local('/hecho 1',[],estado,lambda _:True,dict(C.DEFAULT),lambda:None,None)
            marcar.assert_called_once_with(t['id'],True)
            self.assertIn('completada',texto)


if __name__=='__main__':unittest.main()
