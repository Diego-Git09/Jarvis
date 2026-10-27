import re,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import ayuda_jarvis as A
import ayuda_simple as S
import accesos_jarvis as C
import administracion_local as L
class Pruebas(unittest.TestCase):
    def test_temas_pasos_ejemplos_y_limites(self):
        for n in ['modelos','memoria','archivos','adjuntos','gpu','vocabulario','respaldos','externo']:
            t=A.ayuda(n);self.assertIn('1.',t);self.assertIn('2.',t);self.assertIn('Ejemplo:',t);self.assertIn('Límite:',t)
    def test_comandos_documentados_existen_en_catalogo(self):
        for t in [S.GENERAL,*S.TEMAS.values()]:
            for c in re.findall(r'(?<![\w/])(/[a-z_]+)\b',t):self.assertIn(c,C.ACCESOS,c)
    def test_catalogo_extenso_y_detalle_conservados(self):
        self.assertIn('/sincronizar',A.GENERAL);self.assertIn('/sincronizar estado',A.ayuda('memoria'));self.assertIn('backup',A.ayuda('memoria'))
        self.assertIn('/reemplazar',A.ayuda('archivos detalle'));self.assertIn('/recordatorios',A.ayuda('comandos'))
    def test_despacho_real_de_comandos_nuevos_sin_modelo(self):
        import respaldos_configuracion as R,politica_termica as T,metricas_modelos as M
        with tempfile.TemporaryDirectory() as tmp,patch.object(R,'DATOS',Path(tmp)),patch.object(T,'ARCHIVO',Path(tmp)/'umbrales'),patch.object(M,'ARCHIVO',Path(tmp)/'metricas'):
            for p in ['/respaldo listar','/modelo estadisticas','/temperatura gpu 75']:
                self.assertTrue(L.es_entrada(p,{}));hecho,t=L.comando(p,{},lambda _:False);self.assertTrue(hecho);self.assertTrue(t)
            self.assertFalse(T.ARCHIVO.exists())
if __name__=='__main__':unittest.main()
