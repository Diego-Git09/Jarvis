"""Lectura local de guías acotadas, sin ejecución."""
import re
from pathlib import Path

ARCHIVO=Path(__file__).resolve().parents[1]/'documentacion/GUIAS_RONDA5.md'
TEMAS={'spring':'Spring Boot','spring boot':'Spring Boot','microservicios':'Microservicios','kotlin':'Kotlin, Compose y Room','compose':'Kotlin, Compose y Room','room':'Kotlin, Compose y Room','roomdatabase':'Persistencia Room','oracle':'Oracle en Docker y SQL*Plus','docker':'Docker','apex':'APEX','persistencia room':'Persistencia Room','conexion sqlplus':'Conexión SQLPlus sin contraseña en argumentos','sqlplus':'Oracle en Docker y SQL*Plus','linux':'Diagnóstico Linux de solo lectura','ubuntu':'Diagnóstico Linux de solo lectura'}
TEMAS.update({'versiones spring':'Versiones Java y Spring','viewmodel':'ViewModel Android','compilacion apk':'Qué acredita compilar un APK','endpoint spring':'Endpoint Spring de productos'})

def sistema_detectado():
    import platform
    try:d=platform.freedesktop_os_release()
    except (OSError,AttributeError):return 'El sistema operativo no tiene una lectura disponible; no supongas Windows ni macOS.'
    nombre=d.get('PRETTY_NAME',d.get('NAME','Linux'))[:120]
    return 'Sistema operativo detectado: '+nombre+'. Para este equipo usa instrucciones de ese sistema. Docker Desktop no es requisito para Docker Engine en Ubuntu.'

def guia(tema):
    from normalizacion_entrada import plegar
    clave=plegar(tema.strip());titulo=TEMAS.get(clave)
    if not titulo:return 'Elige una guía: spring, microservicios, kotlin, oracle o linux.'
    if ARCHIVO.is_symlink() or ARCHIVO.stat().st_size>40000:return 'No pude leer la guía local.'
    texto=ARCHIVO.read_text();m=re.search(r'^## '+re.escape(titulo)+r'\n([\s\S]*?)(?=^## |\Z)',texto,re.M)
    return titulo+'\n'+m[1].strip() if m else 'No encontré esa sección.'

def contexto(pedido):
    from normalizacion_entrada import plegar
    n=plegar(pedido)
    if re.search(r'\b(?:crea|escribe|genera) (?:una )?funcion\b',n) and not re.search(r'\b(?:android|room|compose|spring|oracle|microservicios|guia|proyecto)\b',n):return ''
    # El tema técnico basta: «tutorial» y «cómo construyo» también requieren
    # la evidencia local, aunque no coincidan con una plantilla de petición.
    orden=['persistencia room','room','apex']+[x for x in sorted(TEMAS,key=len,reverse=True) if x not in {'persistencia room','room','apex'}]
    for clave in orden:
        if re.search(r'\b'+re.escape(clave)+r'\b',n):return 'Base documental local verificada para esta explicación. Conserva sus límites de ejecución. Lo no cubierto es general, sin verificar; confirma nombres y comandos en la documentación oficial. No inventes APIs, scripts ni rutas.\n'+guia('persistencia room' if clave=='room' else clave)[:2600]
    return ''
