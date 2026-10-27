"""Fechas, persistencia, permisos y concurrencia: nunca usa recordatorios reales."""
import concurrent.futures
import json
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
import recordatorios_jarvis as R
import interfaz_recordatorios as I
import jarvis_agente as J
from instalar_recordatorios import instalar


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ruta=Path(self.tmp.name)/'recordatorios.json'
        self.p=patch.object(R,'ARCHIVO',self.ruta);self.p.start();self.addCleanup(self.p.stop)

    def test_fecha_chilena_natural_iso_relativa_y_siempre(self):
        base=datetime(2026,10,13,15,30,tzinfo=R.ZONA)
        for expresion,esperado in [('mañana a las 9','2026-10-14T09:00:00-03:00'),('14/10/2026 18:30','2026-10-14T18:30:00-03:00'),
                                   ('14 de octubre de 2026 a las 6 pm','2026-10-14T18:00:00-03:00'),('en 2 horas','2026-10-13T17:30:00-03:00'),
                                   ('jueves','2026-10-15T09:00:00-03:00'),('2026-10-14','2026-10-14T09:00:00-03:00')]:
            with self.subTest(fecha=expresion):self.assertEqual(R.interpretar_fecha(expresion,base),esperado)
        self.assertIsNone(R.interpretar_fecha('siempre',base))
        for mala in ('31/02/2026','mañana a las 25:00','algún día','en 0 horas'):
            with self.subTest(fecha=mala),self.assertRaises(ValueError):R.interpretar_fecha(mala,base)

    def test_horario_inexistente_por_cambio_de_hora_no_se_inventa(self):
        with self.assertRaises(ValueError):R.interpretar_fecha('06/09/2026 00:30')

    def test_panel_muestra_vencidos_y_siempre_pero_no_futuros(self):
        base=datetime(2026,10,13,15,30,tzinfo=R.ZONA)
        a=R.crear('Permanente');b=R.crear('Vencido','13/10/2026 14:00');R.crear('Futuro','14/10/2026 09:00')
        self.assertEqual({r['id'] for r in R.visibles(R.listar(),base)},{a['id'],b['id']})

    def test_editar_posponer_completar_y_eliminar_persisten(self):
        a=R.crear('Texto');a=R.modificar(a['id'],texto='Nuevo',fecha='14/10/2026 09:00',esperado=R.revision(a))
        self.assertEqual(R.listar()[0]['texto'],'Nuevo');self.assertEqual(os.stat(self.ruta).st_mode&0o777,0o600)
        a=R.modificar(a['id'],fecha='siempre',esperado=R.revision(a));self.assertIsNone(a['fecha'])
        R.modificar(a['id'],estado='hecho');self.assertFalse(R.listar())
        R.modificar(a['id'],estado='activo');self.assertEqual(len(R.listar()),1)
        R.modificar(a['id'],estado='eliminado');self.assertFalse(R.listar())
        self.assertEqual(R.listar(True)[0]['estado'],'eliminado')

    def test_revision_impide_editar_numero_obsoleto(self):
        a=R.crear('Texto');viejo=R.revision(a);R.modificar(a['id'],texto='Cambió desde escritorio')
        with self.assertRaises(ValueError):R.modificar(a['id'],texto='No pisar',esperado=viejo)
        self.assertEqual(R.listar()[0]['texto'],'Cambió desde escritorio')

    def test_escrituras_simultaneas_no_pierden_recordatorios(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda n:R.crear(f'Nota {n}'),range(24)))
        self.assertEqual(len(R.listar()),24)

    def test_archivo_corrupto_no_se_sobrescribe(self):
        self.ruta.write_text('{roto')
        with self.assertRaises(ValueError):R.crear('Nuevo')
        self.assertEqual(self.ruta.read_text(),'{roto')

    def test_frase_del_usuario_crea_y_guarda_fecha_sin_modelo(self):
        estado={};permisos=[]
        hecho,texto=I.comando('Jarvis recuérdame comprar pan mañana a las 9',estado,lambda p:permisos.append(p) or True)
        self.assertTrue(hecho);self.assertEqual(R.listar()[0]['texto'],'comprar pan');self.assertIn('09:00',permisos[0]);self.assertIn('guardado',texto)
        self.assertIsNotNone(R.listar()[0]['fecha'])

    def test_seleccion_por_lista_y_rechazo_no_cambia_datos(self):
        R.crear('Pan');R.crear('Café');estado={};I.comando('/recordatorios',estado,lambda _:True)
        hecho,texto=I.comando('elimina el recordatorio 2',estado,lambda _:False)
        self.assertTrue(hecho);self.assertEqual(len(R.listar()),2);self.assertIn('conservé',texto)
        I.comando('modifica el recordatorio 1 comprar más pan siempre',estado,lambda _:True)
        self.assertEqual(R.listar()[0]['texto'],'comprar más pan')
        self.assertEqual(estado['_recordatorios_visibles'][1],(R.listar()[0]['id'],R.revision(R.listar()[0])))

    def test_no_interpreta_memorias_negaciones_o_ejemplos_como_creacion(self):
        for p in ('recuerda que soy Diego','no me recuerdes comprar pan','cómo puedo crear un recordatorio','por ejemplo recuérdame comprar pan'):
            self.assertFalse(I.comando(p,{},lambda _:self.fail('No es una orden'))[0])
        self.assertFalse(R.listar())

    def test_herramientas_modelo_validan_numeros_y_conservan_foco(self):
        estado={};r=J.ejecutar_herramienta('crear_recordatorio',{'texto':'Pan'},lambda _:True,estado)
        self.assertTrue(r['ok'])
        self.assertFalse(J.ejecutar_herramienta('modificar_recordatorio',{'numero':'1','texto':'No'},lambda _:True,estado)['ok'])
        self.assertTrue(J.ejecutar_herramienta('modificar_recordatorio',{'fecha':'siempre','texto':'Pan y café'},lambda _:True,estado)['ok'])
        nombres={h['function']['name'] for h in J.herramientas_para_turno([{'role':'user','content':'Recuérdame tomar agua'}])}
        self.assertIn('crear_recordatorio',nombres);self.assertNotIn('buscar_web',nombres)

    def test_instalacion_aislada_y_acceso_sin_pedir_administrador(self):
        base=Path(self.tmp.name)
        with patch('instalar_recordatorios.subprocess.run'):
            a,b=instalar(base/'config',base/'escritorio')
        self.assertIn('--iniciar',a.read_text());self.assertIn('--gestionar',b.read_text())
        self.assertEqual(os.stat(b).st_mode&0o777,0o755)


if __name__=='__main__':unittest.main()
