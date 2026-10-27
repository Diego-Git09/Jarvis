"""Pruebas de adjuntos, entrenamiento y árbol de proyectos."""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adjuntos_jarvis as A
import herramientas_lectura as L
import estructura_jarvis as E
import mejoras_jarvis as M
from interfaz_local import comando_local
from contexto_jarvis import recortar


class ClienteFalso:
    def llamar(self, nombre, args):
        if nombre == 'listar_proyectos':
            return {'proyectos': [{'proyecto':'Jarvis','recuerdos':1,'conversaciones':1,'total':2},
                                  {'proyecto':'vacío','recuerdos':0,'conversaciones':0,'total':0}]}
        if nombre == 'listar_memorias':
            return {'memorias': [{'proyecto':args['proyecto'],'titulo':'Nota de prueba','contenido':'texto',
                                  'creado':'2026-10-12T12:00:00+00:00','tipo':'recuerdo'},
                                 {'proyecto':args['proyecto'],'titulo':'Chat de prueba','contenido':'diálogo',
                                  'creado':'2026-10-12T13:00:00+00:00','tipo':'conversacion'}] if args['proyecto']=='Jarvis' else []}
        raise AssertionError(nombre)


class PruebasNuevasFunciones(unittest.TestCase):
    def test_lectura_segura_de_py_y_sql_sin_ejecucion(self):
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            for ext, text in [('.py','print("no ejecutes")'),('.sql','DELETE FROM datos;')]:
                path=Path(tmp)/('entrada'+ext);path.write_text(text,encoding='utf-8')
                self.assertEqual(A.leer_adjunto(path)['texto'],text)

    def test_lee_docx_desde_xml(self):
        datos=io.BytesIO()
        with zipfile.ZipFile(datos,'w') as z:
            z.writestr('word/document.xml','''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hola documento</w:t></w:r></w:p></w:body></w:document>''')
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            p=Path(tmp)/'nota.docx';p.write_bytes(datos.getvalue())
            self.assertEqual(A.leer_adjunto(p)['texto'],'Hola documento')

    def test_lee_xlsx_con_cadenas_compartidas(self):
        datos=io.BytesIO()
        with zipfile.ZipFile(datos,'w') as z:
            z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Datos" r:id="rId1"/></sheets></workbook>''')
            z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
            z.writestr('xl/sharedStrings.xml','''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>hola</t></si></sst>''')
            z.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>''')
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            p=Path(tmp)/'tabla.xlsx';p.write_bytes(datos.getvalue())
            self.assertEqual(A.leer_adjunto(p)['texto'],'Hoja: Datos\nA1=hola')

    def test_lee_texto_de_presentacion_pptx(self):
        datos=io.BytesIO()
        with zipfile.ZipFile(datos,'w') as z:
            z.writestr('ppt/slides/slide1.xml','''<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Hola diapositiva</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>''')
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            p=Path(tmp)/'presentacion.pptx';p.write_bytes(datos.getvalue())
            self.assertEqual(A.leer_adjunto(p)['texto'],'Diapositiva 1: Hola diapositiva')

    def test_imagen_necesita_modelo_vision(self):
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            p=Path(tmp)/'foto.png';p.write_bytes(b'png-data')
            self.assertIsNone(A.leer_adjunto(p,'qwen3:8b')['imagen'])
            self.assertTrue(A.leer_adjunto(p,'llava:7b')['imagen'])

    def test_payload_visual_no_agota_el_presupuesto_de_texto(self):
        imagen='A'*50000
        historial=[{'role':'system','content':'reglas'},
                    {'role':'user','content':'Describe la imagen','images':[imagen]}]
        recortado=recortar(historial)
        self.assertEqual(recortado[-1]['images'],[imagen])
        self.assertLess(len(recortado[-1]['content']),100)

    def test_estructura_agrupa_por_proyecto_tipo_y_fecha(self):
        data=E.consultar(ClienteFalso())
        result=E.texto(data)
        self.assertIn('▾ Jarvis',result);self.assertIn('▾ Recuerdos',result)
        self.assertIn('▾ Conversaciones',result);self.assertIn('12-10-2026 09:00:00',result)
        self.assertIn('▾ vacío',result)

    def test_estructura_recupera_todas_las_paginas(self):
        class ClientePaginado:
            llamadas=[]
            def llamar(self,nombre,args):
                if nombre=='listar_proyectos':return {'proyectos':[{'proyecto':'Jarvis','recuerdos':55,'conversaciones':0,'total':55}]}
                self.llamadas.append(args['desplazamiento'])
                inicio=args['desplazamiento']
                return {'memorias':[{'id':i+1,'titulo':f'Nota {i+1}','tipo':'recuerdo'} for i in range(inicio,min(inicio+args['limite'],55))]}
        c=ClientePaginado();datos=E.consultar(c)
        self.assertEqual(len(datos['proyectos'][0]['registros']),55)
        self.assertEqual(c.llamadas,[0,50])

    def test_entrenamiento_persiste_con_permisos_y_contexto(self):
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            original=M.ARCHIVO;M.ARCHIVO=Path(tmp)/'entrenamiento.json'
            try:
                state={};text=M.iniciar(state)
                self.assertIn('Caso:',text)
                item=M.proponer(state,'Confirma antes de mover.');self.assertTrue(item)
                M.registrar(item)
                self.assertIn('Confirma antes',M.contexto())
                self.assertEqual(M.ARCHIVO.stat().st_mode & 0o777,0o600)
            finally:M.ARCHIVO=original

    def test_comandos_de_mejoras_y_entrenamiento_solo_guardan_con_permiso(self):
        with tempfile.TemporaryDirectory(dir=L.RAIZ) as tmp:
            original=M.ARCHIVO;M.ARCHIVO=Path(tmp)/'entrenamiento.json'
            try:
                state={};settings={'modelo':'qwen3:8b','tamano_pagina':5,'modo':'normal'}
                confirm=[]
                ejecutar=lambda *a:None
                args=([],state,lambda texto:confirm.append(texto) or True,settings,lambda:None,ClienteFalso())
                ok,text=comando_local('/mejoras',*args)
                self.assertTrue(ok);self.assertIn('/entrenamiento',text)
                ok,text=comando_local('/entrenamiento',*args)
                self.assertTrue(ok);self.assertIn('Caso:',text)
                ok,text=comando_local('Confirma antes de cambiar recuerdos.',*args)
                self.assertTrue(ok);self.assertEqual(len(confirm),1)
                self.assertIn('Confirma antes',M.contexto())
                ok,text=comando_local('Muéstrame los recuerdos y conversaciones agrupados por proyecto',*args)
                self.assertTrue(ok);self.assertIn('Estructura de Segundo Cerebro',text)
            finally:M.ARCHIVO=original


if __name__=='__main__':unittest.main(verbosity=2)
