"""Verifica la política de carga del índice instalado, sin llamar a Ollama."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

RUTA=Path.home()/'SegundoCerebro'/'indice_semantico.py'


@unittest.skipUnless(RUTA.exists(),'Índice externo no instalado en este equipo')
class Pruebas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('indice_instalado',RUTA);cls.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.mod)

    def test_keep_alive_por_defecto_sin_mutar_payload(self):
        payload={'model':'modelo','input':'dato'}
        with patch.object(self.mod.urllib.request,'urlopen',return_value=io.BytesIO(b'{}')) as abrir:self.mod.api('embed',payload)
        self.assertEqual(json.loads(abrir.call_args.args[0].data)['keep_alive'],'5s')
        self.assertNotIn('keep_alive',payload)

    def test_keep_alive_explicito_se_respeta(self):
        with patch.object(self.mod.urllib.request,'urlopen',return_value=io.BytesIO(b'{}')) as abrir:self.mod.api('embed',{'model':'modelo','keep_alive':0})
        self.assertEqual(json.loads(abrir.call_args.args[0].data)['keep_alive'],0)


if __name__=='__main__':unittest.main()
