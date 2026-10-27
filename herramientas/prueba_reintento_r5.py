"""Un diagnóstico intermedio no sustituye la petición que quedó fallida."""
import unittest
import hilo_conversacion as H

class Pruebas(unittest.TestCase):
    def test_diez_consultas_o_ajustes_conservan_el_fallo_real(self):
        for p in ('/modelo','/modelos','/diagnostico','/contexto','/contexto 4096','/gpu cpu','/liberar','/reposo 1m','/timeout 120','/rendimiento'):
            with self.subTest(p=p):
                e={};H.iniciar_turno(e,'que significa 77 C');H.terminar_turno(e,'que significa 77 C','Una explicación antigua.')
                H.iniciar_turno(e,'q es una variable');H.terminar_turno(e,'q es una variable','Carga detenida.',fallido=True)
                H.iniciar_turno(e,p);H.terminar_turno(e,p,'Resultado comprobado del comando.')
                r=H.iniciar_turno(e,'reintenta')
                self.assertTrue(r['reintento']);self.assertEqual(r['pedido'],'q es una variable')

    def test_un_fallo_despues_de_una_accion_sigue_bloqueado(self):
        e={};H.iniciar_turno(e,'crea ejemplo.txt');H.terminar_turno(e,'crea ejemplo.txt','Fallo después del intento.',fallido=True,hubo_acciones=True)
        H.iniciar_turno(e,'/modelo');H.terminar_turno(e,'/modelo','Modelo actual.')
        r=H.iniciar_turno(e,'reintenta');self.assertFalse(r['reintento']);self.assertIn('/cambios',r['aclaracion'])

    def test_una_respuesta_nueva_con_contenido_no_resucita_el_fallo(self):
        e={};H.iniciar_turno(e,'que es una variable');H.terminar_turno(e,'que es una variable','Fallo.',fallido=True)
        H.iniciar_turno(e,'que es una API');H.terminar_turno(e,'que es una API','Una explicación actual.')
        self.assertIsNone(e['_hilo_conversacion']['fallido'])

if __name__=='__main__':unittest.main()
