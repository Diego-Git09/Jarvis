"""Panel de escritorio independiente del chat; sigue atento a fechas al cerrar Jarvis."""
import fcntl
import hashlib
import os
import queue
import socket
import sys
import threading
import tkinter as tk
from tkinter import ttk,messagebox
from pathlib import Path
import recordatorios_jarvis as R
from entorno_jarvis import PROYECTO,en_pruebas

FONDO='#05080c';PANEL='#0c141b';TINTA='#e3edf2';ACENTO='#56e0d2';MUTED='#91a7b5'


def revision_codigo():
    carpeta=Path(__file__).resolve().parent
    nombres=('recordatorios_escritorio.py','recordatorios_jarvis.py','fechas_naturales.py','lenguaje_jarvis.py','estilo_usuario.json','vocabulario.json')
    return tuple((n,(carpeta/n).stat().st_mtime_ns) for n in nombres)


class Instancia:
    def __init__(self,orden):
        tag=hashlib.sha256(str(PROYECTO).encode()).hexdigest()[:10]
        self.ruta=Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/f'jarvis-recordatorios-{os.getuid()}-{tag}.sock'
        self.eventos=queue.Queue();self.secundaria=False
        self.lock=os.open(str(self.ruta)+'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.secundaria=True
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as cliente:
                cliente.settimeout(2);cliente.connect(str(self.ruta));cliente.sendall(orden.encode())
            os.close(self.lock);return
        if self.ruta.exists():self.ruta.unlink()
        self.servidor=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.servidor.bind(str(self.ruta));os.chmod(self.ruta,0o600);self.servidor.listen(5)
        threading.Thread(target=self._leer,daemon=True).start()

    def _leer(self):
        while True:
            try:
                cliente,_=self.servidor.accept()
                with cliente:
                    cliente.settimeout(2);orden=cliente.recv(32).decode('utf-8')
                    if orden in {'gestionar','refrescar','iniciar'}:self.eventos.put(orden)
            except (OSError,UnicodeError):return

    def cerrar(self):
        if self.secundaria:return
        self.servidor.close()
        try:self.ruta.unlink()
        except FileNotFoundError:pass
        os.close(self.lock)


class PanelRecordatorios:
    def __init__(self,root,gestionar=False,instancia=None):
        self.root=root;self.instancia=instancia;self.todos=gestionar;self.plegado=False;self.firma=None;self.conocidos=set();self.job=None;self.revision=revision_codigo();self.en_dialogo=False
        self.root.title('Jarvis · Recordatorios');root.configure(bg=FONDO)
        ancho=min(440,root.winfo_screenwidth()-40);alto=min(500,root.winfo_screenheight()-100)
        root.geometry(f'{ancho}x{alto}+{max(0,root.winfo_screenwidth()-ancho-30)}+60');root.minsize(min(330,ancho),70)
        estilo=ttk.Style(root);estilo.theme_use('clam')
        estilo.configure('R.TFrame',background=FONDO);estilo.configure('R.TButton',background=PANEL,foreground=TINTA,padding=(8,5),font=('Noto Sans',10),bordercolor='#22333e',lightcolor=PANEL,darkcolor=PANEL,focuscolor=PANEL)
        estilo.map('R.TButton',background=[('active','#17313b')])
        estilo.configure('R.Vertical.TScrollbar',background='#1b2b36',troughcolor=FONDO,bordercolor=FONDO,arrowcolor=MUTED,lightcolor=FONDO,darkcolor=FONDO)
        estilo.configure('R.TEntry',fieldbackground=PANEL,foreground=TINTA,insertcolor=ACENTO,bordercolor='#22333e')
        estilo.configure('R.TCombobox',fieldbackground=PANEL,foreground=TINTA,background=PANEL,arrowcolor=ACENTO)
        estilo.map('R.TCombobox',fieldbackground=[('readonly',PANEL)],foreground=[('readonly',TINTA)])
        root.option_add('*TCombobox*Listbox.background',PANEL);root.option_add('*TCombobox*Listbox.foreground',TINTA)
        cab=tk.Frame(root,bg=FONDO);cab.pack(fill='x',padx=12,pady=10)
        self.titulo=tk.Label(cab,text='Recordatorios',bg=FONDO,fg=ACENTO,font=('Noto Sans',11,'bold'));self.titulo.pack(side='left')
        ttk.Button(cab,text='↕',width=3,style='R.TButton',command=self.plegar).pack(side='right')
        self.cuerpo=tk.Frame(root,bg=FONDO);self.cuerpo.pack(fill='both',expand=True)
        barra=tk.Frame(self.cuerpo,bg=FONDO);barra.pack(fill='x',padx=12,pady=(0,8))
        ttk.Button(barra,text='+ Nuevo',style='R.TButton',command=self.editar).pack(side='left')
        self.modo=ttk.Button(barra,text='Solo visibles' if gestionar else 'Ver todos',style='R.TButton',command=self.alternar);self.modo.pack(side='left',padx=6)
        self.fijado=tk.BooleanVar(value=False)
        tk.Checkbutton(barra,text='Encima',variable=self.fijado,command=lambda:root.attributes('-topmost',self.fijado.get()),bg=FONDO,fg=MUTED,selectcolor=PANEL,activebackground=FONDO,activeforeground=TINTA).pack(side='right')
        area=tk.Frame(self.cuerpo,bg=FONDO);area.pack(fill='both',expand=True,padx=12)
        self.canvas=tk.Canvas(area,bg=FONDO,highlightthickness=0);self.canvas.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(area,style='R.Vertical.TScrollbar',command=self.canvas.yview);scroll.pack(side='right',fill='y');self.canvas.configure(yscrollcommand=scroll.set)
        self.tarjetas=tk.Frame(self.canvas,bg=FONDO);self.objeto=self.canvas.create_window((0,0),window=self.tarjetas,anchor='nw')
        self.tarjetas.bind('<Configure>',lambda _e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',self.ajustar)
        for widget in (self.canvas,self.tarjetas):
            widget.bind('<Button-4>',lambda _e:self.canvas.yview_scroll(-3,'units'))
            widget.bind('<Button-5>',lambda _e:self.canvas.yview_scroll(3,'units'))
        self.estado=tk.Label(self.cuerpo,text='Horarios de Chile · se conservan al cerrar el chat',bg=FONDO,fg=MUTED,font=('Noto Sans',9),wraplength=390,justify='left');self.estado.pack(fill='x',padx=12,pady=8)
        self.root.protocol('WM_DELETE_WINDOW',self.plegar)
        self.actualizar()

    def ajustar(self,e):
        self.canvas.itemconfigure(self.objeto,width=e.width)
        for tarjeta in self.tarjetas.winfo_children():
            for w in tarjeta.winfo_children():
                if isinstance(w,tk.Label):w.configure(wraplength=max(180,e.width-20))
                if hasattr(w,'botones'):
                    columnas=4 if e.width>=350 else 2
                    for i,b in enumerate(w.botones):b.grid(row=i//columnas,column=i%columnas,sticky='ew',padx=(0,4),pady=(0,4))
                    for i in range(4):w.columnconfigure(i,weight=1 if i<columnas else 0)

    def plegar(self):
        self.plegado=not self.plegado
        if self.plegado:self.cuerpo.pack_forget();self.root.geometry('')
        else:self.cuerpo.pack(fill='both',expand=True);self.root.geometry(f'{min(440,self.root.winfo_screenwidth()-40)}x{min(500,self.root.winfo_screenheight()-100)}')

    def alternar(self):
        self.todos=not self.todos;self.modo.configure(text='Solo visibles' if self.todos else 'Ver todos');self.firma=None;self.actualizar(programar=False)

    def mostrar(self):
        self.todos=True;self.modo.configure(text='Solo visibles')
        if self.plegado:self.plegar()
        self.firma=None;self.actualizar(programar=False);self.root.deiconify();self.root.lift()

    def actualizar(self,programar=True):
        if not en_pruebas() and self.instancia and revision_codigo()!=self.revision and not self.en_dialogo and not any(isinstance(w,tk.Toplevel) for w in self.root.winfo_children()):
            self.root.after_idle(self.reiniciar);return
        if self.instancia:
            while not self.instancia.eventos.empty():
                orden=self.instancia.eventos.get_nowait()
                if orden=='gestionar':self.mostrar()
                else:self.firma=None
        try:
            items=R.listar();visibles=R.visibles(items);filas=items if self.todos else visibles
            nuevos={r['id'] for r in visibles}-self.conocidos;self.conocidos={r['id'] for r in visibles}
            if nuevos:
                if self.plegado:self.plegar()
                self.root.deiconify()
            firma=tuple((r['id'],R.revision(r)) for r in filas)
            if firma!=self.firma:
                self.firma=firma
                for w in self.tarjetas.winfo_children():w.destroy()
                self.titulo.configure(text=f"Recordatorios • {len(visibles)} {'visible' if len(visibles)==1 else 'visibles'}")
                for item in filas:self.tarjeta(item)
                if not filas:
                    tk.Label(self.tarjetas,text='Sin recordatorios pendientes.' if not items else 'No hay recordatorios visibles ahora.\nPulsa «Ver todos» para revisar sus fechas.',bg=FONDO,fg=MUTED,font=('Noto Sans',11),wraplength=340,justify='left').pack(fill='x',pady=20)
                if not filas and not self.todos:self.root.withdraw()
            self.estado.configure(text='Horarios de Chile · cambios guardados en este computador')
        except (ValueError,OSError) as e:
            self.estado.configure(text='No pude leer los recordatorios: '+str(e));self.root.deiconify()
        if programar:self.job=self.root.after(3000,self.actualizar)

    def reiniciar(self):
        self.instancia.cerrar();self.root.destroy()
        os.execv(sys.executable,[sys.executable,'-B',str(Path(__file__).resolve()),'--gestionar' if self.todos else '--iniciar'])

    def tarjeta(self,item):
        tarjeta=tk.Frame(self.tarjetas,bg=PANEL,padx=10,pady=10);tarjeta.pack(fill='x',pady=(0,8))
        tk.Label(tarjeta,text=item['texto'],bg=PANEL,fg=TINTA,font=('Noto Sans',11),wraplength=350,justify='left',anchor='w').pack(fill='x')
        tk.Label(tarjeta,text=R.texto_fecha(item),bg=PANEL,fg=ACENTO,font=('Noto Sans',9),wraplength=350,justify='left',anchor='w').pack(fill='x',pady=(6,8))
        acciones=tk.Frame(tarjeta,bg=PANEL);acciones.pack(fill='x')
        acciones.botones=[]
        for texto,accion in [('Editar',lambda r=item:self.editar(r)),('Hecho',lambda r=item:self.cambiar(r,estado='hecho')),('+1 h',lambda r=item:self.cambiar(r,fecha='en 1 hora')),('Eliminar',lambda r=item:self.eliminar(r))]:
            b=ttk.Button(acciones,text=texto,style='R.TButton',command=accion);acciones.botones.append(b)
            i=len(acciones.botones)-1;columnas=4 if self.canvas.winfo_width()>=350 else 2
            b.grid(row=i//columnas,column=i%columnas,sticky='ew',padx=(0,4),pady=(0,4));acciones.columnconfigure(i%columnas,weight=1)

    def cambiar(self,item,**cambios):
        try:R.modificar(item['id'],esperado=R.revision(item),**cambios);self.firma=None;self.actualizar(programar=False)
        except (ValueError,OSError) as e:messagebox.showerror('Recordatorio',str(e),parent=self.root)

    def eliminar(self,item):
        self.en_dialogo=True
        try:
            if messagebox.askyesno('Eliminar recordatorio',item['texto']+'\n\n¿Eliminarlo del panel?',parent=self.root):self.cambiar(item,estado='eliminado')
        finally:self.en_dialogo=False

    def editar(self,item=None):
        win=tk.Toplevel(self.root);win.title('Editar recordatorio' if item else 'Nuevo recordatorio');win.configure(bg=FONDO)
        win.geometry(f"{min(520,self.root.winfo_screenwidth()-40)}x{min(610,self.root.winfo_screenheight()-80)}");win.minsize(380,min(510,self.root.winfo_screenheight()-80))
        win.columnconfigure(0,weight=1);win.rowconfigure(1,weight=1)
        tk.Label(win,text='¿Qué quieres recordar?',bg=FONDO,fg=TINTA,font=('Noto Sans',11,'bold')).grid(row=0,column=0,sticky='w',padx=14,pady=10)
        texto=tk.Text(win,bg=PANEL,fg=TINTA,insertbackground=ACENTO,font=('Noto Sans',11),wrap='word',height=4);texto.grid(row=1,column=0,sticky='nsew',padx=14)
        texto.insert('1.0',item['texto'] if item else '')
        avanzado=bool(item and item.get('evento') and (item.get('anticipacion_dias') is not None or item.get('anticipacion_minutos') is not None))
        modo=tk.StringVar(value='Evento con aviso anticipado' if avanzado else 'Desde una fecha' if item and item['fecha'] else 'Siempre visible')
        selector=ttk.Combobox(win,style='R.TCombobox',textvariable=modo,values=('Siempre visible','Desde una fecha','Evento con aviso anticipado'),state='readonly');selector.grid(row=2,column=0,sticky='ew',padx=14,pady=10)
        etiqueta=tk.Label(win,text='Fecha y hora',bg=FONDO,fg=TINTA,anchor='w');etiqueta.grid(row=3,column=0,sticky='ew',padx=14)
        valor_fecha=item.get('evento') if avanzado else item.get('fecha') if item else None
        fecha=tk.StringVar(value=R.datetime.fromisoformat(valor_fecha).astimezone(R.ZONA).strftime('%d/%m/%Y %H:%M') if valor_fecha else 'mañana a las 09:00')
        campo=ttk.Entry(win,style='R.TEntry',textvariable=fecha);campo.grid(row=4,column=0,sticky='ew',padx=14,pady=5)
        fila_antes=tk.Frame(win,bg=FONDO);fila_antes.grid(row=5,column=0,sticky='ew',padx=14,pady=6)
        tk.Label(fila_antes,text='Empieza a aparecer',bg=FONDO,fg=TINTA).pack(side='left')
        minutos=item.get('anticipacion_minutos') if avanzado else None
        cantidad=tk.StringVar(value=str(item.get('anticipacion_dias') if avanzado and item.get('anticipacion_dias') is not None else minutos//60 if minutos is not None and minutos%60==0 else minutos if minutos is not None else 2))
        unidad=tk.StringVar(value='horas' if minutos is not None and minutos%60==0 else 'minutos' if minutos is not None else 'días')
        ttk.Entry(fila_antes,style='R.TEntry',textvariable=cantidad,width=6).pack(side='left',padx=8)
        ttk.Combobox(fila_antes,style='R.TCombobox',textvariable=unidad,values=('días','horas','minutos'),state='readonly',width=9).pack(side='left')
        tk.Label(fila_antes,text='antes',bg=FONDO,fg=TINTA).pack(side='left',padx=5)
        ejemplo=tk.Label(win,text='Ejemplos: 20 de octubre a las nueve y media · mañana a las 09:00.\nSin hora explícita: 09:00 de Chile.',bg=FONDO,fg=MUTED,font=('Noto Sans',9),justify='left',wraplength=450);ejemplo.grid(row=6,column=0,sticky='ew',padx=14,pady=8)
        hasta=tk.StringVar(value=R.datetime.fromisoformat(item['mostrar_hasta']).astimezone(R.ZONA).strftime('%d/%m/%Y %H:%M') if item and item.get('mostrar_hasta') else '')
        tk.Label(win,text='Mostrar hasta (opcional; vacío = hasta completarlo)',bg=FONDO,fg=TINTA,anchor='w').grid(row=7,column=0,sticky='ew',padx=14)
        ttk.Entry(win,style='R.TEntry',textvariable=hasta).grid(row=8,column=0,sticky='ew',padx=14,pady=5)
        calculo=tk.Label(win,text='',bg=FONDO,fg=ACENTO,font=('Noto Sans',10),justify='left',wraplength=450);calculo.grid(row=9,column=0,sticky='ew',padx=14,pady=8)
        def argumentos():
            args={'texto':texto.get('1.0','end-1c'),'mostrar_hasta':hasta.get().strip() or 'sin fin'}
            if modo.get()=='Evento con aviso anticipado':
                n=int(cantidad.get());args['evento']=fecha.get()
                args['anticipacion_dias' if unidad.get()=='días' else 'anticipacion_minutos']=n*(60 if unidad.get()=='horas' else 1)
            else:args['fecha']=fecha.get() if modo.get()=='Desde una fecha' else 'siempre'
            return args
        def seleccionar(*_e):
            avanzado=modo.get()=='Evento con aviso anticipado'
            campo.configure(state='disabled' if modo.get()=='Siempre visible' else 'normal')
            etiqueta.configure(text='Fecha del evento o prueba' if avanzado else 'Cuándo empieza a aparecer')
            if avanzado:fila_antes.grid()
            else:fila_antes.grid_remove()
            try:
                args=argumentos();plan=R.proyectar(item,**args) if item else R.plan_fecha(**{k:v for k,v in args.items() if k!='texto'})
                calculo.configure(text=R.texto_fecha(plan))
            except (ValueError,TypeError):calculo.configure(text='Indica una fecha válida y una anticipación con cifras.')
        selector.bind('<<ComboboxSelected>>',seleccionar)
        for var in (fecha,cantidad,unidad,hasta):var.trace_add('write',seleccionar)
        seleccionar()
        def guardar():
            try:
                args=argumentos()
                if item:R.modificar(item['id'],esperado=R.revision(item),**args)
                else:R.crear(**args)
                win.destroy();self.firma=None;self.actualizar(programar=False)
            except (ValueError,OSError) as e:messagebox.showerror('Recordatorio',str(e),parent=win)
        ttk.Button(win,text='Guardar',style='R.TButton',command=guardar).grid(row=10,column=0,sticky='e',padx=14,pady=12)
        texto.focus_set()
        self.editor={'ventana':win,'texto':texto,'modo':modo,'fecha':fecha,'cantidad':cantidad,'unidad':unidad,'hasta':hasta,'guardar':guardar,'calculo':calculo}


def main():
    if en_pruebas() and os.environ.get('JARVIS_UI_REAL')!='1':return
    orden='gestionar' if '--gestionar' in sys.argv else 'refrescar' if '--refrescar' in sys.argv else 'iniciar'
    instancia=Instancia(orden)
    if instancia.secundaria:return
    root=tk.Tk();root.withdraw();panel=PanelRecordatorios(root,orden=='gestionar',instancia)
    if orden=='gestionar':root.deiconify()
    try:root.mainloop()
    finally:instancia.cerrar()


if __name__=='__main__':main()
