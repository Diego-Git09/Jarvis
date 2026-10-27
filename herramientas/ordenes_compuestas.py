"""Separa un orden explícito fuera de citas; no inventa destinos ni permisos."""
import re
import shlex


def referencia_archivo(texto,anterior):
    """Pronombre solo para el destino del paso previo comprobado, sin inferir."""
    m=re.fullmatch(r'(?i)(ren[oó]mbralo|mu[eé]velo|c[oó]pialo)\s+(?:a|como|con el nombre)\s+(.+)',texto.strip())
    if not m:return texto
    if not anterior:raise ValueError('No hay un archivo comprobado en el paso anterior para ese pronombre. Indica origen y destino.')
    try:destino=shlex.split(m[2])
    except ValueError:raise ValueError('Revisa las comillas del destino.')
    if len(destino)!=1:raise ValueError('Indica un solo destino entre comillas si tiene espacios.')
    acceso='/copiar' if m[1].casefold() in {'copialo','cópialo'} else '/mover'
    return acceso+' '+shlex.quote(anterior)+' '+shlex.quote(destino[0])

def separar(texto):
    comilla=None;esc=False;cortes=[];mascara=list(texto)
    parejas={'"':'"',"'":"'",'`':'`','«':'»','“':'”','‘':'’'}
    for i,c in enumerate(texto):
        if esc:
            if comilla:mascara[i]=' '
            esc=False;continue
        if c=='\\':
            if comilla:mascara[i]=' '
            esc=True;continue
        if comilla is not None:
            mascara[i]=' '
            if c==comilla:comilla=None
        elif c in parejas:
            mascara[i]=' ';comilla=parejas[c]
        if comilla is None:
            m=re.match(r'(?i)\s+y\s+(?:luego|despu[eé]s)\s+',texto[i:])
            if m and (not cortes or i>=cortes[-1][1]):cortes.append((i,i+m.end()))
    if not cortes:return []
    visible=''.join(mascara)
    if re.search(r'(?i)\bsincroniz|^/sync\b',visible):return []  # La sincronización cambia listados; exige un turno separado.
    if len(cortes)>4:raise ValueError('Puedo seguir hasta cinco acciones explícitas; divide el plan.')
    partes=[];anterior=0
    for a,b in cortes:partes.append(texto[anterior:a].strip());anterior=b
    partes.append(texto[anterior:].strip())
    if any(not p for p in partes):return []
    if re.search(r'(?i)\b(?:no|nunca|ejemplo|hip[oó]tesis|expl[ií]came|explica)\b',visible):return []
    if not re.search(r'(?i)\b(?:copiar?|duplica(?:r)?|mover|mueve|renombrar?|crea(?:r)?|leer|lee|abre|abrir|reemplaza(?:r)?|traslada(?:r)?|muevelo|renombralo|copialo|anota(?:r)?|marca(?:r)?|completa(?:r)?|elimina(?:r)?|borra(?:r)?)\b',visible):return []
    return partes

def ejecutar(partes,accion):
    resultados=[]
    for i,p in enumerate(partes,1):
        try:dato=accion(p)
        except (OSError,ValueError):
            resultados.append(f'Paso {i}: no pude completar la acción. Revisa /ultima_accion y /cambios antes de repetir. No ejecuté los pasos posteriores.');break
        ok,respuesta=dato[:2];comprobado=dato[2] if len(dato)>2 else None
        if not ok:
            resultados.append(f'Paso {i} pendiente: «{p}». Necesito el objeto/destino exacto. Elige: 1) archivo, 2) recuerdo, 3) otra acción. No ejecuté los pasos posteriores.');break
        resultados.append(f'Paso {i}: {respuesta}')
        if comprobado is False or (comprobado is None and re.search(r'(?i)(no autoriz|sin permiso|no pude|fuera de alcance|no encontr[eé]|^uso:|^revisa las comillas|^primero |^elige |^no reconozco)',respuesta)):
            resultados.append('Me detuve en ese paso; los posteriores siguen pendientes.');break
    return '\n\n'.join(resultados)
