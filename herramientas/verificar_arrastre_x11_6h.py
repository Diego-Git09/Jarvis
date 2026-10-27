"""Integración Xdnd entre dos procesos propios, sin mover ni capturar el ratón.

Emite mensajes nativos Xdnd y atiende XdndSelection en el proceso de origen.
No acredita un gesto físico desde un gestor de archivos. No usa modelos/MCP.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch


def emisor(config):
    import tkinter as tk
    import arrastre_adjuntos as A
    root=tk.Tk();root.withdraw();marco=tk.Frame(root);marco.pack();root.update()
    trazas=[]
    try:
        A._cargar_backend().TkinterDnD.require(root)
        datos='\r\n'.join(Path(p).as_uri() for p in config['rutas'])+'\r\n'
        def seleccion(desde,cantidad):
            trazas.append({'evento':'SelectionRequest','desde':int(desde),'cantidad':int(cantidad)})
            return datos[int(desde):int(desde)+int(cantidad)]
        marco.selection_handle(seleccion,selection='XdndSelection',type='text/uri-list')
        marco.selection_own(selection='XdndSelection')
        fuente=str(marco);destino=config['ventana']
        def enviar(nombre,*args):
            try:
                # La biblioteca nativa registra estos comandos en el espacio
                # global; las funciones Tcl de xdnd los resuelven allí.
                valor=root.tk.call(nombre,*args)
                trazas.append({'evento':nombre,'resultado':str(valor)})
            except Exception as e:trazas.append({'evento':nombre,'error':str(e)})
        root.after(100,lambda:enviar('_send_XdndEnter',fuente,destino,destino,('text/uri-list',)))
        root.after(300,lambda:enviar('_send_XdndPosition',fuente,destino,destino,config['x'],config['y'],'copy'))
        root.after(600,lambda:enviar('_send_XdndDrop',fuente,destino,destino))
        root.after(2200,root.quit);root.mainloop()
    finally:root.destroy()
    print(json.dumps({'trazas':trazas},ensure_ascii=False),flush=True)


def verificar(destino):
    destino.parent.mkdir(parents=True,exist_ok=True)
    if destino.exists():raise ValueError('No sobrescribir una verificación anterior.')
    with tempfile.TemporaryDirectory(prefix='jarvis-xdnd-6h-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        trabajo=Path(tmp,'trabajo');trabajo.mkdir()
        import tkinter as tk
        import interfaz_grafica as G
        root=tk.Tk();root.withdraw();root.overrideredirect(True)
        root.geometry('1024x768+20000+20000')
        resultados=[];emision=None;app=None
        def comprobar(nombre,valor,detalle=None):resultados.append({'prueba':nombre,'ok':bool(valor),'detalle':detalle})
        try:
            with patch.object(G.Aplicacion,'_inicializar_estado',return_value=None):
                app=G.Aplicacion(root,SimpleNamespace(cerrar=lambda:None))
            root.geometry('1024x768+20000+20000');root.deiconify();root.update()
            comprobar('backend_real',app._arrastre['ok'],app._arrastre)
            paths=[trabajo/'fuente con espacio.txt',trabajo/'fuente ñ y {llaves}.md']
            for i,p in enumerate(paths):p.write_text(f'Fuente ficticia X11 número {i}.\n')
            config={'ventana':app.composer.winfo_id(),'x':app.composer.winfo_rootx()+8,
                    'y':app.composer.winfo_rooty()+8,'rutas':[str(p) for p in paths]}
            p=Path(tmp,'emisor.json');p.write_text(json.dumps(config));p.chmod(0o600)
            emision=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--emitir',str(p)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=os.environ.copy())
            fin=time.monotonic()+8
            while time.monotonic()<fin:
                root.update();time.sleep(.005)
                if emision.poll() is not None and not app.pendiente_actual:break
            if emision.poll() is None:emision.kill()
            stdout,stderr=emision.communicate(timeout=2)
            try:traza=json.loads(stdout)
            except ValueError:traza={'error':'El emisor no produjo JSON válido.'}
            comprobar('emisor_termina',emision.returncode==0,{'codigo':emision.returncode,'stderr':stderr[:1000],**traza})
            envios=[t for t in traza.get('trazas',[]) if t.get('evento','').startswith('_send_')]
            comprobar('tres_mensajes_nativos_emitidos',len(envios)==3 and not any('error' in t for t in envios))
            comprobar('seleccion_servida_por_otro_proceso',any(t.get('evento')=='SelectionRequest' for t in traza.get('trazas',[])))
            comprobar('tanda_recibida',len(app.pendientes)==1 and bool(app.pendientes[0].get('tanda_id')),app.detalle_adjuntos['text'])
            if app.pendientes:
                d=G.J.TANDAS.cargar(app.pendientes[0]['tanda_id'])
                comprobar('dos_rutas_literales',sorted(x['ruta'] for x in d['archivos'])==sorted(str(p) for p in paths))
                comprobar('originales_intactos',all(p.read_text()==f'Fuente ficticia X11 número {i}.\n' for i,p in enumerate(paths)))
        except Exception as e:comprobar('excepcion',False,type(e).__name__+': '+str(e)[:1000])
        finally:
            if emision and emision.poll() is None:emision.kill();emision.communicate(timeout=2)
            if app:app._cerrando.set();app._cancelar_adjuntos.set()
            root.destroy()
        dato={'resultados':resultados,'alcance':'Dos procesos Tk propios, mensajes Xdnd nativos y selección de archivos locales ficticios; sin mover el ratón, capturas, modelos ni MCP. No acredita un gesto físico desde otra aplicación.'}
        destino.write_text(json.dumps(dato,ensure_ascii=False,indent=2)+'\n');destino.chmod(0o600)
        print(json.dumps(dato,ensure_ascii=False));return 0 if all(r['ok'] for r in resultados) else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--emitir',type=Path);ap.add_argument('--salida',type=Path);a=ap.parse_args()
    if a.emitir:emisor(json.loads(a.emitir.read_text()))
    elif a.salida:raise SystemExit(verificar(a.salida))
    else:ap.error('Indica --salida.')
