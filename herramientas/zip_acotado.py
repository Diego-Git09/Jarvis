"""Preflight del directorio ZIP antes de que ZipFile construya su lista en RAM.

Solo inspecciona cabeceras y tamaños. No extrae ni descomprime miembros.
Los límites también se verifican recorriendo las entradas reales: el contador
del EOCD puede estar manipulado. ZIP64 y archivos multidisco no se admiten.
"""
from contextlib import contextmanager
import os
import struct
import zipfile

MAX_DIRECTORIO = 4 * 1024 * 1024


class ZipFileAcotado(zipfile.ZipFile):
    """Variante de solo lectura que conserva el descriptor verificado."""
    def __init__(self, origen, max_entradas=1000, max_directorio=MAX_DIRECTORIO):
        self.fp = None
        self._origen_propio = None
        propio = isinstance(origen, (str, bytes, os.PathLike))
        f = open(origen, 'rb') if propio else origen
        try:
            verificar_directorio_zip(f, max_entradas, max_directorio)
            if propio:self._origen_propio = f
            super().__init__(f, 'r')
        except BaseException:
            if propio:f.close()
            raise

    def close(self):
        try:super().close()
        finally:
            if self._origen_propio is not None:
                self._origen_propio.close();self._origen_propio = None


@contextmanager
def abrir_zip_acotado(origen, max_entradas=1000, max_directorio=MAX_DIRECTORIO):
    """Valida y abre el mismo descriptor; admite rutas y buffers seekables.

    El mismo descriptor evita sustituir la ruta entre preflight y ZipFile.
    Un buffer del llamador conserva su posición y no se cierra aquí.
    """
    propio = isinstance(origen, (str, bytes, os.PathLike))
    f = open(origen, 'rb') if propio else origen
    posicion = f.tell()
    try:
        verificar_directorio_zip(f, max_entradas, max_directorio)
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            yield z
    finally:
        if propio:
            f.close()
        else:
            f.seek(posicion)


def verificar_directorio_zip(f, max_entradas=1000, max_directorio=MAX_DIRECTORIO):
    if type(max_entradas) is not int or not 1 <= max_entradas <= 1000:
        raise ValueError('Límite de entradas ZIP inválido.')
    if type(max_directorio) is not int or not 46 <= max_directorio <= MAX_DIRECTORIO:
        raise ValueError('Límite del directorio ZIP inválido.')
    posicion = f.tell()
    try:
        f.seek(0, 2); tam = f.tell()
        if tam < 22:
            raise ValueError('ZIP sin directorio final válido.')
        inicio = max(0, tam - 65557)
        f.seek(inicio); cola = f.read(min(tam, 65557))
        # Una firma dentro del comentario no se confunde con el EOCD verdadero.
        pos = len(cola)
        while True:
            pos = cola.rfind(b'PK\x05\x06', 0, pos)
            if pos < 0:
                raise ValueError('ZIP sin directorio final válido.')
            if pos + 22 <= len(cola):
                campos = struct.unpack_from('<4s4H2IH', cola, pos)
                if pos + 22 + campos[-1] == len(cola):
                    break
        _, disco, disco_cd, entradas_disco, entradas, bytes_cd, offset, _ = campos
        if disco or disco_cd or entradas_disco != entradas:
            raise ValueError('ZIP multidisco no soportado; divide el archivo.')
        if entradas == 65535 or bytes_cd == 0xffffffff or offset == 0xffffffff:
            raise ValueError('ZIP64 no soportado dentro de los límites autorizados.')
        if entradas > max_entradas:
            raise ValueError('ZIP con demasiadas entradas; reduce la tanda.')
        if bytes_cd > max_directorio:
            raise ValueError('Directorio ZIP demasiado grande; reduce sus metadatos.')
        fin_cd = inicio + pos
        inicio_cd = fin_cd - bytes_cd
        # ZipFile permite prefijos autoextraíbles. No se ejecutan; la posición
        # efectiva del directorio debe ser válida incluso si existe ese prefijo.
        if inicio_cd < 0 or offset > inicio_cd or (entradas and bytes_cd < 46):
            raise ValueError('Directorio ZIP inconsistente.')
        if fin_cd >= 20:
            f.seek(fin_cd - 20)
            if f.read(4) == b'PK\x06\x07':
                raise ValueError('ZIP64 no soportado dentro de los límites autorizados.')
        actual = inicio_cd; cuenta = 0
        while actual < fin_cd:
            if cuenta >= max_entradas:
                raise ValueError('ZIP con demasiadas entradas reales; reduce la tanda.')
            f.seek(actual); cabecera = f.read(46)
            if len(cabecera) != 46 or cabecera[:4] != b'PK\x01\x02':
                raise ValueError('Directorio ZIP dañado o inconsistente.')
            nombre, extra, comentario = struct.unpack_from('<3H', cabecera, 28)
            if struct.unpack_from('<H', cabecera, 34)[0]:
                raise ValueError('ZIP multidisco no soportado.')
            actual += 46 + nombre + extra + comentario; cuenta += 1
            if actual > fin_cd:
                raise ValueError('Entrada del directorio ZIP fuera de límites.')
        if cuenta != entradas:
            raise ValueError('Cuenta de entradas del directorio ZIP inconsistente.')
        return {'entradas': cuenta, 'bytes_directorio': bytes_cd}
    finally:
        f.seek(posicion)
