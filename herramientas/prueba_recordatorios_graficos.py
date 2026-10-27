"""Pruebas reales de Tk, con notas aisladas e invisibles y sin captura del usuario."""
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
import recordatorios_jarvis as R
from recordatorios_escritorio import PanelRecordatorios


@unittest.skipUnless(os.environ.get('JARVIS_UI_REAL')=='1','Requiere sesión gráfica explícita')
class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=patch.object(R,'ARCHIVO',Path(self.tmp.name)/'recordatorios.json');self.p.start();self.addCleanup(self.p.stop)
        self.root=tk.Tk();self.root.attributes('-alpha',0)
        self.addCleanup(self.cerrar)

    def cerrar(self):
        for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
        self.root.destroy()

    def test_tarjetas_texto_y_botones_caben_al_redimensionar(self):
        R.crear('Recordatorio de prueba muy largo que debe ajustarse a varias líneas sin perder su texto completo.')
        panel=PanelRecordatorios(self.root,True)
        for ancho,alto in ((330,250),(440,500),(700,600)):
            self.root.geometry(f'{ancho}x{alto}');self.root.update()
            tarjeta=panel.tarjetas.winfo_children()[0]
            acciones=next(w for w in tarjeta.winfo_children() if hasattr(w,'botones'))
            for b in acciones.botones:
                self.assertLessEqual(b.winfo_x()+b.winfo_width(),acciones.winfo_width()+1)
            texto=tarjeta.winfo_children()[0].cget('text');self.assertIn('sin perder su texto',texto)
        panel.plegar();self.root.update();self.assertFalse(panel.cuerpo.winfo_ismapped())
        panel.plegar();self.root.update();self.assertTrue(panel.cuerpo.winfo_ismapped())

    def test_fecha_vencida_aparece_sin_chat_y_una_fecha_futura_espera(self):
        R.crear('Después','2026-10-14T09:00:00-03:00')
        with patch.object(R,'ahora',return_value=datetime(2026,10,13,15,tzinfo=R.ZONA)):panel=PanelRecordatorios(self.root)
        self.root.update();self.assertEqual(len(panel.conocidos),0)
        with patch.object(R,'ahora',return_value=datetime(2026,10,14,10,tzinfo=R.ZONA)):panel.actualizar(False)
        self.root.update();self.assertEqual(len(panel.conocidos),1);self.assertEqual(self.root.state(),'normal')

    def test_editar_completar_y_eliminar_actualizan_tarjetas(self):
        item=R.crear('Prueba');panel=PanelRecordatorios(self.root,True);self.root.update()
        panel.cambiar(item,texto='Modificado');self.root.update();self.assertEqual(R.listar()[0]['texto'],'Modificado')
        item=R.listar()[0];panel.cambiar(item,estado='hecho');self.root.update();self.assertEqual(len(panel.conocidos),0)
        item=R.crear('Eliminar');panel.actualizar(False)
        with patch('recordatorios_escritorio.messagebox.askyesno',return_value=True):panel.eliminar(item)
        self.assertFalse(R.listar())

    def test_editor_separa_evento_anticipacion_y_fecha_de_aparicion(self):
        panel=PanelRecordatorios(self.root,True);panel.editar();self.root.update();e=panel.editor
        e['texto'].insert('1.0','Prueba de matemáticas');e['modo'].set('Evento con aviso anticipado')
        e['fecha'].set('20/10/2026 09:30');e['cantidad'].set('2');e['unidad'].set('días');self.root.update()
        self.assertIn('18/10/2026',e['calculo'].cget('text'));self.assertIn('20/10/2026',e['calculo'].cget('text'))
        e['guardar']();self.root.update();item=R.listar()[0]
        self.assertEqual(item['texto'],'Prueba de matemáticas');self.assertEqual(item['fecha'][:10],'2026-10-18');self.assertEqual(item['evento'][:10],'2026-10-20')


if __name__=='__main__':unittest.main()
