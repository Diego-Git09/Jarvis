"""Pruebas del Tk real con ventanas invisibles y clientes falsos.

Activa JARVIS_UI_REAL=1 en una sesión gráfica para comprobar los eventos nativos.
"""
import os
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
from interfaz_grafica import Aplicacion,PANEL


class InstanciaFalsa:
    def cerrar(self):pass


@unittest.skipUnless(os.environ.get('JARVIS_UI_REAL')=='1','Requiere una sesión gráfica explícita')
class Pruebas(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.withdraw();self.root.attributes('-alpha',0)
        with patch.object(Aplicacion,'_inicializar_estado',return_value=None):self.app=Aplicacion(self.root,InstanciaFalsa())
        self.win=self.app.ventana_memoria;self.win.attributes('-alpha',0)
        registros=[{'id':i,'titulo':f'Registro {i}','contenido':f'Texto íntegro {i}',
                    'tipo':'conversacion','fuente':'codex','proyecto':'sin_clasificar',
                    'creado':'2026-10-12T20:00:00+00:00'} for i in range(1,5)]
        self.app._poblar_estructura({'ok':True,'proyectos':[{'proyecto':'sin_clasificar','registros':registros},
                                                         {'proyecto':'Destino','registros':[]}]})
        self.win.deiconify();self.win.geometry('640x600');self.root.update()
        def cerrar():
            for job in self.root.tk.call('after','info'):self.root.after_cancel(job)
            self.root.destroy()
        self.addCleanup(cerrar)

    def test_controles_de_mover_no_se_cortan_al_redimensionar(self):
        for ancho,alto in ((560,420),(640,600),(1100,780)):
            self.win.geometry(f'{ancho}x{alto}');self.root.update()
            for widget in (self.app.boton_mover,self.app.proyecto_destino,self.app.estado_memoria):
                y=widget.winfo_rooty()-self.win.winfo_rooty()
                self.assertGreaterEqual(y,0)
                self.assertLessEqual(y+widget.winfo_height(),self.win.winfo_height()+1)
        self.assertGreater(float(self.app.arbol.xview()[1]),0)

    def test_acceso_api_antiguo_solo_avisa_y_no_lee_credenciales(self):
        with patch('interfaz_grafica.messagebox.showinfo') as aviso,patch('interfaz_grafica.J.IA.P.configuracion') as secreto,patch('interfaz_grafica.J.IA.preguntar_externa') as red:
            self.app.configurar_api(self.root);self.root.update()
        aviso.assert_called_once();self.assertIn('bloqueadas',aviso.call_args.args[1])
        secreto.assert_not_called();red.assert_not_called()
        self.assertEqual(ttk.Style().lookup('TEntry','fieldbackground'),PANEL)

    def test_ctrl_y_shift_seleccionan_varias_filas_y_muestran_sus_textos(self):
        arbol=self.app.arbol;ids=arbol.get_children()
        x,y,w,h=arbol.bbox(ids[0]);arbol.event_generate('<ButtonPress-1>',x=x+30,y=y+h//2)
        arbol.event_generate('<ButtonRelease-1>',x=x+30,y=y+h//2);self.root.update()
        arbol.see(ids[2]);self.root.update()
        x,y,w,h=arbol.bbox(ids[2]);arbol.event_generate('<ButtonPress-1>',x=x+30,y=y+h//2,state=1)
        arbol.event_generate('<ButtonRelease-1>',x=x+30,y=y+h//2,state=1);self.root.update()
        self.assertGreaterEqual(len(arbol.selection()),2)
        self.app._seleccionar_todos();self.root.update()
        self.assertEqual(len(self.app.registros_actuales),4)
        self.assertIn('4 registros seleccionados',self.app.titulo_detalle.cget('text'))

    def test_click_centro_del_selector_abre_la_lista(self):
        campo=self.app.proyecto_destino
        self.assertEqual(str(campo.cget('state')),'readonly')
        campo.event_generate('<ButtonPress-1>',x=10,y=campo.winfo_height()//2)
        self.root.update()
        pop=self.root.tk.call('ttk::combobox::PopdownWindow',str(campo))
        self.assertTrue(int(self.root.tk.call('winfo','ismapped',pop)))
        self.root.tk.call('ttk::combobox::Unpost',str(campo))

    def test_seleccion_unica_muestra_texto_literal_sin_modelo(self):
        self.app.arbol.selection_set(self.app.arbol.get_children()[0]);self.root.update()
        self.assertEqual(self.app.contenido_detalle.get('1.0','end-1c'),'Texto íntegro 1')
        self.assertEqual(str(self.app.boton_texto_completo.cget('state')),'normal')

    def test_ctrl_agrega_y_quita_filas_no_contiguas(self):
        arbol=self.app.arbol;ids=arbol.get_children()
        def clic(i,estado):
            arbol.see(ids[i]);self.root.update();x,y,w,h=arbol.bbox(ids[i])
            arbol.event_generate('<ButtonPress-1>',x=x+25,y=y+h//2,state=estado)
            arbol.event_generate('<ButtonRelease-1>',x=x+25,y=y+h//2,state=estado);self.root.update()
        clic(0,0);clic(2,4)
        self.assertEqual(set(arbol.selection()),{ids[0],ids[2]})
        clic(0,4);self.assertEqual(arbol.selection(),(ids[2],))

    def test_fecha_completa_tiene_ancho_y_desplazamiento_lateral(self):
        self.win.geometry('560x420');self.root.update()
        self.assertEqual(self.app.arbol.item(self.app.arbol.get_children()[0],'values')[0],'12/10/2026 17:00:00')
        self.assertLess(self.app.arbol.xview()[1],1)
        self.app.arbol.xview_moveto(1);self.assertGreater(self.app.arbol.xview()[0],0)

    def test_decision_de_modelo_larga_no_oculta_entrada(self):
        self.win.withdraw();self.root.deiconify()
        self.app.estado_ia.configure(text='Última elección: jarvis-deepseek:8b · razonamiento, comparación, diseño o depuración explícitos. Respaldo local sin repetir herramientas.')
        for ancho,alto in ((760,560),(1100,780)):
            self.root.geometry(f'{ancho}x{alto}');self.root.update()
            for widget in (self.app.composer,self.app.boton_enviar):
                x=widget.winfo_rootx()-self.root.winfo_rootx();y=widget.winfo_rooty()-self.root.winfo_rooty()
                self.assertGreater(widget.winfo_height(),10);self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                self.assertLessEqual(x+widget.winfo_width(),self.root.winfo_width()+1)
                self.assertLessEqual(y+widget.winfo_height(),self.root.winfo_height()+1)

    def test_chat_conserva_composer_y_envio_a_distintos_tamanos(self):
        self.win.withdraw();self.root.deiconify()
        for ancho,alto in ((760,560),(1100,780),(1380,900)):
            self.root.geometry(f'{ancho}x{alto}');self.root.update()
            campo=self.app.composer
            y=campo.winfo_rooty()-self.root.winfo_rooty()
            self.assertGreater(campo.winfo_height(),30)
            self.assertGreaterEqual(y,0)
            self.assertLessEqual(y+campo.winfo_height(),self.root.winfo_height())
            self.assertEqual(str(campo.cget('state')),'normal')
            boton=self.app.boton_enviar
            self.assertTrue(boton.winfo_ismapped());self.assertGreater(boton.winfo_width(),40)
            self.assertLessEqual(boton.winfo_rootx()-self.root.winfo_rootx()+boton.winfo_width(),self.root.winfo_width())
        self.app.composer.insert('1.0','Mensaje de prueba sin enviar')
        self.assertEqual(self.app.composer.get('1.0','end-1c'),'Mensaje de prueba sin enviar')
        self.app.composer.delete('1.0','end')

    def test_enter_envia_y_ctrl_enter_inserta_linea_sin_enviar(self):
        self.win.withdraw();self.root.deiconify();self.root.update()
        campo=self.app.composer;campo.focus_force();self.root.update()
        campo.insert('1.0','Primera');campo.mark_set('insert','end-1c')
        with patch.object(self.app,'enviar') as enviar:
            campo.event_generate('<Control-Return>');self.root.update()
            self.assertEqual(campo.get('1.0','end-1c'),'Primera\n');enviar.assert_not_called()
            campo.insert('insert','Segunda')
            campo.event_generate('<Return>');self.root.update()
            enviar.assert_called_once();self.assertEqual(campo.get('1.0','end-1c'),'Primera\nSegunda')

    def test_ctrl_enter_reemplaza_seleccion_con_una_sola_linea(self):
        campo=self.app.composer;campo.insert('1.0','Uno Dos Tres');campo.tag_add('sel','1.4','1.7')
        self.app._salto_linea(None)
        self.assertEqual(campo.get('1.0','end-1c'),'Uno \n Tres')

    def test_selector_otra_ia_ofrece_solo_modelos_de_chat_locales(self):
        from tkinter import ttk
        self.app.modelos.configure(values=('qwen3:8b','otro:1b','nomic-embed-text:latest'))
        self.app.modelo_var.set('qwen3:8b');self.app.composer.insert('1.0','Pregunta elegida')
        self.app.mostrar_otra_ia();self.root.update()
        ventana=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Jarvis · Otra IA')
        def todos(w):
            yield w
            for hijo in w.winfo_children():yield from todos(hijo)
        campo=next(w for w in todos(ventana) if isinstance(w,ttk.Combobox))
        self.assertEqual(campo.cget('values'),('qwen3:8b','otro:1b'));self.assertEqual(campo.get(),'otro:1b')
        texto=next(w for w in todos(ventana) if isinstance(w,tk.Text));self.assertEqual(texto.get('1.0','end-1c'),'Pregunta elegida')

    def test_selector_automatico_persiste_sin_guardar_etiqueta_como_modelo(self):
        import configuracion_jarvis as C
        import jarvis_agente as J
        ajustes=dict(C.DEFAULT)
        self.app.modelo_var.set(C.ETIQUETA_AUTOMATICA)
        with patch.object(J,'AJUSTES',ajustes),patch.object(J,'MODELO',C.MODELO_PREDETERMINADO),patch.object(C,'guardar',side_effect=lambda d:C.validar(d)) as guardar:
            self.app._cambiar_modelo()
            self.assertEqual(ajustes['seleccion_modelo'],'automatico')
            self.assertEqual(guardar.call_args.args[0]['modelo'],C.MODELO_PREDETERMINADO)
            self.app._aplicar_config()
            self.assertEqual(self.app.modelo_var.get(),C.ETIQUETA_AUTOMATICA)

    def test_selector_otra_ia_no_ofrece_etiqueta_automatica_como_modelo(self):
        import configuracion_jarvis as C
        from tkinter import ttk
        self.app.modelos.configure(values=(C.ETIQUETA_AUTOMATICA,'qwen3:8b'))
        self.app.modelo_var.set(C.ETIQUETA_AUTOMATICA)
        self.app.mostrar_otra_ia();self.root.update()
        ventana=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Jarvis · Otra IA')
        def todos(w):
            yield w
            for hijo in w.winfo_children():yield from todos(hijo)
        campo=next(w for w in todos(ventana) if isinstance(w,ttk.Combobox))
        self.assertNotIn(C.ETIQUETA_AUTOMATICA,campo.cget('values'))
        ventana.destroy()

    def test_api_no_crea_formulario_ni_aunque_se_altere_la_politica(self):
        from tkinter import ttk
        antes=set(self.root.winfo_children())
        with patch('politica_ia.permite_externa',return_value=True),patch('interfaz_grafica.messagebox.showinfo'),patch.object(__import__('segunda_opinion').WEB,'solicitar_publico') as red:
            self.app.configurar_api(self.root);self.root.update()
        self.assertEqual(set(self.root.winfo_children()),antes)
        self.assertFalse(hasattr(self.app,'api_widgets'));red.assert_not_called()

    def test_segunda_opinion_local_conserva_consulta_al_redimensionar(self):
        from tkinter import ttk
        self.app.modelos.configure(values=('qwen3:8b','jarvis-deepseek:8b'))
        self.app.mostrar_otra_ia();self.root.update()
        ventana=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Jarvis · Otra IA')
        def todos(w):
            yield w
            for hijo in w.winfo_children():yield from todos(hijo)
        botones=[w for w in todos(ventana) if isinstance(w,ttk.Button)]
        self.assertEqual([w.cget('text') for w in botones],['Consultar'])
        for tamano in ('640x480','800x640'):
            ventana.geometry(tamano);self.root.update()
            for b in botones:
                self.assertTrue(b.winfo_ismapped())
                self.assertLessEqual(b.winfo_rooty()-ventana.winfo_rooty()+b.winfo_height(),ventana.winfo_height())
        ventana.destroy()


if __name__=='__main__':unittest.main()
