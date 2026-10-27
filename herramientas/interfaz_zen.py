"""Configuración visible de la excepción Zen; no usa historial ni adjuntos."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox,ttk
import externo_zen as Z


class VentanaZen:
    def __init__(self,app):
        from interfaz_grafica import SUPERFICIE,PANEL,TINTA,VERDE
        self.app=app;self.resultados=queue.Queue();self.ocupado=False;self._job=None
        self.win=tk.Toplevel(app.root);self.win.title('Jarvis · OpenCode API')
        self.win.configure(bg=SUPERFICIE)
        self.win.geometry(f"{min(720,app.root.winfo_screenwidth()-40)}x{min(620,app.root.winfo_screenheight()-80)}")
        self.win.minsize(500,430);self.win.columnconfigure(0,weight=1);self.win.rowconfigure(5,weight=1)
        self.win.protocol('WM_DELETE_WINDOW',self.cerrar)
        ttk.Label(self.win,text='OpenCode Zen',font=app._fuente(20,'bold'),style='Panel.TLabel').grid(row=0,column=0,sticky='w',padx=18,pady=(14,6))
        self.estado=ttk.Label(self.win,style='PanelSubtitle.TLabel',wraplength=650)
        self.estado.grid(row=1,column=0,sticky='ew',padx=18,pady=(0,10))
        self.estado.bind('<Configure>',lambda e:self.estado.configure(wraplength=max(200,e.width)))
        clave=ttk.Frame(self.win,style='Panel.TFrame',padding=(18,0));clave.grid(row=2,column=0,sticky='ew');clave.columnconfigure(0,weight=1)
        ttk.Label(clave,text='1. Pega tu clave aquí; nunca en el chat.',style='Panel.TLabel').grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,6))
        self.clave=tk.StringVar()
        self.entrada=ttk.Entry(clave,textvariable=self.clave,show='*');self.entrada.grid(row=1,column=0,sticky='ew')
        self.boton_guardar=ttk.Button(clave,text='Guardar clave',command=self.guardar_clave);self.boton_guardar.grid(row=1,column=1,padx=(8,0))
        controles=ttk.Frame(self.win,style='Panel.TFrame',padding=18);controles.grid(row=3,column=0,sticky='ew')
        for i in range(3):controles.columnconfigure(i,weight=1)
        self.boton_catalogo=ttk.Button(controles,text='2. Cargar modelos',command=lambda:self.ejecutar('/externo modelos actualizar'))
        self.boton_catalogo.grid(row=0,column=0,sticky='ew',padx=(0,6))
        self.boton_encender=ttk.Button(controles,text='3. Activar',command=lambda:self.ejecutar('/externo encender'))
        self.boton_encender.grid(row=0,column=1,sticky='ew',padx=(0,6))
        self.boton_apagar=ttk.Button(controles,text='Apagar',command=self.apagar);self.boton_apagar.grid(row=0,column=2,sticky='ew')
        self.aviso=ttk.Label(self.win,text='Primero local. Zen solo recibe preguntas genéricas; archivos, adjuntos y memoria permanecen locales. Cargar modelos no prueba una respuesta.',style='PanelSubtitle.TLabel',wraplength=650)
        self.aviso.grid(row=4,column=0,sticky='ew',padx=18,pady=(0,10))
        self.aviso.bind('<Configure>',lambda e:self.aviso.configure(wraplength=max(200,e.width)))
        marco=ttk.Frame(self.win,style='Panel.TFrame',padding=(18,0));marco.grid(row=5,column=0,sticky='nsew')
        self.modelos=tk.Text(marco,wrap='word',height=7,bg=PANEL,fg=TINTA,insertbackground=VERDE,font=app._fuente(10),relief='flat',padx=10,pady=8)
        scroll=ttk.Scrollbar(marco,command=self.modelos.yview);self.modelos.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.modelos.pack(fill='both',expand=True)
        ttk.Button(self.win,text='Cerrar',command=self.cerrar).grid(row=6,column=0,sticky='e',padx=18,pady=12)
        self.refrescar();self._job=self.win.after(80,self.procesar)

    def refrescar(self):
        e=Z.estado()
        texto=('Activado' if e['encendido'] else 'Apagado')+' · Clave '+('guardada/disponible' if Z.clave() else 'sin configurar')+' · Catálogo '+('cargado' if e.get('catalogo') else 'pendiente')
        if e.get('transporte')=='cliente_oficial':texto+=' · Cliente oficial aislado'
        if e.get('ultimo_error'):texto+='\nÚltimo intento: '+e['ultimo_error'][:400]
        self.estado.configure(text=texto)
        listado=Z.modelos();self.modelos.configure(state='normal');self.modelos.delete('1.0','end')
        self.modelos.insert('1.0','Modelos del registro (el acceso de tu cuenta se comprueba al cargar el catálogo):\n\n'+'\n'.join(m['id']+' · '+m['estado'] for m in listado))
        self.modelos.configure(state='disabled')

    def guardar_clave(self):
        valor=self.clave.get().strip();self.clave.set('')
        if not valor:self.aviso.configure(text='Pega la clave en el campo oculto antes de guardarla.');return
        if not messagebox.askyesno('Guardar clave OpenCode','¿Guardar esta clave fuera del proyecto, en un archivo privado con permisos 600?',parent=self.win):return
        try:
            Z.guardar_clave(valor)
            self.aviso.configure(text='Clave guardada. Continúa con «Cargar modelos» y después «Activar». Guardarla no activa Zen.')
        except (OSError,ValueError):self.aviso.configure(text='No pude guardar la clave. Revisa el formato y los permisos; no se añadió al chat.')
        finally:valor=None
        self.refrescar()

    def ejecutar(self,comando):
        if self.ocupado:return
        if comando not in {'/externo modelos actualizar','/externo encender'}:raise ValueError('Acción de configuración no permitida')
        self.ocupado=True;self.aviso.configure(text='Esperando permiso o respuesta del servicio… Puedes apagar Zen en cualquier momento.')
        for boton in (self.boton_catalogo,self.boton_encender,self.boton_guardar):boton.configure(state='disabled')
        def trabajar():
            try:
                _,texto=Z.comando(comando,self.app._pedir_permiso)
            except (OSError,ValueError,ConnectionError):texto='No pude completar esta configuración. Revisa /externo estado.'
            self.resultados.put(texto)
        threading.Thread(target=trabajar,daemon=True).start()

    def apagar(self):
        self.aviso.configure(text=Z.apagar());self.refrescar()

    def procesar(self):
        try:
            while True:
                texto=self.resultados.get_nowait();self.ocupado=False;self.aviso.configure(text=texto)
                for boton in (self.boton_catalogo,self.boton_encender,self.boton_guardar):boton.configure(state='normal')
                self.refrescar()
        except queue.Empty:pass
        self._job=self.win.after(80,self.procesar)

    def cerrar(self):
        self.clave.set('')
        if self._job:self.win.after_cancel(self._job)
        self.win.destroy()
