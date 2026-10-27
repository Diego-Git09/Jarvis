import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import aislamiento_pruebas as A

class Pruebas(unittest.TestCase):
    def test_escrituras_python_se_bloquean_antes_de_crear(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'real'
            with patch.object(A,'REALES',(p,)):
                with self.assertRaises(RuntimeError):p.mkdir()
            self.assertFalse(p.exists())
    def test_red_real_bloqueada_y_servidor_falso_distinto_permitido(self):
        for host in ['127.0.0.1','::1','::ffff:127.0.0.1','localhost']:
            with self.assertRaises(RuntimeError):A.comprobar_evento('socket.connect',(None,(host,8765)))
        A.comprobar_evento('socket.connect',(None,('127.0.0.1',42123)))
    def test_no_conecta_el_mcp_real_aunque_se_cambie_en_pruebas(self):
        with socket.socket() as s,self.assertRaises(RuntimeError):s.connect(('127.0.0.1',8765))
    def test_sqlite_nativo_no_abre_datos_reales(self):
        p=Path(__file__).resolve().parents[1]/'datos/.aislamiento-no-crear.sqlite'
        with self.assertRaises(RuntimeError):sqlite3.connect(str(p))
        self.assertFalse(p.exists())
    def test_movimientos_enlaces_y_truncado(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'real';p.mkdir();f=p/'dato';f.write_text('original')
            with patch.object(A,'REALES',(p,)):
                for evento,args in [('os.rename',(str(f),str(p/'otro'),-1,-1)),('os.link',(str(f),str(Path(d)/'enlace'),-1,-1)),('os.truncate',(str(f),0))]:
                    with self.assertRaises(RuntimeError):A.comprobar_evento(evento,args)
            self.assertEqual(f.read_text(),'original')
    def test_simbolo_hacia_datos_reales_se_resuelve_antes_de_escribir(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'real').mkdir();(p/'enlace').symlink_to(p/'real',target_is_directory=True)
            with patch.object(A,'REALES',(p/'real',)):
                with self.assertRaises(RuntimeError):(p/'enlace/archivo').write_text('no')
            self.assertFalse((p/'real/archivo').exists())
    def test_modulo_importado_con_otras_rutas_aborta(self):
        import entorno_jarvis
        with tempfile.TemporaryDirectory() as d,patch.object(entorno_jarvis,'DATOS',Path.home()/'Jarvis/datos'),self.assertRaises(RuntimeError):A.verificar_previo(d)
    def test_temporal_correcto_y_raiz_real_rechazada(self):
        import entorno_jarvis
        self.assertTrue(A.verificar_previo(entorno_jarvis.PROYECTO)['guarda_instalada'])
        with self.assertRaises(RuntimeError):A.verificar_previo(Path.home()/'Jarvis')
    def test_proceso_nativo_no_escribe_datos_reales(self):
        p=Path(__file__).resolve().parents[1]/'datos/.aislamiento-r4-no-crear'
        self.assertFalse(p.exists())
        r=subprocess.run(['/bin/sh','-c','printf prueba > "$1"','prueba',str(p)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertFalse(p.exists())
    def test_ejecutor_declara_aislamiento_nativo(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'probe.py';p.write_text('from pathlib import Path\nPath(__file__).with_name("temporal").write_text("ok")\nprint("OK")\n')
            env=dict(os.environ,JARVIS_DIR=d,JARVIS_PRUEBAS='1')
            r=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('ejecutar_prueba_aislada.py')),str(p)],env=env,text=True,capture_output=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertIn('OK',r.stdout)

if __name__=='__main__':unittest.main()
