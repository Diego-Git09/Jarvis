"""Planes reales con autorización única: secuencias, fallos y carreras."""
import unittest
from unittest.mock import patch
import prueba_proyectos_codigo as FIX
import jarvis_agente as J
import planes_archivos as P
from interfaz_jarvis import comando

class Pruebas(unittest.TestCase):
    def setUp(self):
        FIX.Pruebas.setUp(self);self.e={};self.h=[];self.llamadas=[]
        (self.work/'origen.txt').write_text('dato original\n')
    def si(self,t):self.permisos.append(t);return True
    def accion(self,n,a):
        self.llamadas.append(n)
        return J.ejecutar_herramienta(n,a,lambda _:self.fail('No debe pedir un segundo permiso'),self.e)
    def pedir(self,t,confirmar=None):return comando(t,self.h,self.e,self.accion,J.SISTEMA,confirmar_plan=confirmar or self.si)
    def test_dos_tres_y_cinco_pasos_un_permiso_cada_plan(self):
        for cantidad in [2,3,5]:
            self.permisos.clear();self.llamadas.clear()
            texto='/copiar origen.txt copia'+str(cantidad)+'.txt'
            anterior='copia'+str(cantidad)+'.txt'
            for k in range(cantidad-1):
                nuevo=f'final{cantidad}_{k}.txt';texto+=' y luego renómbralo a '+nuevo;anterior=nuevo
            ok,t=self.pedir(texto)
            self.assertTrue(ok);self.assertEqual((self.work/anterior).read_text(),'dato original\n')
            self.assertEqual(len(self.permisos),1);self.assertEqual(len(self.llamadas),cantidad)
            self.assertIn('--- /dev/null',self.permisos[0]);self.assertIn('Paso '+str(cantidad)+' comprobado',t)
    def test_carpeta_copia_reemplazo_usa_archivo_real(self):
        ok,t=self.pedir('/carpeta respaldo y luego /copiar origen.txt respaldo/dato.txt y luego /reemplazar respaldo/dato.txt original nuevo')
        self.assertTrue(ok);self.assertEqual((self.work/'respaldo/dato.txt').read_text(),'dato nuevo\n');self.assertEqual(len(self.permisos),1)
        self.assertIn('-dato original',self.permisos[0]);self.assertIn('+dato nuevo',self.permisos[0])
    def test_paso_ambiguo_no_ejecuta_el_primero(self):
        ok,t=self.pedir('/copiar origen.txt copia.txt y luego arregla eso')
        self.assertTrue(ok);self.assertFalse(self.llamadas);self.assertFalse(self.permisos);self.assertIn('Paso 2',t)
    def test_cancelacion_no_escribe(self):
        ok,t=self.pedir('/copiar origen.txt copia.txt y luego /mover copia.txt final.txt',lambda _:False)
        self.assertTrue(ok);self.assertFalse(self.llamadas);self.assertFalse((self.work/'copia.txt').exists())
    def test_fallo_segundo_detiene_y_ofrece_deshacer_primero(self):
        real=self.accion
        def fallar(n,a):
            if n=='mover_archivo':return {'ok':False,'error':'fallo inyectado, simulación'}
            return real(n,a)
        with patch.object(self,'accion',side_effect=fallar):ok,t=self.pedir('/copiar origen.txt copia.txt y luego /mover copia.txt final.txt y luego /copiar final.txt tercero.txt')
        self.assertTrue(ok);self.assertTrue((self.work/'copia.txt').exists());self.assertFalse((self.work/'tercero.txt').exists());self.assertIn('Paso 2 falló',t);self.assertIn('/deshacer_plan',t)
        ok,t=self.pedir('/deshacer_plan');self.assertTrue(ok);self.assertFalse((self.work/'copia.txt').exists());self.assertIn('comprobado',t)
    def test_cambio_tras_permiso_cancela_sin_sobrescribir(self):
        def cambio(t):self.permisos.append(t);(self.work/'origen.txt').write_text('CAMBIO EXTERNO');return True
        ok,t=self.pedir('/copiar origen.txt copia.txt y luego /mover copia.txt final.txt',cambio)
        self.assertTrue(ok);self.assertFalse((self.work/'copia.txt').exists());self.assertIn('cambió',t)
    def test_una_peticion_que_parece_doble_preserva_literal(self):
        (self.work/'dato y luego otro.txt').write_text('LITERAL')
        def individual(n,a):return J.ejecutar_herramienta(n,a,self.si,self.e)
        with patch.object(self,'accion',side_effect=individual):
            ok,t=self.pedir('/copiar "dato y luego otro.txt" "otro.txt"',lambda _:self.fail('Es una acción individual'))
        # La ruta individual utiliza el permiso normal, no un permiso de plan.
        self.assertTrue(ok);self.assertEqual((self.work/'otro.txt').read_text(),'LITERAL');self.assertEqual(len(self.permisos),1)
    def test_no_acepta_otra_accion_en_el_ambito_autorizado(self):
        p=P.preparar(['/copiar origen.txt copia.txt','/mover copia.txt final.txt'])[0]
        with P.autorizacion(p):
            r=J.ejecutar_herramienta('copiar_archivo',{'origen':'origen.txt','destino':'intruso.txt'},self.si,self.e)
        self.assertFalse(r['ok']);self.assertFalse((self.work/'intruso.txt').exists());self.assertFalse(self.permisos)
    def test_deshacer_no_borra_un_archivo_modificado(self):
        self.pedir('/copiar origen.txt copia.txt y luego /mover copia.txt final.txt')
        (self.work/'final.txt').write_text('CONSERVAR')
        ok,t=self.pedir('/deshacer_plan');self.assertTrue(ok);self.assertIn('Me detuve',t);self.assertEqual((self.work/'final.txt').read_text(),'CONSERVAR')

if __name__=='__main__':unittest.main()
