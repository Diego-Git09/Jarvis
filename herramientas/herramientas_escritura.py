"""Herramientas de ESCRITURA para Jarvis (reversibles).

Actúan en trabajo y carpetas personales autorizadas. Cada respuesta separa lo que
realmente pasó: "preparado" (hay un plan), "escrito" (el archivo cambió)
y "verificado" (se volvió a leer y coincide).
"""
import difflib
import errno
import hashlib
import json
import os
import re
import uuid
import tempfile
import stat
from datetime import datetime, timezone

from herramientas_lectura import RAIZ, _resolver, _ejecutar, etiqueta_ruta

from entorno_jarvis import REGISTROS

BASE = REGISTROS
PENDIENTES = BASE / "pendientes"   # ediciones preparadas, aún sin aplicar
CAMBIOS = BASE / "cambios"         # cambios ya escritos (para revertir)
COPIAS = BASE / "copias"           # copia del archivo antes de editar
MAX_BYTES_ESCRIBIR = 100_000
MAX_BYTES_COPIAR = 2_000_000_000
_ID = re.compile(r"[0-9a-f]{8,32}")


def _hash(datos):
    return hashlib.sha256(datos).hexdigest()


def _hash_archivo(ruta):
    h=hashlib.sha256()
    with open(ruta,'rb') as f:
        while trozo:=f.read(1_048_576):h.update(trozo)
    return h.hexdigest()


def _copiar_atomico(fuente,destino,huella=None):
    """Copia binarios por bloques sin cargar el documento completo en RAM."""
    fd,tmp=tempfile.mkstemp(prefix='.jarvis-',dir=destino.parent)
    try:
        cantidad=0
        with os.fdopen(fd,'wb') as salida,open(fuente,'rb') as entrada:
            while trozo:=entrada.read(1_048_576):
                cantidad+=len(trozo)
                if cantidad>MAX_BYTES_COPIAR:raise ValueError('La copia supera 2 GB.')
                salida.write(trozo)
            salida.flush();os.fsync(salida.fileno())
        if huella is not None and _hash_archivo(tmp)!=huella:raise ValueError('El archivo cambió durante la copia; no se creó el destino.')
        os.link(tmp,destino);os.unlink(tmp)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def _trasladar_sin_sobrescribir(fuente,destino,huella):
    try:os.link(fuente,destino)
    except OSError as e:
        if e.errno!=errno.EXDEV:raise
        _copiar_atomico(fuente,destino,huella)
    if _hash_archivo(destino)!=huella or _hash_archivo(fuente)!=huella:
        raise ValueError('El origen cambió durante el traslado. Conservé ambos archivos; revisa las dos rutas.')
    fuente.unlink()


def _nuevo_id():
    return uuid.uuid4().hex[:16]


def _id_valido(valor):
    if not _ID.fullmatch(str(valor)):
        raise ValueError("identificador inválido")


def _guardar_json(carpeta, ident, datos):
    carpeta.mkdir(parents=True, exist_ok=True)
    _escribir_atomico(carpeta / f"{ident}.json", json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8"))


def _cargar_json(carpeta, ident):
    _id_valido(ident)
    ruta = carpeta / f"{ident}.json"
    if not ruta.is_file():
        raise FileNotFoundError(f"no existe el registro {ident}")
    if ruta.is_symlink() or ruta.stat().st_size>300000:
        raise ValueError("Registro inválido o demasiado grande")
    dato=json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(dato,dict):raise ValueError("Registro no válido")
    return dato


def _escribir_atomico(destino, datos, exclusivo=False,modo=None):
    """Archivo temporal único; preserva permisos, no pisa creaciones ajenas."""
    fd,tmp = tempfile.mkstemp(prefix='.jarvis-',dir=destino.parent)
    try:
        if modo is None:modo=stat.S_IMODE(destino.stat().st_mode) if destino.exists() else 0o600
        with os.fdopen(fd,'wb') as f:
            f.write(datos);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,modo)
        if exclusivo:
            os.link(tmp,destino)  # falla si el destino apareció mientras escribíamos
            os.unlink(tmp)
        else:
            os.replace(tmp,destino)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def _preparar_registro(ident, cambio):
    cambio = dict(cambio, estado="preparado", creado=datetime.now(timezone.utc).isoformat())
    _guardar_json(CAMBIOS, ident, cambio)
    return cambio


def _terminar_registro(ident, cambio, verificado, **extra):
    cambio["estado"] = "confirmado"
    try:
        _guardar_json(CAMBIOS, ident, cambio)
    except OSError:
        return {"ok":False,"id_cambio":ident,"ruta":cambio["ruta"],"escrito":True,
                "verificado":verificado,"error":"El archivo cambió, pero no pude completar su registro. Usa /cambios para revisar y, si corresponde, deshacerlo.",**extra}
    return {"id_cambio":ident,"ruta":cambio["ruta"],"escrito":True,"verificado":verificado,**extra}


def _leer_texto_estricto(archivo):
    with open(archivo, "rb") as f:
        datos = f.read(MAX_BYTES_ESCRIBIR + 1)
    if len(datos) > MAX_BYTES_ESCRIBIR:
        raise ValueError("El archivo supera 100 KB para edición")
    if b"\x00" in datos:
        raise ValueError("el archivo parece binario")
    datos.decode("utf-8")  # falla si no es texto UTF-8 válido
    return datos


def crear_archivo(ruta, contenido):
    def hacer():
        datos=contenido.encode("utf-8")
        if len(datos)>MAX_BYTES_ESCRIBIR:raise ValueError("El contenido supera 100 KB")
        destino=_resolver(ruta)
        if destino==RAIZ or destino.is_dir():raise ValueError("La ruta no es un archivo")
        if destino.exists():raise FileExistsError("El archivo ya existe; prepara una edición")
        destino.parent.mkdir(parents=True,exist_ok=True)
        ident=_nuevo_id();rel=etiqueta_ruta(destino)
        cambio=_preparar_registro(ident,{"tipo":"crear","ruta":rel,"hash_despues":_hash(datos),"revertido":False})
        _escribir_atomico(destino,datos,exclusivo=True)
        return _terminar_registro(ident,cambio,_hash_archivo(destino)==_hash(datos))
    return _ejecutar("crear_archivo",{"ruta":ruta,"bytes":len(contenido.encode('utf-8'))},hacer)


def proponer_edicion(ruta, contenido_nuevo):
    """Prepara un cambio y muestra la diferencia. NO escribe nada."""
    def hacer():
        datos_nuevos = contenido_nuevo.encode("utf-8")
        if len(datos_nuevos) > MAX_BYTES_ESCRIBIR:
            raise ValueError(f"supera {MAX_BYTES_ESCRIBIR} bytes")
        archivo = _resolver(ruta)
        if not archivo.is_file():
            raise FileNotFoundError(f"'{ruta}' no existe; use crear_archivo")
        original = _leer_texto_estricto(archivo)
        from planes_archivos import validar_hash
        validar_hash(archivo,_hash(original))
        if original == datos_nuevos:
            raise ValueError("el contenido nuevo es igual al actual")
        rel = etiqueta_ruta(archivo)
        diff = "".join(difflib.unified_diff(
            original.decode("utf-8").splitlines(keepends=True),
            contenido_nuevo.splitlines(keepends=True),
            fromfile=f"{rel} (actual)", tofile=f"{rel} (propuesto)"))
        ident = _nuevo_id()
        _guardar_json(PENDIENTES, ident, {
            "ruta": rel, "hash_original": _hash(original),
            "contenido_nuevo": contenido_nuevo})
        return {"id_propuesta": ident, "ruta": rel, "diferencia": diff,
                "preparado": True, "escrito": False}
    return _ejecutar("proponer_edicion", {"ruta": ruta}, hacer)


def aplicar_edicion(id_propuesta):
    def hacer():
        prop=_cargar_json(PENDIENTES,id_propuesta);archivo=_resolver(prop["ruta"])
        if not archivo.is_file():raise FileNotFoundError("El archivo ya no existe")
        actual=_leer_texto_estricto(archivo)
        if _hash(actual)!=prop["hash_original"]:raise ValueError("El archivo cambió desde la propuesta. Prepare una nueva; no se escribió nada")
        nuevo=prop["contenido_nuevo"].encode("utf-8")
        if len(nuevo)>MAX_BYTES_ESCRIBIR:raise ValueError("La propuesta supera 100 KB")
        ident=_nuevo_id();COPIAS.mkdir(parents=True,exist_ok=True)
        _escribir_atomico(COPIAS/f"{ident}.orig",actual,exclusivo=True)
        cambio=_preparar_registro(ident,{"tipo":"editar","ruta":prop["ruta"],"hash_antes":_hash(actual),"hash_despues":_hash(nuevo),"revertido":False})
        # Segunda comprobación después de guardar la copia y preparar el registro.
        if _hash(_leer_texto_estricto(archivo))!=prop["hash_original"]:raise ValueError("El archivo cambió mientras preparaba la escritura. No se escribió nada")
        _escribir_atomico(archivo,nuevo)
        resultado=_terminar_registro(ident,cambio,_hash_archivo(archivo)==_hash(nuevo))
        if resultado.get("ok",True):
            try:(PENDIENTES/f"{id_propuesta}.json").unlink()
            except OSError:resultado["aviso"]="El cambio se completó; quedó una propuesta antigua que ya no puede aplicarse sobre este contenido."
        return resultado
    return _ejecutar("aplicar_edicion",{"id_propuesta":id_propuesta},hacer)


def revertir_cambio(id_cambio):
    """Deshace un cambio, solo si el archivo sigue como lo dejó ese cambio."""
    def hacer():
        cambio = _cargar_json(CAMBIOS, id_cambio)
        if cambio["revertido"]:
            raise ValueError("este cambio ya fue revertido")
        archivo = _resolver(cambio["ruta"])
        if cambio["tipo"] == "carpeta":
            if not archivo.is_dir():raise FileNotFoundError("la carpeta ya no existe")
            archivo.rmdir()  # solo permite borrar una carpeta vacía
            cambio["revertido"] = True
            _guardar_json(CAMBIOS,id_cambio,cambio)
            return {"ruta":cambio["ruta"],"revertido":True,"verificado":not archivo.exists()}
        if not archivo.is_file():
            raise FileNotFoundError("el archivo ya no existe")
        if _hash_archivo(archivo) != cambio["hash_despues"]:
            raise ValueError("el archivo cambió después de ese cambio; "
                             "no se revirtió nada")
        if cambio["tipo"] == "mover":
            origen=_resolver(cambio["origen"])
            if origen.exists():raise FileExistsError("La ruta original ya está ocupada; no se revirtió")
            if not origen.parent.is_dir():raise FileNotFoundError("La carpeta original no existe")
            _trasladar_sin_sobrescribir(archivo,origen,cambio['hash_despues'])
            verificado=origen.is_file() and _hash(origen.read_bytes())==cambio["hash_despues"] and not archivo.exists()
        elif cambio["tipo"] == "crear":
            archivo.unlink()
            verificado = not archivo.exists()
        else:
            original = (COPIAS / f"{id_cambio}.orig").read_bytes()
            _escribir_atomico(archivo, original)
            verificado = _hash_archivo(archivo) == cambio["hash_antes"]
        cambio["revertido"] = True
        _guardar_json(CAMBIOS, id_cambio, cambio)
        return {"ruta": cambio["ruta"], "revertido": True,
                "verificado": verificado}
    return _ejecutar("revertir_cambio", {"id_cambio": id_cambio}, hacer)

def crear_carpeta(ruta):
    def hacer():
        destino=_resolver(ruta)
        if destino==RAIZ or destino.exists():raise FileExistsError("La ruta ya existe")
        if not destino.parent.is_dir():raise FileNotFoundError("Primero crea la carpeta padre")
        ident=_nuevo_id();rel=etiqueta_ruta(destino)
        cambio=_preparar_registro(ident,{"tipo":"carpeta","ruta":rel,"revertido":False})
        destino.mkdir(mode=0o700)
        return _terminar_registro(ident,cambio,destino.is_dir())
    return _ejecutar("crear_carpeta",{"ruta":ruta},hacer)


def copiar_archivo(origen, destino):
    def hacer():
        fuente=_resolver(origen);objetivo=_resolver(destino)
        if not fuente.is_file():raise FileNotFoundError("El origen no es un archivo")
        if objetivo.exists():raise FileExistsError("El destino ya existe; no se sobrescribió")
        if not objetivo.parent.is_dir():raise FileNotFoundError("La carpeta destino no existe")
        if fuente.stat().st_size>MAX_BYTES_COPIAR:raise ValueError("El archivo supera 2 GB para copiar")
        huella=_hash_archivo(fuente)
        from planes_archivos import validar_hash
        validar_hash(fuente,huella)
        ident=_nuevo_id();rel=etiqueta_ruta(objetivo)
        cambio=_preparar_registro(ident,{"tipo":"crear","ruta":rel,"hash_despues":huella,"revertido":False})
        _copiar_atomico(fuente,objetivo,huella)
        return _terminar_registro(ident,cambio,_hash_archivo(objetivo)==huella)
    return _ejecutar("copiar_archivo",{"origen":origen,"destino":destino},hacer)


def mover_archivo(origen, destino):
    def hacer():
        fuente=_resolver(origen);objetivo=_resolver(destino)
        if not fuente.is_file():raise FileNotFoundError("El origen no es un archivo")
        if objetivo.exists():raise FileExistsError("El destino ya existe; no se sobrescribió")
        if not objetivo.parent.is_dir():raise FileNotFoundError("La carpeta destino no existe")
        if fuente.stat().st_size>MAX_BYTES_COPIAR:raise ValueError("El archivo supera 2 GB para mover")
        huella=_hash_archivo(fuente)
        from planes_archivos import validar_hash
        validar_hash(fuente,huella)
        ident=_nuevo_id();rel=etiqueta_ruta(objetivo);orig=etiqueta_ruta(fuente)
        cambio=_preparar_registro(ident,{"tipo":"mover","ruta":rel,"origen":orig,"hash_despues":huella,"revertido":False})
        try:_trasladar_sin_sobrescribir(fuente,objetivo,huella)
        except (OSError,ValueError):
            if not objetivo.exists():raise
            return {"ok":False,"id_cambio":ident,"ruta":rel,"escrito":True,"verificado":False,
                    "error":"Se creó el destino, pero no pude retirar el origen. Ambos archivos se conservaron; revisa las dos rutas antes de continuar."}
        return _terminar_registro(ident,cambio,not fuente.exists() and _hash_archivo(objetivo)==huella,origen=orig)
    return _ejecutar("mover_archivo",{"origen":origen,"destino":destino},hacer)


def listar_cambios(limite=20):
    def hacer():
        if type(limite) is not int or not 1<=limite<=50:raise ValueError('Límite entre 1 y 50')
        items=[]
        if CAMBIOS.exists():
            for p in sorted(CAMBIOS.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:limite]:
                try:
                    d=json.loads(p.read_text(encoding='utf-8'))
                    if isinstance(d,dict) and all(k in d for k in ('tipo','ruta','revertido')):
                        estado=d.get('estado','confirmado')
                        aplicado=not d['revertido']
                        if estado=='preparado':
                            destino=_resolver(d['ruta'])
                            if d['tipo']=='carpeta':aplicado=destino.is_dir()
                            else:aplicado=destino.is_file() and destino.stat().st_size<=MAX_BYTES_COPIAR and _hash_archivo(destino)==d.get('hash_despues')
                            if d['tipo']=='mover' and _resolver(d['origen']).exists():aplicado=False
                            estado='registro_pendiente' if aplicado else 'no_aplicado'
                        items.append({'id_cambio':p.stem,'estado':estado,'aplicado':aplicado,'tipo':d['tipo'],'ruta':d['ruta'],
                                      'revertido':d['revertido'],'fecha':p.stat().st_mtime})
                except Exception:continue
        return {'cambios':items}
    return _ejecutar('listar_cambios',{'limite':limite},hacer)


def proponer_reemplazo(ruta, texto_actual, texto_nuevo, todas=False):
    """Sustitución literal que conserva todo el contenido ajeno al cambio."""
    if not isinstance(texto_actual,str) or not texto_actual:
        return {'ok':False,'error':'El texto a reemplazar no puede estar vacío'}
    if type(todas) is not bool:return {'ok':False,'error':'Todas debe ser verdadero o falso'}
    try:
        archivo=_resolver(ruta);contenido=_leer_texto_estricto(archivo).decode('utf-8')
        coincidencias=contenido.count(texto_actual)
        if coincidencias==0:return {'ok':False,'error':'No encontré ese texto exacto. No cambié nada.'}
        if coincidencias>1 and not todas:return {'ok':False,'error':f'Hay {coincidencias} coincidencias. Indica si quieres reemplazarlas todas o usa un texto más específico.'}
        nuevo=contenido.replace(texto_actual,texto_nuevo) if todas else contenido.replace(texto_actual,texto_nuevo,1)
        r=proponer_edicion(ruta,nuevo)
        if r.get('ok'):r['coincidencias']=coincidencias
        return r
    except Exception as e:return {'ok':False,'error':str(e)}
