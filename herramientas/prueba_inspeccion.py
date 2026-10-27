import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import herramientas_lectura as L
import inspeccion_archivos as I
from interfaz_archivos import comando_archivos


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.patch=patch.object(L,'RAIZ',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.log=patch.object(L,'_registrar');self.log.start();self.addCleanup(self.log.stop)

    def test_info_texto_y_binario_con_fecha_real(self):
        (self.root/'nota.txt').write_text('hola\n')
        r=I.informacion_archivo('nota.txt')
        self.assertTrue(r['ok']);self.assertEqual(r['bytes'],5);self.assertTrue(r['texto_utf8']);self.assertIn('+00:00',r['modificado'])
        (self.root/'foto.bin').write_bytes(b'\x00\x01')
        self.assertFalse(I.informacion_archivo('foto.bin')['texto_utf8'])
        self.assertFalse(I.informacion_archivo('noexiste')['ok'])

    def test_muestra_parcial_utf8_no_corta_un_caracter(self):
        (self.root/'largo.txt').write_text('x'*19999+'á'*2000)
        r=I.informacion_archivo('largo.txt')
        self.assertTrue(r['texto_utf8']);self.assertTrue(r['muestra_parcial'])

    def test_comparar_conserva_archivos_y_salto_final(self):
        a=self.root/'a.txt';b=self.root/'b.txt';a.write_text('uno\ndos\n');b.write_text('uno\ntres')
        r=I.comparar_archivos('a.txt','b.txt')
        self.assertTrue(r['ok']);self.assertFalse(r['iguales']);self.assertIn('-dos',r['diferencia']);self.assertIn('+tres',r['diferencia'])
        self.assertTrue(r['salto_final_primero']);self.assertFalse(r['salto_final_segundo'])
        self.assertEqual(a.read_text(),'uno\ndos\n');self.assertEqual(b.read_text(),'uno\ntres')
        self.assertTrue(I.comparar_archivos('a.txt','a.txt')['iguales'])

    def test_comparacion_rechaza_binarios_grandes_y_fuera(self):
        (self.root/'bin').write_bytes(b'\0');(self.root/'grande').write_bytes(b'x'*100001);(self.root/'normal').write_text('texto')
        for nombre in ('bin','grande','../fuera'):
            self.assertFalse(I.comparar_archivos(nombre,'normal')['ok'])

    def test_buscar_nombres_comodines_y_enlaces(self):
        (self.root/'sub').mkdir();(self.root/'sub'/'Mi Nota.md').write_text('texto');(self.root/'otro.txt').write_text('texto')
        (self.root/'alias.md').symlink_to(self.root/'otro.txt')
        r=I.encontrar_archivos('nota')
        self.assertEqual([m['ruta'] for m in r['archivos']],['sub/Mi Nota.md'])
        self.assertEqual(len(I.encontrar_archivos('*.MD')['archivos']),1)
        self.assertFalse(I.encontrar_archivos('','.')['ok'])
        self.assertFalse(I.encontrar_archivos('*','otro.txt')['ok'])

    def test_busqueda_acotada_y_consola(self):
        for i in range(55):(self.root/f'{i:02}.txt').write_text('x')
        r=I.encontrar_archivos('*.txt');self.assertEqual(len(r['archivos']),50);self.assertTrue(r['limite_alcanzado'])
        funcs={'informacion_archivo':I.informacion_archivo,'comparar_archivos':I.comparar_archivos,'encontrar_archivos':I.encontrar_archivos}
        handled,texto=comando_archivos('/info 00.txt',[],{},lambda n,a:funcs[n](**a))
        self.assertTrue(handled);self.assertIn('Chile',texto)
        handled,texto=comando_archivos('/encontrar "*.txt"',[],{},lambda n,a:funcs[n](**a))
        self.assertIn('Búsqueda acotada',texto)


if __name__=='__main__':unittest.main()
