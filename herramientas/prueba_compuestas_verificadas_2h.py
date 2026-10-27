"""Secuencias reales en carpetas temporales, permisos y parada por estado comprobado."""
import unittest
from unittest.mock import patch
import prueba_proyectos_codigo as FIX
import jarvis_agente as J
import ordenes_compuestas as O
from interfaz_jarvis import comando


class Pruebas(unittest.TestCase):
    def setUp(self):
        FIX.Pruebas.setUp(self);self.h=[];self.estado={};self.llamadas=[]
        (self.work/'origen.txt').write_text('contenido sintético\n')

    def si(self,texto):self.permisos.append(texto);return True

    def pedir(self,p,autorizar=True):
        def ejecutar(n,a):
            self.llamadas.append((n,a));return J.ejecutar_herramienta(n,a,self.si if autorizar else lambda _:False,self.estado)
        return comando(p,self.h,self.estado,ejecutar,J.SISTEMA)

    def test_copia_y_pronombre_renombra_destino_comprobado(self):
        ok,t=self.pedir('copia origen.txt a copia.txt y luego renómbralo a final.txt')
        self.assertTrue(ok);self.assertEqual((self.work/'final.txt').read_text(),'contenido sintético\n')
        self.assertTrue((self.work/'origen.txt').exists());self.assertFalse((self.work/'copia.txt').exists())
        self.assertEqual([n for n,a in self.llamadas],['copiar_archivo','mover_archivo']);self.assertEqual(len(self.permisos),2)

    def test_destino_existente_no_permite_segundo_paso(self):
        (self.work/'copia.txt').write_text('CONSERVAR')
        ok,t=self.pedir('copia origen.txt a copia.txt y luego renómbralo a final.txt')
        self.assertTrue(ok);self.assertIn('Me detuve',t);self.assertEqual(len(self.llamadas),1)
        self.assertEqual((self.work/'copia.txt').read_text(),'CONSERVAR');self.assertFalse((self.work/'final.txt').exists())

    def test_permiso_denegado_no_encadena(self):
        ok,t=self.pedir('copia origen.txt a copia.txt y luego renómbralo a final.txt',False)
        self.assertTrue(ok);self.assertEqual(len(self.llamadas),1);self.assertFalse((self.work/'copia.txt').exists());self.assertFalse((self.work/'final.txt').exists())

    def test_texto_leido_con_palabras_de_error_no_es_estado_de_error(self):
        (self.work/'origen.txt').write_text('No pude completar la tarea. No autorizaste el ejemplo.\n')
        ok,t=self.pedir('/leer origen.txt y luego /copiar origen.txt copia.txt')
        self.assertTrue(ok);self.assertTrue((self.work/'copia.txt').exists());self.assertNotIn('Me detuve',t)

    def test_uso_invalido_detiene_antes_de_copiar(self):
        ok,t=self.pedir('/copiar origen.txt y luego /copiar origen.txt copia.txt')
        self.assertTrue(ok);self.assertFalse(self.llamadas);self.assertFalse((self.work/'copia.txt').exists());self.assertIn('Me detuve',t)

    def test_pronombre_no_reutiliza_otra_sesion_o_paso(self):
        ok,t=self.pedir('renómbralo a final.txt y luego /copiar origen.txt copia.txt')
        self.assertTrue(ok);self.assertFalse(self.llamadas);self.assertIn('No hay un archivo comprobado',t)

    def test_rutas_con_espacios_y_separador_citado(self):
        (self.work/'origen y luego dato.txt').write_text('LITERAL')
        ok,t=self.pedir('copia "origen y luego dato.txt" a "copia con espacios.txt" y luego renómbralo a "final con espacios.txt"')
        self.assertTrue(ok);self.assertEqual((self.work/'final con espacios.txt').read_text(),'LITERAL')

    def test_sin_verificacion_no_pasa_al_siguiente(self):
        llamadas=[]
        def ejecutar(n,a):llamadas.append(n);return {'ok':True,'verificado':False}
        ok,t=comando('/copiar origen.txt copia.txt y luego /mover copia.txt final.txt',[],{},ejecutar,J.SISTEMA)
        self.assertTrue(ok);self.assertEqual(llamadas,['copiar_archivo']);self.assertIn('Me detuve',t)

    def test_excepcion_no_pierde_recuento_de_pasos_hechos(self):
        veces=[]
        def accion(p):
            veces.append(p)
            if len(veces)==2:raise OSError('No mostrar detalles internos')
            return True,'Comprobado',True
        t=O.ejecutar(['uno','dos','tres'],accion)
        self.assertIn('Paso 1: Comprobado',t);self.assertIn('Paso 2:',t);self.assertEqual(veces,['uno','dos']);self.assertNotIn('detalles internos',t)


if __name__=='__main__':unittest.main()
