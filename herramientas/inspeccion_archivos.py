"""Información, comparación y búsqueda por nombre dentro de la carpeta de trabajo."""
import difflib
import fnmatch
import mimetypes
import os
from datetime import datetime,timezone
import herramientas_lectura as L


def informacion_archivo(ruta):
    def hacer():
        archivo=L._resolver(ruta)
        if not archivo.is_file():raise FileNotFoundError('La ruta no es un archivo')
        datos=archivo.stat()
        with archivo.open('rb') as f:muestra=f.read(20000)
        binario=b'\x00' in muestra
        utf8=False
        if not binario:
            try:
                import codecs
                codecs.getincrementaldecoder('utf-8')().decode(muestra,final=datos.st_size<=20000)
                utf8=True
            except UnicodeError:pass
        return {'ruta':L.etiqueta_ruta(archivo),'bytes':datos.st_size,
                'modificado':datetime.fromtimestamp(datos.st_mtime,timezone.utc).isoformat(),
                'tipo':mimetypes.guess_type(archivo.name)[0] or 'tipo desconocido',
                'texto_utf8':utf8,'muestra_parcial':datos.st_size>20000}
    return L._ejecutar('informacion_archivo',{'ruta':ruta},hacer)


def comparar_archivos(primero,segundo):
    def hacer():
        textos=[];rutas=[]
        for nombre in (primero,segundo):
            archivo=L._resolver(nombre)
            if not archivo.is_file():raise FileNotFoundError(f'{nombre} no es un archivo')
            with archivo.open('rb') as f:datos=f.read(100001)
            if len(datos)>100000:raise ValueError('Compara archivos de hasta 100 KB')
            if b'\x00' in datos:raise ValueError('La comparación requiere archivos de texto')
            textos.append(datos.decode('utf-8'));rutas.append(L.etiqueta_ruta(archivo))
        diff='\n'.join(difflib.unified_diff(textos[0].splitlines(),textos[1].splitlines(),
                                       fromfile=rutas[0],tofile=rutas[1],lineterm=''))
        return {'primero':rutas[0],'segundo':rutas[1],'iguales':textos[0]==textos[1],
                'diferencia':diff[:20000],'recortado':len(diff)>20000,
                'salto_final_primero':textos[0].endswith('\n'),'salto_final_segundo':textos[1].endswith('\n')}
    return L._ejecutar('comparar_archivos',{'primero':primero,'segundo':segundo},hacer)


def encontrar_archivos(nombre,ruta='.'):
    def hacer():
        if not isinstance(nombre,str) or not nombre.strip() or len(nombre)>200:raise ValueError('Escribe un nombre o patrón de hasta 200 caracteres')
        base=L._resolver(ruta)
        if not base.is_dir():raise NotADirectoryError('La ruta de búsqueda no es una carpeta')
        patron=nombre.casefold();comodin=any(c in nombre for c in '*?[')
        encontrados=[];revisados=0;limitado=False;directorios=0
        for directorio,carpetas,archivos in os.walk(base,followlinks=False):
            directorios+=1
            if directorios>5000:limitado=True;break
            carpetas[:]=sorted(c for c in carpetas if not c.startswith('.') and not (L.Path(directorio)/c).is_symlink() and not L.ACCESO.protegida(L.Path(directorio)/c))
            for archivo in sorted(archivos):
                revisados+=1
                if revisados>5000 or len(encontrados)>=50:limitado=True;break
                p=L.Path(directorio)/archivo
                if p.is_symlink():continue
                coincide=fnmatch.fnmatchcase(archivo.casefold(),patron) if comodin else patron in archivo.casefold()
                if coincide:
                    try:
                        seguro=L._resolver(p)
                        encontrados.append({'ruta':L.etiqueta_ruta(seguro),'bytes':seguro.stat().st_size})
                    except (OSError,L.FueraDeAlcance):continue
            if limitado:break
        return {'nombre':nombre,'archivos':encontrados,'limite_alcanzado':limitado,'revisados':min(revisados,5000)}
    return L._ejecutar('encontrar_archivos',{'nombre':nombre,'ruta':ruta},hacer)
