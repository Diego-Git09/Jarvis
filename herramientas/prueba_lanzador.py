import fcntl
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name);self.bin=self.base/'bin';self.bin.mkdir()
        self.addCleanup(self.temp.cleanup)
        self.trace=self.base/'trace.txt';self.runtime=self.base/'runtime';self.runtime.mkdir()
        self.env=dict(os.environ,PATH=str(self.bin),XDG_RUNTIME_DIR=str(self.runtime),JARVIS_DIR=str(self.base/'Jarvis'),JARVIS_LAUNCH_TRACE=str(self.trace))
        for nombre,contenido in [('python3','#!/bin/sh\nexit 1\n'),('notify-send','#!/bin/sh\necho "aviso $*" >> "$JARVIS_LAUNCH_TRACE"\n'),
                                 ('ptyxis','#!/bin/sh\necho "terminal $*" >> "$JARVIS_LAUNCH_TRACE"\n')]:
            p=self.bin/nombre;p.write_text(contenido);p.chmod(0o755)
        (self.bin/'flock').symlink_to(shutil.which('flock'))

    def test_ollama_caido_abre_terminal_igualmente(self):
        p=subprocess.run(['/bin/bash',str(Path(__file__).with_name('abrir_jarvis.sh'))],env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        texto=self.trace.read_text();self.assertIn('Ollama no responde',texto);self.assertIn('terminal --new-window',texto)

    def test_candado_impide_ventana_duplicada(self):
        with open(self.runtime/'jarvis.lock','w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            p=subprocess.run(['/bin/bash',str(Path(__file__).with_name('abrir_jarvis.sh'))],env=self.env,capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        texto=self.trace.read_text();self.assertIn('ya está abierto',texto);self.assertNotIn('terminal',texto)


if __name__=='__main__':unittest.main()
