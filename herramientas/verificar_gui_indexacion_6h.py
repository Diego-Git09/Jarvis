"""Indexación PDF301 real desde la GUI: progreso, cancelación y reanudación.

Dos procesos de lectura reales limitados. Embeddings desactivados únicamente
en este arnés; transporte de modelos/MCP prohibido. Ventana propia fuera de
pantalla, sin foco, puntero, capturas ni archivos personales.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch


def main(destino):
    if destino.exists():raise ValueError('No sobrescribir una verificación anterior.')
    destino.parent.mkdir(parents=True,exist_ok=True)
    resultados=[];latidos=[];detalles=[];llamadas=[];intentos_red=[];reanudacion=[];fase=''
    def comprobar(nombre,valor,detalle=None):resultados.append({'prueba':nombre,'ok':bool(valor),'detalle':detalle})
    with tempfile.TemporaryDirectory(prefix='jarvis-gui-indexacion-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',JARVIS_DEEPSEEK='0')
        trabajo=Path(tmp,'trabajo');trabajo.mkdir()
        from medir_adjuntos_pesados_6h import pdf
        archivo=trabajo/'lectura301.pdf';pdf(archivo)
        huella=hashlib.sha256(archivo.read_bytes()).hexdigest()
        import tkinter as tk
        import interfaz_grafica as G
        from contextlib import ExitStack
        root=tk.Tk();root.withdraw();root.overrideredirect(True);root.geometry('1024x768+20000+20000');app=None
        real=G.J.TANDAS.indexar
        def indexar(ident,semantico=True,embedding=None,progreso=None,cancelar=None,detalle_progreso=None):
            llamadas.append({'tanda':ident,'semantico_solicitado':semantico,'semantico_arnes':False})
            return real(ident,False,embedding,progreso,cancelar,detalle_progreso)
        def prohibido(*a,**k):
            intentos_red.append('Solicitud prohibida durante el arnés');raise AssertionError('Sin modelo/MCP en esta verificación.')
        def esperar(condicion,segundos):
            fin=time.monotonic()+segundos
            while not condicion() and time.monotonic()<fin:root.update();time.sleep(.005)
            root.update();return bool(condicion())
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(G.Aplicacion,'_inicializar_estado',return_value=None))
                stack.enter_context(patch.object(G.J.TANDAS,'indexar',side_effect=indexar))
                stack.enter_context(patch.object(G.J.O,'solicitar',side_effect=prohibido))
                stack.enter_context(patch.object(G.J.CEREBRO,'llamar',side_effect=prohibido))
                app=G.Aplicacion(root,SimpleNamespace(cerrar=lambda:None))
                root.geometry('1024x768+20000+20000');root.deiconify();root.update()
                def pulso():
                    latidos.append(time.monotonic())
                    texto=str(app.detalle_adjuntos['text'])
                    if not detalles or detalles[-1]!=texto:detalles.append(texto)
                    if fase=='reanudacion':
                        unidades=re.search(r'unidades (\d+)',texto)
                        reanudacion.append({'unidades':int(unidades[1]) if unidades else 0,
                            'cancelar':str(app.boton_cancelar_adjuntos['state'])=='normal'})
                    if not app._cerrando.is_set():root.after(20,pulso)
                root.after(1,pulso)
                app._adjuntar_tanda([str(archivo)])
                comprobar('preparacion_real',esperar(lambda:not app.pendiente_actual,8) and bool(app.pendientes))
                if not app.pendientes:raise ValueError('No se preparó la tanda.')
                ident=app.pendientes[0]['tanda_id'];app.composer.insert('1.0','/indexar');app.enviar()
                def progreso_visible():
                    m=re.search(r'unidades (\d+)',str(app.detalle_adjuntos['text']))
                    return bool(m and int(m[1])>=10)
                comprobar('progreso_real_visible',esperar(progreso_visible,15))
                comprobar('cancelar_disponible',str(app.boton_cancelar_adjuntos['state'])=='normal')
                inicio=time.monotonic();app.boton_cancelar_adjuntos.invoke()
                comprobar('cancelacion_termina',esperar(lambda:not app.pendiente_actual,10),{'segundos':round(time.monotonic()-inicio,3)})
                parcial=G.J.TANDAS.cargar(ident)
                comprobar('tanda_cancelada_persistida',parcial.get('cancelada') and parcial['archivos'][0]['estado']=='parcial',parcial['archivos'][0]['estado'])
                with sqlite3.connect(G.J.TANDAS.RAIZ/'trozos.sqlite') as db:
                    confirmados=db.execute('SELECT count(*) FROM trozos WHERE clave=?',(parcial['archivos'][0].get('clave'),)).fetchone()[0]
                comprobar('trozos_confirmados_conservados',0<confirmados<301,confirmados)
                comprobar('pregunta_y_tanda_conservadas',app.estado.get('_tanda_documentos')==ident and 'Conservé la pregunta y la tanda' in app.chat.get('1.0','end'))
                antes=len(latidos);empezar=time.monotonic();fase='reanudacion'
                app.composer.insert('1.0','/indexar');app.enviar()
                comprobar('reanuda_desde_chat',esperar(lambda:not app.pendiente_actual,30))
                comprobar('reanudacion_actualiza_progreso',max((x['unidades'] for x in reanudacion),default=0)>=100)
                comprobar('reanudacion_permite_cancelar',any(x['cancelar'] for x in reanudacion))
                tiempo=time.monotonic()-empezar;pulsos=latidos[antes:]
                mayor=max((b-a for a,b in zip(pulsos,pulsos[1:])),default=0)
                comprobar('gui_responde_durante_lector_real',len(pulsos)>=10 and mayor<1,{'latidos':len(pulsos),'mayor_intervalo_s':round(mayor,4),'segundos_lectura_y_ui':round(tiempo,3)})
                final=G.J.TANDAS.cargar(ident);fuente=final['archivos'][0]
                comprobar('pdf301_completo_tras_reanudar',not final.get('cancelada') and fuente['estado']=='indexado' and fuente.get('paginas_leidas')==301,{'estado':fuente['estado'],'paginas':fuente.get('paginas_leidas'),'trozos':fuente.get('trozos')})
                r=G.J.TANDAS.buscar(ident,'PAGINA_ORO_301',presupuesto=5000)
                comprobar('cita_pagina301',any('página 301' in t['referencia'] and 'PAGINA_ORO_301' in t['texto'] for t in r['trozos']))
                comprobar('original_intacto',hashlib.sha256(archivo.read_bytes()).hexdigest()==huella)
                comprobar('sin_modelo_ni_mcp',not intentos_red,intentos_red)
                comprobar('dos_indexaciones_reales',len(llamadas)==2,llamadas)
                comprobar('controles_recuperados',str(app.boton_cancelar_adjuntos['state'])=='disabled' and str(app.boton_enviar['state'])=='normal')
        except Exception as e:comprobar('excepcion',False,type(e).__name__+': '+str(e)[:1000])
        finally:
            if app:
                app._cerrando.set();app._cancelar_adjuntos.set()
                ident=app.estado.get('_tanda_documentos')
                if ident:G.J.TANDAS.cancelar_indexacion(ident)
                esperar(lambda:not app.pendiente_actual,5)
            root.destroy()
    dato={'resultados':resultados,'progreso_visible':detalles[-30:],'alcance':'GUI Tk real, PDF sintético301, lector aislado real, cancelación y /indexar por el chat. Embeddings desactivados en el arnés; sin modelo/MCP. Latidos observados no garantizan latencia de cualquier equipo.'}
    destino.write_text(json.dumps(dato,ensure_ascii=False,indent=2)+'\n');destino.chmod(0o600)
    print(json.dumps(dato,ensure_ascii=False));return 0 if all(r['ok'] for r in resultados) else 1


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--salida',type=Path,required=True);a=ap.parse_args();raise SystemExit(main(a.salida))
