"""Herramientas de SOLO LECTURA para Jarvis.

Usan trabajo y carpetas personales autorizadas. El código (no el modelo)
comprueba cada ruta. No escriben, no borran, no ejecutan nada.
"""
import json
import os
from datetime import datetime
from pathlib import Path

from entorno_jarvis import TRABAJO, REGISTROS
import acceso_archivos as ACCESO

RAIZ = TRABAJO.resolve()
REGISTRO = REGISTROS / "jarvis.jsonl"
MAX_BYTES_LEER = 20_000        # tope al leer un archivo
MAX_BYTES_BUSCAR = 1_000_000   # no busca dentro de archivos mayores
MAX_RESULTADOS = 50


class FueraDeAlcance(Exception):
    pass


def _registrar(herramienta, argumentos, ok, detalle):
    """Anota qué se pidió y qué pasó (una línea JSON por llamada)."""
    linea = {"fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
             "herramienta":herramienta,"argumentos":argumentos,"ok":ok,"detalle":detalle}
    try:
        REGISTRO.parent.mkdir(parents=True,exist_ok=True)
        with open(REGISTRO,'a',encoding='utf-8') as f:
            f.write(json.dumps(linea,ensure_ascii=False)+'\n')
        return True
    except (OSError,UnicodeError):
        return False


def _resolver(ruta):
    """Convierte una ruta en absoluta y comprueba que sigue dentro de RAIZ.

    resolve() sigue enlaces simbólicos y '..', así que un enlace que
    apunte fuera de la carpeta también se rechaza.
    """
    destino = (RAIZ / Path(str(ruta)).expanduser()).resolve()
    if not ACCESO.permitido(destino,RAIZ):
        raise FueraDeAlcance(f"'{ruta}' no pertenece a una carpeta autorizada. Usa /carpetas para ver los accesos.")
    return destino


def etiqueta_ruta(ruta):
    p=Path(ruta)
    return str(p.relative_to(RAIZ)) if p==RAIZ or RAIZ in p.parents else str(p)


def recorrer_archivos(base):
    """No recorre enlaces ni carpetas ocultas al buscar en un árbol personal."""
    if base.is_file():yield base;return
    for directorio,carpetas,archivos in os.walk(base,followlinks=False):
        carpetas[:]=sorted(c for c in carpetas if not c.startswith('.') and not (Path(directorio)/c).is_symlink() and not ACCESO.protegida(Path(directorio)/c))
        for nombre in sorted(archivos):
            if not nombre.startswith('.'):yield Path(directorio)/nombre


def _ejecutar(nombre, argumentos, funcion):
    try:
        resultado = funcion()
        registrado=_registrar(nombre, argumentos, bool(resultado.get("ok",True)), "ok" if resultado.get("ok",True) else "fallo comunicado por la operación")
        r={"ok": True, **resultado}
        if not registrado:r["aviso_registro"]="No pude añadir esta operación al registro de actividad. El resultado del archivo se muestra por separado."
        return r
    except FueraDeAlcance as e:
        _registrar(nombre, argumentos, False, f"fuera de alcance: {e}")
        return {"ok": False, "error": f"Fuera de alcance: {e}"}
    except Exception as e:  # error real, se informa tal cual
        _registrar(nombre, argumentos, False, f"{type(e).__name__}: {e}")
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def listar_archivos(ruta="."):
    def hacer():
        carpeta = _resolver(ruta)
        if not carpeta.is_dir():
            raise NotADirectoryError(f"'{ruta}' no es una carpeta")
        items = []
        for hijo in sorted(carpeta.iterdir()):
            if ACCESO.protegida(hijo):continue
            if hijo.is_symlink():
                items.append({"nombre": hijo.name, "tipo": "enlace"})
            elif hijo.is_dir():
                items.append({"nombre": hijo.name, "tipo": "carpeta"})
            else:
                items.append({"nombre": hijo.name, "tipo": "archivo",
                              "bytes": hijo.stat().st_size})
        return {"ruta": etiqueta_ruta(carpeta) or ".", "items": items}
    return _ejecutar("listar_archivos", {"ruta": ruta}, hacer)


def leer_archivo(ruta):
    def hacer():
        archivo = _resolver(ruta)
        if not archivo.is_file():
            raise FileNotFoundError(f"'{ruta}' no es un archivo")
        from documentos_jarvis import EXTENSIONES,leer
        if archivo.suffix.lower() in EXTENSIONES:return {'ruta':etiqueta_ruta(archivo),**leer(archivo)}
        with open(archivo, "rb") as f:
            datos = f.read(MAX_BYTES_LEER + 1)
        if b"\x00" in datos:
            raise ValueError("el archivo parece binario, no es texto")
        cortado = len(datos) > MAX_BYTES_LEER
        texto = datos[:MAX_BYTES_LEER].decode("utf-8", errors="replace")
        return {"ruta": etiqueta_ruta(archivo),
                "contenido": texto, "cortado": cortado}
    return _ejecutar("leer_archivo", {"ruta": ruta}, hacer)


def leer_documento(ruta,inicio=1,offset=0):
    def hacer():
        archivo=_resolver(ruta)
        if not archivo.is_file():raise FileNotFoundError(f"'{ruta}' no es un archivo")
        from documentos_jarvis import leer
        return {'ruta':etiqueta_ruta(archivo),**leer(archivo,inicio,offset)}
    return _ejecutar('leer_documento',{'ruta':ruta,'inicio':inicio,'offset':offset},hacer)


def buscar_texto(texto, ruta="."):
    def hacer():
        if not texto:
            raise ValueError("falta el texto a buscar")
        base = _resolver(ruta)
        if not base.exists():raise FileNotFoundError(f"'{ruta}' no existe")
        aguja = texto.lower()
        encontrados = []
        limitado=False
        for revisados,archivo in enumerate(recorrer_archivos(base),1):
            if revisados>5000 or len(encontrados) >= MAX_RESULTADOS:
                limitado=True
                break
            if archivo.is_symlink() or not archivo.is_file():
                continue
            if archivo.stat().st_size > MAX_BYTES_BUSCAR:
                continue
            try:
                _resolver(archivo)
                contenido = archivo.read_bytes()
            except (FueraDeAlcance, OSError):
                continue
            if b"\x00" in contenido:
                continue
            lineas = contenido.decode("utf-8", errors="replace").splitlines()
            for n, linea in enumerate(lineas, start=1):
                if aguja in linea.lower():
                    encontrados.append({
                        "archivo": etiqueta_ruta(archivo),
                        "linea": n,
                        "texto": linea.strip()[:200],
                    })
                    if len(encontrados) >= MAX_RESULTADOS:
                        break
        return {"buscado": texto, "resultados": encontrados,
                "limite_alcanzado": limitado or len(encontrados) >= MAX_RESULTADOS}
    return _ejecutar("buscar_texto", {"texto": texto, "ruta": ruta}, hacer)



def leer_lineas(ruta, inicio=1, cantidad=60):
    """Lee un tramo de texto sin cargar un archivo completo en el modelo."""
    def hacer():
        if type(inicio) is not int or inicio<1 or type(cantidad) is not int or not 1<=cantidad<=200:
            raise ValueError('inicio debe ser positivo y cantidad entre 1 y 200')
        archivo=_resolver(ruta)
        if not archivo.is_file():raise FileNotFoundError('No es un archivo')
        from documentos_jarvis import EXTENSIONES,leer
        if archivo.suffix.lower() in EXTENSIONES:return {'ruta':etiqueta_ruta(archivo),**leer(archivo,inicio)}
        if archivo.stat().st_size>MAX_BYTES_BUSCAR:raise ValueError('Archivo demasiado grande para lectura por líneas (máximo 1 MB)')
        datos=archivo.read_bytes()
        if b'\x00' in datos:raise ValueError('El archivo parece binario')
        lineas=datos.decode('utf-8',errors='strict').splitlines()
        seleccion=lineas[inicio-1:inicio-1+cantidad]
        texto='\n'.join(seleccion)
        # Evita una única línea enorme que sature el contexto.
        if len(texto)>20000:raise ValueError('Ese tramo supera 20000 caracteres. Pide menos líneas o revisa el archivo fuera de Jarvis.')
        siguiente=inicio+len(seleccion) if inicio+len(seleccion)<=len(lineas) else None
        return {'ruta':etiqueta_ruta(archivo),'inicio':inicio,'lineas':seleccion,
                'contenido':texto,'total_lineas':len(lineas),'siguiente':siguiente}
    return _ejecutar('leer_lineas',{'ruta':ruta,'inicio':inicio,'cantidad':cantidad},hacer)
