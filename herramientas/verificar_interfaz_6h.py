"""QA de widgets Tk reales con archivos sintéticos; no inicia modelos ni captura.

El arrastre se inyecta por el evento Tcl de TkDND, no mediante un ratón físico.
Las imágenes opcionales solo recortan la ventana propia con contenido ficticio.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch


def capturar_ventana(root,ruta):
    """Lee únicamente el drawable X11 creado por este arnés, nunca el escritorio."""
    import ctypes as C
    from PIL import Image
    class XImage(C.Structure):
        _fields_=[('width',C.c_int),('height',C.c_int),('xoffset',C.c_int),('format',C.c_int),('data',C.c_void_p),
                  ('byte_order',C.c_int),('bitmap_unit',C.c_int),('bitmap_bit_order',C.c_int),('bitmap_pad',C.c_int),
                  ('depth',C.c_int),('bytes_per_line',C.c_int),('bits_per_pixel',C.c_int),
                  ('red_mask',C.c_ulong),('green_mask',C.c_ulong),('blue_mask',C.c_ulong)]
    x=C.CDLL('libX11.so.6');x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
    x.XGetImage.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_ulong,C.c_int];x.XGetImage.restype=C.POINTER(XImage)
    x.XDestroyImage.argtypes=[C.POINTER(XImage)];x.XCloseDisplay.argtypes=[C.c_void_p]
    d=x.XOpenDisplay(None)
    if not d:raise RuntimeError('La conexión X11 de la ventana no está disponible.')
    imagen=None
    try:
        imagen=x.XGetImage(d,root.winfo_id(),0,0,root.winfo_width(),root.winfo_height(),C.c_ulong(-1).value,2)
        if not imagen:raise RuntimeError('No pude leer el drawable propio.')
        i=imagen.contents
        if i.bits_per_pixel!=32 or i.byte_order!=0 or (i.red_mask,i.green_mask,i.blue_mask)!=(0xff0000,0xff00,0xff):
            raise RuntimeError('Formato de píxel X11 no admitido por el arnés.')
        datos=C.string_at(i.data,i.bytes_per_line*i.height)
        Image.frombytes('RGB',(i.width,i.height),datos,'raw','BGRX',i.bytes_per_line,1).save(ruta)
    finally:
        if imagen:x.XDestroyImage(imagen)
        x.XCloseDisplay(d)


def main():
    p=argparse.ArgumentParser();p.add_argument('--salida',type=Path,required=True);a=p.parse_args()
    a.salida.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-gui-6h-') as temporal:
        os.environ.update(JARVIS_DIR=temporal,JARVIS_PRUEBAS='1')
        Path(temporal,'trabajo').mkdir()
        import tkinter as tk
        import interfaz_grafica as G
        resultados=[]
        root=tk.Tk()
        try:
            with patch.object(G.Aplicacion,'_inicializar_estado',return_value=None):
                app=G.Aplicacion(root,SimpleNamespace(cerrar=lambda:None))
            def comprobar(nombre,valor,detalle=''):
                resultados.append({'prueba':nombre,'ok':bool(valor),'detalle':detalle})
            root.update()
            comprobar('backend_TkDND_real',app._arrastre['ok'],dict(app._arrastre))
            for w,h in [(760,560),(1024,768),(1380,900)]:
                root.geometry(f'{w}x{h}+10+10');root.update()
                x=app.composer.winfo_rootx()-root.winfo_rootx();y=app.composer.winfo_rooty()-root.winfo_rooty()
                cw,ch=app.composer.winfo_width(),app.composer.winfo_height()
                comprobar(f'editor_visible_{w}x{h}',0<=x<x+cw<=root.winfo_width() and 0<=y<y+ch<=root.winfo_height(),{'posicion':[x,y,cw,ch],'ventana':[root.winfo_width(),root.winfo_height()]})
                comprobar(f'boton_visible_{w}x{h}',app.boton_enviar.winfo_ismapped())
            root.geometry('1024x768+10+10');root.update()
            app.composer.focus_force();app.composer.insert('1.0','Texto sintético')
            enviados=[]
            with patch.object(app,'enviar',side_effect=lambda:enviados.append(app.composer.get('1.0','end-1c'))):
                app.composer.event_generate('<Control-Return>');root.update()
                comprobar('Ctrl_Enter_salto',app.composer.get('1.0','end-1c')=='Texto sintético\n' and not enviados)
                app.composer.event_generate('<Return>');root.update()
                comprobar('Enter_envia',enviados==['Texto sintético\n'])
            archivos=[Path(temporal,'trabajo',n) for n in ['uno con espacio.txt','dos ñ.txt']]
            for n,f in enumerate(archivos):f.write_text(f'Documento ficticio {n}\n')
            datos=root.tk.call('list',*(str(f) for f in archivos))
            # TkDND expone %D por un evento virtual registrado; Tcl invoca el
            # mismo callback de la ventana, sin convertir la lista en código.
            enlace=root.tk.splitlist(app.composer.dnd_bind('<<Drop>>'))[0]
            def esperar(condicion,plazo=3):
                fin=time.monotonic()+plazo
                while not condicion() and time.monotonic()<fin:root.update();time.sleep(.005)
                root.update();return bool(condicion())
            real_crear=G.J.TANDAS.crear;latidos=[]
            def pulso():
                latidos.append(time.monotonic())
                if not app._cerrando.is_set():root.after(20,pulso)
            root.after(1,pulso)
            def lento(*args,**kw):
                for _ in range(20):
                    if kw.get('control'):kw['control']()
                    time.sleep(.02)
                return real_crear(*args,**kw)
            with patch.object(G.J.TANDAS,'crear',side_effect=lento):
                inicio=time.monotonic()
                root.tk.call(enlace,'copy','copy',1,'','', '', '',datos,'<<Drop>>','DND_Files','', 'DND_Files','DND_Files','DND_Files','DND_Files',str(app.composer),10,10)
                comprobar('drop_no_bloquea_evento',time.monotonic()-inicio<.2)
                comprobar('preparacion_termina',esperar(lambda:not app.pendiente_actual))
            comprobar('ventana_responde_durante_preparacion',len(latidos)>=5,{'latidos':len(latidos)})
            comprobar('drop_multiarchivo_Tcl',len(app.pendientes)==1 and bool(app.pendientes[0].get('tanda_id')))
            if app.pendientes:
                d=G.J.TANDAS.cargar(app.pendientes[0]['tanda_id'])
                comprobar('drop_preserva_nombres',sorted(x['nombre'] for x in d['archivos'])==sorted(f.name for f in archivos))
                anterior=app.pendientes[0]['tanda_id'];activa=G.J.TANDAS.RAIZ/'activa.json';contenido=activa.read_bytes()
                with patch.object(G.J.TANDAS,'crear',side_effect=lento):
                    app._adjuntar_tanda([str(archivos[0])]);app.cancelar_lectura()
                    comprobar('cancelar_preparacion_termina',esperar(lambda:not app.pendiente_actual))
                comprobar('cancelar_conserva_adjuntos_previos',app.pendientes[0]['tanda_id']==anterior and activa.read_bytes()==contenido)
            app.eventos.put(('indexando',True));app.eventos.put(('progreso_adjuntos',{'archivo':'Sintético.pdf','archivos':1,'total_archivos':2,'paginas':50,'unidades':50,'trozos':12,'segundos':3,'eta_segundos':3}))
            app._procesar_eventos();root.update()
            comprobar('cancelar_activo',str(app.boton_cancelar_adjuntos['state'])=='normal')
            app.cancelar_lectura();root.update()
            comprobar('cancelacion_senal',app._cancelar_adjuntos.is_set() and str(app.boton_cancelar_adjuntos['state'])=='disabled')
            app.eventos.put(('indexando',False));app._procesar_eventos();root.update()
            comprobar('controles_se_recuperan',str(app.boton_cancelar_adjuntos['state'])=='disabled')
            try:
                root.update();capturar_ventana(root,a.salida/'ventana_sintetica.png')
            except Exception as e:resultados.append({'prueba':'captura_ventana','ok':False,'detalle':type(e).__name__})
        except Exception as e:
            resultados.append({'prueba':'excepcion_arnes','ok':False,'detalle':type(e).__name__+': '+str(e)[:300]})
        finally:
            if 'app' in locals():app._cerrando.set();app._cancelar_adjuntos.set()
            root.destroy()
        (a.salida/'widgets_reales.json').write_text(json.dumps({'resultados':resultados,'alcance':'Tk y TkDND reales; eventos sintéticos dentro de la propia ventana. Sin gesto físico entre aplicaciones, sin modelo ni captura en Segundo Cerebro.'},ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(resultados,ensure_ascii=False))
        return 0 if all(x['ok'] for x in resultados) else 1


if __name__=='__main__':raise SystemExit(main())
