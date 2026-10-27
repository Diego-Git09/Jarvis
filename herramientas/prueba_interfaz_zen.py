"""Eventos Tk reales con datos temporales; nunca usa el proveedor real."""
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch
from interfaz_grafica import Aplicacion
import externo_zen as Z


@unittest.skipUnless(os.environ.get('JARVIS_UI_REAL')=='1','Requiere Tk real autorizado')
class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);p=Path(self.tmp.name)
        for nombre,valor in [('CLAVE',p/'privado/zen.key'),('ARCHIVO',p/'estado.json'),('AUDITORIA',p/'auditoria.jsonl')]:
            parche=patch.object(Z,nombre,valor);parche.start();self.addCleanup(parche.stop)
        parche=patch.dict(os.environ,{k:'' for k in ('OPENCODE_ZEN_API_KEY','OPENCODE_API_KEY','ZEN_API_KEY')});parche.start();self.addCleanup(parche.stop)
        self.root=tk.Tk();self.root.attributes('-alpha',0)
        with patch.object(Aplicacion,'_inicializar_estado',return_value=None):self.app=Aplicacion(self.root,None)
        self.root.geometry('760x650');self.root.update()
        self.panel=self.app.mostrar_zen();self.panel.win.attributes('-alpha',0);self.root.update()
        def cerrar():
            if self.panel.win.winfo_exists():self.panel.cerrar()
            for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
            self.root.destroy()
        self.addCleanup(cerrar)

    def test_boton_visible_y_panel_abre_sin_red_ni_activacion(self):
        self.assertEqual(self.app.boton_zen.cget('text'),'OpenCode API')
        self.assertTrue(self.app.boton_zen.winfo_ismapped())
        x=self.app.boton_zen.winfo_rootx()-self.root.winfo_rootx()
        self.assertGreaterEqual(x,0);self.assertLessEqual(x+self.app.boton_zen.winfo_width(),760)
        with patch.object(Z,'transporte') as red:
            self.assertIs(self.app.mostrar_zen(),self.panel)
        red.assert_not_called();self.assertFalse(Z.estado()['encendido'])
        self.assertIn('sin configurar',self.panel.estado.cget('text'));self.assertFalse(Z.ARCHIVO.exists())

    def test_estado_muestra_cliente_oficial_y_rechazo_real(self):
        Z.guardar(dict(Z.estado(),encendido=True,transporte='cliente_oficial',ultimo_error='OpenCode HTTP 403, FreeTierError'))
        self.panel.refrescar()
        t=self.panel.estado.cget('text')
        self.assertIn('Cliente oficial aislado',t);self.assertIn('FreeTierError',t)

    def test_clave_oculta_guardada_con_permiso_fuera_del_chat(self):
        clave='CLAVE_FICTICIA_UI_SIN_SERVICIO'
        previo=list(self.app.historial)
        self.assertEqual(self.panel.entrada.cget('show'),'*')
        self.panel.clave.set(clave)
        with patch('interfaz_zen.messagebox.askyesno',return_value=True):self.panel.boton_guardar.invoke()
        self.assertEqual(Z.clave(),clave);self.assertEqual(Z.CLAVE.stat().st_mode&0o777,0o600)
        self.assertEqual(self.panel.clave.get(),'');self.assertEqual(self.app.historial,previo)
        self.assertNotIn(clave,self.app.chat.get('1.0','end'));self.assertFalse(Z.estado()['encendido'])

    def test_rechazar_permiso_no_guarda_y_limpia_el_campo(self):
        self.panel.clave.set('CLAVE_FICTICIA_RECHAZADA')
        with patch('interfaz_zen.messagebox.askyesno',return_value=False):self.panel.guardar_clave()
        self.assertFalse(Z.CLAVE.exists());self.assertEqual(self.panel.clave.get(),'')

    def test_catalogo_en_hilo_no_recibe_historial_ni_adjuntos(self):
        listo=threading.Event();llamadas=[]
        self.app.pendientes=[{'texto':'DATO_LOCAL_NO_ENVIAR'}]
        def ejecutar(comando,confirmar):
            llamadas.append(comando);listo.set();return True,'Catálogo simulado listo.'
        with patch.object(Z,'comando',side_effect=ejecutar):
            self.panel.boton_catalogo.invoke();self.assertTrue(listo.wait(2))
            limite=time.monotonic()+2
            while self.panel.ocupado and time.monotonic()<limite:self.root.update();time.sleep(.02)
        self.assertEqual(llamadas,['/externo modelos actualizar'])
        self.assertFalse(self.panel.ocupado);self.assertIn('simulado',self.panel.aviso.cget('text'))
        self.assertEqual(self.app.pendientes,[{'texto':'DATO_LOCAL_NO_ENVIAR'}])

    def test_apagar_sigue_disponible_durante_consulta(self):
        soltar=threading.Event();iniciado=threading.Event();self.addCleanup(soltar.set)
        def esperar(*args):iniciado.set();soltar.wait(2);return True,'Consulta simulada terminada.'
        Z.guardar(dict(Z.estado(),encendido=True))
        with patch.object(Z,'comando',side_effect=esperar):
            self.panel.ejecutar('/externo modelos actualizar');self.assertTrue(iniciado.wait(1))
            self.assertEqual(str(self.panel.boton_apagar.cget('state')),'normal')
            self.panel.boton_apagar.invoke();self.assertFalse(Z.estado()['encendido']);soltar.set()

    def test_controles_completos_en_ventana_reducida(self):
        self.panel.win.geometry('540x480');self.root.update()
        for w in (self.panel.entrada,self.panel.boton_catalogo,self.panel.boton_encender,self.panel.boton_apagar):
            x=w.winfo_rootx()-self.panel.win.winfo_rootx();y=w.winfo_rooty()-self.panel.win.winfo_rooty()
            self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
            self.assertLessEqual(x+w.winfo_width(),self.panel.win.winfo_width())
            self.assertLessEqual(y+w.winfo_height(),self.panel.win.winfo_height())

    def test_cerrar_limpia_clave_y_no_admite_acciones_arbitrarias(self):
        with self.assertRaises(ValueError):self.panel.ejecutar('/externo evaluar modelo')
        self.panel.clave.set('CLAVE_FICTICIA_NO_GUARDADA');self.panel.cerrar()
        self.assertEqual(self.panel.clave.get(),'');self.assertFalse(Z.CLAVE.exists())

if __name__=='__main__':unittest.main()
