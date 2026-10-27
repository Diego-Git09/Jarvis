"""Listas Tcl reales y registro simulado de eventos, sin abrir ventanas."""
import hashlib
import json
from pathlib import Path
import tempfile
import tkinter
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import arrastre_adjuntos as A


class Widget:
    def __init__(self):self.eventos={};self.registrado=False;self.tipo=''
    def drop_target_register(self,tipo):self.registrado=True;self.tipo=tipo
    def drop_target_unregister(self):self.registrado=False
    def dnd_bind(self,nombre,callback):self.eventos[nombre]=callback


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tk=tkinter.Tcl()
        self.avisos=[]
        self.root=SimpleNamespace(tk=self.tk,event_generate=lambda *a,**kw:self.avisos.append((a,kw)))

    def test_lista_tcl_preserva_tildes_espacios_llaves_y_varios_archivos(self):
        datos='{/tmp/Informe  Ñuñoa.pdf} {/tmp/carpeta con espacios/código.py} {/tmp/a{b}.txt}'
        self.assertEqual(A.rutas_del_evento(self.root,datos),('/tmp/Informe  Ñuñoa.pdf','/tmp/carpeta con espacios/código.py','/tmp/a{b}.txt'))

    def test_splitlist_no_evalua_scripts_ni_caracteres_de_shell(self):
        self.tk.setvar('JARVIS_NO_EJECUTAR','intacto')
        datos='{/tmp/[set JARVIS_NO_EJECUTAR cambiado];$(touch no).sql}'
        self.assertEqual(A.rutas_del_evento(self.root,datos),('/tmp/[set JARVIS_NO_EJECUTAR cambiado];$(touch no).sql',))
        self.assertEqual(self.tk.getvar('JARVIS_NO_EJECUTAR'),'intacto')

    def test_uri_local_se_decodifica_una_vez_sin_alterar_nombres(self):
        datos='file:///tmp/Informe%20%C3%91u%C3%B1oa.pdf file://localhost/tmp/Hoja%2520literal.xlsm'
        self.assertEqual(A.rutas_del_evento(self.root,datos),('/tmp/Informe Ñuñoa.pdf','/tmp/Hoja%20literal.xlsm'))

    def test_urls_ubicaciones_remotas_y_rutas_ambiguas_se_rechazan(self):
        casos=['https://example.com/archivo.pdf','smb://servidor/a','file://otro-pc/tmp/a',
               'file://usuario@localhost/tmp/a','file://localhost:42/tmp/a','file:///tmp/a?token=x',
               'file:///tmp/a#fragmento','../fuera.txt','archivo.txt','//servidor/carpeta/a',
               '/tmp/../fuera','file:///tmp/%2e%2e/fuera','file:///tmp/%XX','file:///tmp/%FF']
        for datos in casos:
            with self.subTest(datos=datos):
                with self.assertRaises(ValueError):A.rutas_del_evento(self.root,datos)

    def test_nulos_y_controles_incluso_percent_encoded_se_rechazan(self):
        for datos in ['/tmp/a\x00b','{/tmp/a\nb}','file:///tmp/a%00b','file:///tmp/a%0Ab',
                      '{file://localhos\nt/tmp/a}']:
            with self.subTest(datos=repr(datos)):
                with self.assertRaises(ValueError):A.rutas_del_evento(self.root,datos)

    def test_lista_mal_formada_vacia_o_excesiva_se_rechaza(self):
        for datos in ['', '{/tmp/incompleta', ' '.join('/tmp/a'+str(n) for n in range(201)), 'x'*(A.MAX_DATOS+1)]:
            with self.assertRaises(ValueError):A.rutas_del_evento(self.root,datos)
        self.assertEqual(A.rutas_del_evento(self.root,'/tmp/a /tmp/a /tmp/b'),('/tmp/a','/tmp/b'))

    def backend(self,require=None):
        return SimpleNamespace(TkinterDnD=SimpleNamespace(require=require or (lambda _: '2.10.3')),
                               DND_FILES='DND_Files',COPY='copy',REFUSE_DROP='refuse_drop')

    def test_instalar_varios_widgets_entrega_tupla_sin_autorizar_ni_ejecutar(self):
        a,b=Widget(),Widget();recibidos=[]
        with patch.object(A,'_cargar_backend',return_value=self.backend()):
            estado=A.instalar(self.root,[a,b,a],lambda rutas:recibidos.append(rutas))
        self.assertTrue(estado['ok']);self.assertEqual(estado['version'],'2.10.3')
        self.assertTrue(a.registrado and b.registrado);self.assertEqual(a.tipo,'DND_Files')
        self.assertEqual(a.eventos['<<DropEnter>>'](None),'copy')
        resultado=b.eventos['<<Drop>>'](SimpleNamespace(data='{/tmp/Caso Ñuñoa.pdf} /tmp/prueba.sql'))
        self.assertEqual(resultado,'copy');self.assertEqual(recibidos,[('/tmp/Caso Ñuñoa.pdf','/tmp/prueba.sql')])

    def test_callback_puede_rechazar_y_origen_no_recibe_orden_de_mover(self):
        widget=Widget()
        with patch.object(A,'_cargar_backend',return_value=self.backend()):
            A.instalar(self.root,[widget],lambda _:False)
        self.assertEqual(widget.eventos['<<DropPosition>>'](None),'copy')
        self.assertEqual(widget.eventos['<<Drop>>'](SimpleNamespace(data='/tmp/a')),'refuse_drop')

    def test_arrastre_invalido_no_llama_callback_y_avisa_sin_cerrar_chat(self):
        widget=Widget();callback=[]
        with patch.object(A,'_cargar_backend',return_value=self.backend()):
            estado=A.instalar(self.root,[widget],lambda rutas:callback.append(rutas))
        self.assertEqual(widget.eventos['<<Drop>>'](SimpleNamespace(data='https://example.com/a')),'refuse_drop')
        self.assertFalse(callback);self.assertIn('locales',estado['error'])
        self.assertEqual(self.avisos[0][0],('<<JarvisArrastreError>>',))

    def test_excepcion_callback_no_sale_al_bucle_de_tk(self):
        for tipo in (RuntimeError,ValueError,OSError):
            with self.subTest(tipo=tipo.__name__):
                widget=Widget()
                def falla(_):raise tipo('Detalles privados que no deben copiarse al aviso')
                with patch.object(A,'_cargar_backend',return_value=self.backend()):
                    estado=A.instalar(self.root,[widget],falla)
                self.assertEqual(widget.eventos['<<Drop>>'](SimpleNamespace(data='/tmp/a')),'refuse_drop')
                self.assertNotIn('Detalles privados',estado['error']);self.assertIn('Adjuntar',estado['error'])

    def test_sin_display_o_biblioteca_el_chat_puede_seguir_con_adjuntar(self):
        def no_display(_):raise tkinter.TclError('no display name')
        with patch.object(A,'_cargar_backend',return_value=self.backend(no_display)):
            estado=A.instalar(self.root,[Widget()],lambda _:None)
        self.assertFalse(estado['ok']);self.assertIn('Adjuntar',estado['error'])

    def test_fallo_parcial_retira_destinos_y_no_deja_media_instalacion(self):
        correcto=Widget()
        with patch.object(A,'_cargar_backend',return_value=self.backend()):
            estado=A.instalar(self.root,[correcto,object()],lambda _:None)
        self.assertFalse(estado['ok']);self.assertFalse(correcto.registrado)

    def test_procedencia_oficial_y_huellas_de_copia_incluyen_tcl8_y_tcl9(self):
        self.assertEqual(A.verificar_copia(),'0.6.4')
        d=json.loads((A.TERCEROS/'TKINTERDND2_SHA256.json').read_text())
        self.assertIn('tkdnd/linux-x64/libtkdnd2.10.3.so',d['archivos'])
        self.assertIn('tkdnd/linux-x64-tcl9/libtcl9tkdnd2.10.3.so',d['archivos'])
        self.assertIn('MIT License',(A.TERCEROS/'tkinterdnd2/LICENSE').read_text())

    def test_integridad_fallida_no_importa_codigo_nativo(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'tkinterdnd2').mkdir();(base/'tkinterdnd2/x').write_text('alterado')
            d={'version':'0.6.4','wheel_sha256':'4b11e0ac6febd8609faf154851d782eca4068bfa68a88ca3d3dded8294367f80',
               'archivos':{'x':hashlib.sha256(b'original').hexdigest()}}
            (base/'TKINTERDND2_SHA256.json').write_text(json.dumps(d))
            with patch.object(A,'TERCEROS',base):
                with self.assertRaises(ValueError):A.verificar_copia()


if __name__=='__main__':unittest.main()
