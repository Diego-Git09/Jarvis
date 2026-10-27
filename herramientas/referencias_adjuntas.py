"""Consulta extractiva por posición del manifiesto, sin ejecutar sus contenidos."""
import re
from normalizacion_entrada import vista


def atender(pedido, estado):
    if not estado.get('_tanda_documentos') or pedido.lstrip().startswith('/'):
        return None
    n = vista(pedido).strip(' ¿?¡!.')
    from referencias_fuentes import explicita
    if not explicita(pedido,estado):return None
    if re.search(r'\b(?:opcion|alternativa|paso|punto|segundo cerebro|borra|elimina|mueve|modifica|guarda|escribe|ejecuta)\b', n):
        return None
    if not re.search(r'\b(?:resume|resumeme|resumen|habla|trata|dice|contenido|muestrame|muestra)\b', n):
        return None
    ordinales = {0: r'primer[oa]?', 1: r'segund[oa]', 2: r'tercer[oa]?'}
    posiciones = [i for i, patron in ordinales.items() if re.search(r'\b'+patron+r'\b', n)]
    ambos = bool(re.search(r'\b(?:los dos|ambos)\b', n))
    if not posiciones and not ambos:
        return None
    import tandas_documentales as T
    try:
        manifiesto = T.cargar(estado['_tanda_documentos'])
        archivos = manifiesto['archivos']
        if ambos:
            posiciones = [0, 1]
        if any(i >= len(archivos) for i in posiciones):
            nombres = ', '.join(a['nombre'] for a in archivos[:5]) or 'ninguno'
            return 'Esa posición no existe en el último lote. Disponibles: '+nombres+'. ¿Qué archivo quieres consultar?'
        lineas = ['Orden del último manifiesto; extractos textuales comprobados, no lectura completa de cada archivo:']
        for i in posiciones:
            archivo = archivos[i]
            encabezado = str(i+1)+'. '+archivo['nombre']
            if not all(k in archivo for k in ('ruta', 'clave', 'firma', 'hash')):
                lineas.append(encabezado+'\nNo pude comprobar su índice. Usa /indexar antes de consultar el contenido.')
                continue
            seleccionado = dict(manifiesto, archivos=[archivo])
            lineas.append(encabezado+'\n'+T.resumen_extractivo(seleccionado))
        estado['_fuentes_tema_activo'] = True
        estado['_fuentes_turno'] = True
        return '\n\n'.join(lineas)
    except (OSError, ValueError, KeyError, TypeError):
        return 'No pude comprobar el último manifiesto. Usa /adjuntos para revisar los nombres y /indexar para reanudar la lectura.'
