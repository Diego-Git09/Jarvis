"""Lectura HTTP con límite de bytes y plazo total para el cuerpo."""
import http.client
import socket
import time


class LimiteHTTP(ValueError):
    """El cuerpo superó el límite de bytes de su llamador."""


def _fragmentos(respuesta,limite,plazo):
    """No renueva el plazo al recibir fragmentos.

    read1 evita esperar a llenar un bloque con un servidor que gotea datos.
    El socket de HTTPResponse se acota al tiempo restante antes de cada bloque.
    Los adaptadores en memoria conservan el contrato read de las pruebas.
    """
    total=0
    lector=respuesta.read1 if callable(getattr(type(respuesta),'read1',None)) else respuesta.read
    while total<limite:
        restante=plazo-time.monotonic()
        if restante<=0:raise TimeoutError('Se agotó el plazo total de lectura HTTP.')
        if isinstance(respuesta,http.client.HTTPResponse):
            crudo=getattr(getattr(respuesta,'fp',None),'raw',None)
            conexion=getattr(crudo,'_sock',None)
            if isinstance(conexion,socket.socket):conexion.settimeout(restante)
        datos=lector(min(65536,limite-total))
        if not datos:break
        if not isinstance(datos,bytes):raise ValueError('Respuesta HTTP no binaria.')
        total+=len(datos)
        if time.monotonic()>plazo:raise TimeoutError('Se agotó el plazo total de lectura HTTP.')
        yield datos
    if time.monotonic()>plazo:raise TimeoutError('Se agotó el plazo total de lectura HTTP.')


def leer_acotado(respuesta,limite,plazo):
    return b''.join(_fragmentos(respuesta,limite,plazo))


def lineas_acotadas(respuesta,limite,plazo):
    """Líneas NDJSON sin esperar indefinidamente un salto ni perder fragmentos."""
    pendiente=bytearray();total=0
    for datos in _fragmentos(respuesta,limite+1,plazo):
        total+=len(datos)
        if total>limite:raise LimiteHTTP('El flujo superó el límite de bytes.')
        desde=len(pendiente);pendiente.extend(datos)
        while True:
            pos=pendiente.find(b'\n',desde)
            if pos<0:break
            yield bytes(pendiente[:pos+1]);del pendiente[:pos+1];desde=0
    if pendiente:yield bytes(pendiente)
