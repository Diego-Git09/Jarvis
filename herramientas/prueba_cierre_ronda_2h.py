"""El cierre no acredita éxito ni publica si falla la batería o su lectura final."""
from contextlib import ExitStack,redirect_stdout
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import cerrar_ronda_mejora as C
import estado_ia as E
import entorno_jarvis as ENTORNO
import cerebro_mcp as MCP


class Pruebas(unittest.TestCase):
    def contexto(self,carpeta,codigo=0):
        pila=ExitStack()
        self.addCleanup(pila.close)
        pila.enter_context(patch.object(ENTORNO,'en_pruebas',return_value=False))
        pila.enter_context(patch.object(ENTORNO,'REGISTROS',carpeta))
        pila.enter_context(patch.object(C.subprocess,'run',return_value=SimpleNamespace(returncode=codigo)))
        pila.enter_context(patch.object(E,'generar',return_value='Estado sintético'))
        cliente=pila.enter_context(patch.object(MCP,'ClienteCerebro'))
        publicar=pila.enter_context(patch.object(E,'publicar',return_value=[{'id':938,'verificado':True}]))
        return publicar,cliente

    def test_bateria_fallida_actualiza_estado_pero_no_publica(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()) as salida:
            publicar,_=self.contexto(Path(tmp),1)
            self.assertEqual(C.cerrar(publicar=True),1)
            publicar.assert_not_called()
            E.generar.assert_called_once()
            self.assertIn('Hay fallos',salida.getvalue())
            self.assertEqual(len(list(Path(tmp).rglob('pruebas_control_*.txt'))),1)

    def test_cierre_local_no_publica_sin_opcion_explicita(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()):
            publicar,cliente=self.contexto(Path(tmp))
            self.assertEqual(C.cerrar(),0)
            publicar.assert_not_called();cliente.assert_not_called()

    def test_publicacion_incierta_no_anuncia_exito(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()) as salida:
            publicar,_=self.contexto(Path(tmp))
            publicar.side_effect=ConnectionError('Lectura posterior no coincide')
            self.assertEqual(C.cerrar(publicar=True),1)
            self.assertIn('No se confirmó',salida.getvalue())
            self.assertNotIn('Resumen fijo actualizado',salida.getvalue())

    def test_exito_publica_una_vez_y_devuelve_id_comprobado(self):
        with tempfile.TemporaryDirectory() as tmp,redirect_stdout(io.StringIO()) as salida:
            publicar,cliente=self.contexto(Path(tmp))
            self.assertEqual(C.cerrar(publicar=True),0)
            publicar.assert_called_once_with(cliente.return_value)
            self.assertIn('ID: 938',salida.getvalue())

    def test_no_inicia_cierre_real_dentro_de_pruebas(self):
        with patch.object(ENTORNO,'en_pruebas',return_value=True),patch.object(C.subprocess,'run') as ejecutar:
            with self.assertRaisesRegex(ValueError,'pruebas aisladas'):C.cerrar(True)
            ejecutar.assert_not_called()


if __name__=='__main__':unittest.main()
