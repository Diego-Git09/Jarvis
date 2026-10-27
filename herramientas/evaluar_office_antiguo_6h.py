"""Genera DOC/XLS/PPT sintéticos con la suite aislada y comprueba su lectura."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time
import zipfile
import shutil
import struct
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
CASOS=[('doc','odt','text','doc:MS Word 97','docx:Office Open XML Text','ORO_DOC_A17'),
       ('xls','ods','spreadsheet','xls:MS Excel 97','xlsx:Calc MS Excel 2007 XML','ORO_XLS_B28'),
       ('ppt','odp','presentation','ppt:MS PowerPoint 97','odp:impress8','ORO_PPT_C39')]


def fuente(p,tipo,oro):
    if tipo=='text':cuerpo=f'<office:text><text:p>{oro} presupuesto 271</text:p></office:text>'
    elif tipo=='spreadsheet':cuerpo=f'<office:spreadsheet><table:table table:name="Datos"><table:table-row><table:table-cell office:value-type="string"><text:p>{oro}</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="42"><text:p>42</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet>'
    else:cuerpo=f'<office:presentation><draw:page draw:name="Diapositiva1"><draw:frame svg:x="1cm" svg:y="1cm" svg:width="20cm" svg:height="5cm"><draw:text-box><text:p>{oro} presupuesto 389</text:p></draw:text-box></draw:frame></draw:page></office:presentation>'
    mime='application/vnd.oasis.opendocument.'+tipo
    xml=f'''<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" office:version="1.2"><office:body>{cuerpo}</office:body></office:document-content>'''
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('mimetype',mime,compress_type=zipfile.ZIP_STORED);z.writestr('content.xml',xml)
        z.writestr('META-INF/manifest.xml',f'''<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>''')


def main():
    p=argparse.ArgumentParser();p.add_argument('--ronda',required=True);p.add_argument('--indexar',action='store_true');p.add_argument('--verificar-rechazo',action='store_true');a=p.parse_args()
    if not a.ronda.replace('_','').isalnum():raise ValueError('Ronda inválida.')
    salida=BASE/'registros/reportes/mejora_6h_20261014/office'/(a.ronda+'.json')
    if salida.exists():raise ValueError('La ronda ya existe; se conserva.')
    resultados=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-office-datos-') as temporal:
        os.environ.update(JARVIS_DIR=temporal,JARVIS_PRUEBAS='1')
        trabajo=Path(temporal,'trabajo');trabajo.mkdir()
        import office_seguro as O
        import lectores_adjuntos as R
        import tandas_documentales as T
        import libros_jarvis as X
        O.MAX_AS=512*1024**2
        for ext,moderno,tipo,filtro,intermedio,oro in CASOS:
            base=trabajo/ext;base.mkdir();original=base/('fuente.'+moderno);fuente(original,tipo,oro)
            salida_lo=base/'salida';perfil=base/'perfil';salida_lo.mkdir();perfil.mkdir();O._perfil(perfil)
            bwrap,prlimit=O._herramientas();inicio=time.monotonic();fila={'tipo':ext,'oro':oro,'sintetico':True,'sin_macros_ni_formulas':True}
            try:
                O._ejecutar(O._comando(original,salida_lo,perfil,filtro,bwrap,prlimit),base/'generacion.log',perfil)
                antiguo=salida_lo/('fuente.'+ext)
                if not antiguo.is_file():raise ValueError('No se generó el formato antiguo.')
                fila['bytes_antiguo']=antiguo.stat().st_size
                with O.abrir_convertido(antiguo,intermedio) as convertido:
                    item={'nombre':antiguo.name,'tipo_real':convertido.suffix,'aviso':''}
                    if ext=='xls':texto='\n'.join(t for _,t in X.unidades(convertido,10000,item))
                    else:texto='\n'.join(t for _,t in R._zip_xml(convertido,item,10000))
                fila.update(ok=oro in texto,texto=texto[:4000])
                if a.indexar:
                    T.configurar_recursos(dict(T.RECURSOS_DEFAULT,mb_proceso=512))
                    d=T.indexar(T.crear([antiguo])['id'],False);r=T.buscar(d['id'],oro)
                    fila['indice']=d['archivos'][0];fila['recuperacion']=r
                    fila['ok']=fila['ok'] and any(oro in x['texto'] for x in r['trozos'])
                if a.verificar_rechazo and ext=='xls':
                    # Un archivo OLE real con una cabecera BIFF prohibida.
                    # No contiene una fórmula válida y JAMÁS se abre con LO.
                    import olefile
                    prohibido=base/'no_convertir.xls';shutil.copyfile(antiguo,prohibido)
                    with olefile.OleFileIO(str(prohibido),write_mode=True) as ole:
                        datos=bytearray(ole.openstream('Workbook').read());offset=0
                        while offset+4<=len(datos):
                            ident,tam=struct.unpack_from('<HH',datos,offset)
                            if ident==0x000A:struct.pack_into('<H',datos,offset,0x0006);break
                            offset+=4+tam
                        else:raise ValueError('No encontré el registro EOF para el ensayo BIFF.')
                        ole.write_stream('Workbook',bytes(datos))
                    rechazado=False
                    with patch.object(O,'_ejecutar',side_effect=AssertionError('El archivo prohibido no debe abrirse')) as abrir:
                        try:
                            with O.abrir_convertido(prohibido,intermedio):pass
                        except ValueError as e:rechazado='fórmulas' in str(e)
                    fila['registro_formula_rechazado_antes_de_lo']=rechazado and not abrir.called
                    fila['ok']=fila['ok'] and fila['registro_formula_rechazado_antes_de_lo']
            except (OSError,ValueError) as e:
                fila.update(ok=False,error=type(e).__name__+': '+str(e))
                fila['log_generacion']=(base/'generacion.log').read_text(errors='replace')[:5000] if (base/'generacion.log').exists() else ''
            fila['segundos']=round(time.monotonic()-inicio,3);resultados.append(fila);print(json.dumps(fila,ensure_ascii=False),flush=True)
    salida.write_text(json.dumps({'ronda':a.ronda,'casos':resultados,'aprobados':sum(x['ok'] for x in resultados),'limite_as_mib':512,'alcance':'Tres documentos mínimos generados por LO aislado, sin macros ni fórmulas. No acredita todos los documentos antiguos ni un libro XLS con fórmulas.'},ensure_ascii=False,indent=2)+'\n')
    return 0 if all(x['ok'] for x in resultados) else 1


if __name__=='__main__':raise SystemExit(main())
