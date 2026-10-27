"""Referencias explícitas a fuentes: una ordinal discursiva no elige archivos."""
import re
from normalizacion_entrada import vista

ORDINAL=r'(?:primer[oa]?|segund[oa]|tercer[oa]?)'
SUSTANTIVO=r'(?:archivos?|adjuntos?|documentos?|fuentes?|pdfs?)'

def explicita(pedido,estado=None):
    n=vista(pedido)
    if '[adjunto:' in n:return True
    ordinal=bool(re.search(r'\b'+ORDINAL+r'\b|\b(?:ambos|ambas|los dos|las dos)\b',n))
    if ordinal and (estado or {}).get('_hilo_conversacion',{}).get('propuesta'):return False
    # Definiciones genéricas y posiciones de una explicación no son archivos.
    if re.search(r'\b(?:que (?:es|son|significa)|definicion de|se define)\s+(?:(?:un|una|el|la|los|las)\s+)?(?:documentos?|fuentes?|pdfs?|archivos?)\b',n):return False
    if re.search(r'\b'+ORDINAL+r'\s+(?:paso|opcion|alternativa|punto|tema|ejemplo)\b',n):return False
    if re.search(r'\b'+ORDINAL+r'\s+'+SUSTANTIVO+r'\b|\b'+SUSTANTIVO+r'\s+(?:(?:el|la)\s+)?'+ORDINAL+r'\b',n):return True
    if re.search(r'\b(?:adjuntos?|archivos? adjuntados?|documentos? adjuntos?|fuentes? adjuntas?|(?:esta|esa|la|mi) tanda|(?:mis|estos|esos|los) (?:documentos|archivos|pdfs))\b',n):return True
    # Un nombre de archivo explícito conserva su significado, sin abrirlo.
    if re.search(r'\b[\w.-]+\.(?:pdf|docx|xlsx|pptx|txt|md|csv)\b',n):return True
    corta=bool(re.search(r'\b(?:el|la|del)\s+'+ORDINAL+r'\b|\b(?:ambos|ambas|los dos|las dos)\b',n))
    ident=(estado or {}).get('_tanda_documentos')
    if not corta or not ident:return False
    try:
        import tandas_documentales as T
        m=T.cargar(ident)
        return m.get('id',ident)==ident and isinstance(m.get('archivos'),list) and bool(m['archivos'])
    except (OSError,ValueError,KeyError,TypeError):return False
