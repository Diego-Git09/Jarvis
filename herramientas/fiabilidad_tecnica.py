"""Contratos acotados contra los errores de API observados; no prueba universal."""
import re
from normalizacion_entrada import vista


def incumplimientos(pedido, respuesta):
    n=vista(pedido)
    codigo='\n'.join(re.findall(r'```[^\n]*\n([\s\S]*?)```',respuesta))
    sintaxis=codigo or respuesta
    fallos=[]
    if re.search(r'\b(?:room(?:database)?|kotlin)\b',n):
        if ('@DatabaseBuilder' in codigo or re.search(r'(?m)^\s*@DatabaseBuilder\b',sintaxis)):
            fallos.append('Room no tiene la anotación @DatabaseBuilder. Usa @Database y Room.databaseBuilder para construir la base.')
        if re.search(r':\s*RoomDatabase\s*\{',sintaxis):
            fallos.append('La herencia Kotlin de RoomDatabase requiere RoomDatabase().')
        if re.search(r'\.allowMainThreadQueries\s*\(',sintaxis):
            fallos.append('No habilites consultas de base en el hilo de interfaz. Usa DAO asíncrono y corrutinas.')
    if 'apex' in n and re.search(r'\bswddo\.sql\b',codigo or respuesta,re.I):
        fallos.append('Ese script no tiene evidencia en la guía verificada de APEX. No inventes el nombre: consulta el paquete y la documentación de la versión elegida.')
    if re.search(r'\bsql\s*\*?\s*plus\b',n) and re.search(r'\bsin\b.{0,70}\b(?:clave|contrasena|password)\b',n) and re.search(r'\bsqlplus\s+[^\s/]+/[^\s]+@',sintaxis,re.I):
        fallos.append('Se pidió no escribir la contraseña en el comando. Omítela y usa la solicitud oculta de SQL*Plus; no inventes usuario, host ni servicio.')
    return fallos


def guia_directa(pedido,historial=()):
    n=vista(pedido)
    if re.search(r'\b(?:crea|guarda|escribe|modifica|ejecuta|borra)\b',n):return None
    tema=None
    if 'spring' in n and re.search(r'\b(?:endpoint|api rest)\b',n) and re.search(r'\b(?:como|guia|pasos|tutorial)\b',n):tema='endpoint spring'
    if 'spring' in n and re.search(r'\b(?:java|jdk)\b',n) and re.search(r'\b(?:version|versiones|compatible|compatibilidad|requisito|requisitos)\b',n):tema='versiones spring'
    if re.search(r'\bviewmodel\b',n) and re.search(r'\b(?:android|compose|new project|plantilla)\b',n):tema='viewmodel'
    if re.search(r'\bapk\b',n) and re.search(r'\b(?:que (?:prueba|acredita|demuestra)|compilacion)\b',n):tema='compilacion apk'
    if re.search(r'\broom(?:database)?\b',n) and re.search(r'\b(?:como|pasos|guia|tutorial|parentesis|heredar|herencia)\b',n):tema='persistencia room'
    if re.search(r'\bsql\s*\*?\s*plus\b',n) and re.search(r'\bsin\b.{0,70}\b(?:clave|contrasena|password)\b',n):tema='conexion sqlplus'
    if 'apex' in n and re.search(r'\b(?:instalar|instalo|instalacion|configuro|configurar)\b',n):tema='apex'
    if 'docker' in n and re.search(r'\b(?:como uso|como usar|guia|tutorial)\b',n):tema='docker'
    if not tema and re.search(r'\bguia\b',n) and re.search(r'\b(?:usarlo|eso|lo anterior)\b',n):
        anteriores=[m.get('content','') for m in historial if m.get('role')=='user'][-4:]
        temas={t for p in anteriores for t in ('docker','spring','kotlin','room','oracle','apex','linux') if re.search(r'\b'+t+r'\b',vista(p))}
        if len(temas)==1:tema=temas.pop()
    if tema:
        from guias_contexto_r3 import guia
        return guia(tema)
    return None
