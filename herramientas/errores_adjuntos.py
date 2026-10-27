"""Mensajes de lectura sin volcar detalles internos ni contenidos del archivo."""
import gzip
import sqlite3
import tarfile
import zipfile
import zlib
from xml.etree.ElementTree import ParseError


def explicar(error,tipo=''):
    if isinstance(error,zipfile.BadZipFile):return 'El contenedor ZIP está dañado o incompleto; no pude leerlo.'
    if isinstance(error,tarfile.TarError):return 'El contenedor TAR está dañado o incompleto; no pude leerlo.'
    if isinstance(error,(gzip.BadGzipFile,zlib.error)):return 'El contenido comprimido está dañado o tiene una cabecera inválida.'
    if isinstance(error,EOFError):return 'El archivo está truncado o incompleto; se interrumpió la lectura.'
    if isinstance(error,ParseError):return 'El XML del documento está dañado o incompleto.'
    if isinstance(error,sqlite3.DatabaseError):
        codigo=getattr(error,'sqlite_errorcode',None)
        if type(codigo) is int and codigo&255 in {sqlite3.SQLITE_CORRUPT,sqlite3.SQLITE_NOTADB}:
            return 'La base SQLite está dañada o no tiene un formato legible; no pude obtener su esquema y muestra.'
    componente=(isinstance(error,KeyError) and error.args and isinstance(error.args[0],str)
        and error.args[0].startswith('There is no item named ') and error.args[0].endswith(' in the archive'))
    if componente and tipo in {'.xlsx','.xlsm','.docx','.pptx','.odt','.ods','.odp','.epub'}:
        return f'El documento {tipo.lstrip(".").upper()} está incompleto: falta un componente requerido.'
    from conversaciones_jarvis import _redactar
    return _redactar(str(error))[:1200] or 'El lector no pudo completar esta fuente.'
