"""Auditoría sin credenciales reales: metadatos no prueban identidad ni validez."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import auditar_clave_zen_r5 as A
import externo_zen as Z


class Pruebas(unittest.TestCase):
    def test_ningun_valor_ni_huella_sale_y_no_modifica(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'zen.key';p.write_text('ficticio-auditoria-nunca-real');p.chmod(0o600)
            antes=p.stat();contenido=p.read_bytes()
            with patch.dict('os.environ',{},clear=True):r=A.auditar(p,Path(tmp))
            self.assertNotIn(contenido.decode(),json.dumps(r));self.assertNotIn('sha256',json.dumps(r))
            self.assertEqual(contenido,p.read_bytes());self.assertEqual(antes.st_mtime_ns,p.stat().st_mtime_ns)
            self.assertIn('desconocida',r['clasificacion']);self.assertFalse(r['servicio_consultado'])
            self.assertIn('No atribuible',r['autor']);self.assertEqual(r['permisos'],'0o600')

    def test_coincidencia_de_prueba_atribuye_valor_no_persona(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p=d/'zen.key';p.write_text('ficticio-auditoria-nunca-real');p.chmod(0o600)
            (d/'prueba_ejemplo.py').write_text("DATO='ficticio-auditoria-nunca-real'\n")
            r=A.auditar(p,d)
            self.assertIn('ficticio',r['clasificacion']);self.assertEqual(r['coincidencias_con_literal_de_prueba'],[{'archivo':'prueba_ejemplo.py','linea':1}])

    def test_rechaza_enlace_y_permisos_abiertos_sin_leer(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p=d/'real';p.write_text('sin-lectura');p.chmod(0o644)
            (d/'enlace').symlink_to(p)
            for ruta in (p,d/'enlace'):
                with self.subTest(ruta=ruta):
                    r=A.auditar(ruta,d);self.assertIn('no se leyó',r['clasificacion'])

    def test_estado_no_afirma_validez_y_cero_red(self):
        with patch.object(Z,'clave',return_value='ficticio-nunca-real'),patch.object(Z,'transporte',side_effect=AssertionError('Sin red')):
            ok,t=Z.comando('/externo estado',lambda _:self.fail('Solo lectura'))
        self.assertTrue(ok);self.assertIn('autenticidad y origen sin verificar',t)
        self.assertNotIn('ficticio-nunca-real',t)


if __name__=='__main__':unittest.main()
