"""Órdenes de preferencia solo fuera de citas, código y pegados identificables."""
import re

def visible(texto):
    texto=re.split(r'(?i)\[Adjunto:',texto,maxsplit=1)[0]
    texto=re.sub(r'```[\s\S]*?```|~~~[\s\S]*?~~~',' ',texto)
    texto=re.sub(r'`[^`\n]*`|«[^»]*»|“[^”]*”|"(?:\\.|[^"\\])*"|(?<!\w)\'(?:\\.|[^\'\\])*\'(?!\w)',' ',texto)
    limite=re.search(r'(?im)^\s*(?:>|\S+@\S+[:~$]|Traceback|NVIDIA-SMI|Usuario:|Respuesta(?: final)?:)|\b(?:cita|texto pegado|salida|log|ejemplo)\s*:',texto)
    return texto[:limite.start()] if limite else texto
