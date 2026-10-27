"""Vista jerárquica de proyectos y registros de Segundo Cerebro (solo lectura)."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re
from cerebro_mcp import ClienteCerebro, ErrorCerebro


def consultar(cliente: ClienteCerebro, proyecto: str = '') -> dict:
    proyectos = cliente.llamar('listar_proyectos', {}).get('proyectos', [])
    if not isinstance(proyectos, list):
        raise ErrorCerebro('Segundo Cerebro devolvió una lista de proyectos no válida.')
    seleccionados = [p for p in proyectos if not proyecto or p.get('proyecto', '').casefold() == proyecto.casefold()]
    if proyecto and not seleccionados:
        return {'ok': False, 'error': f'No existe el proyecto «{proyecto}».'}
    grupos = []
    for p in seleccionados:
        nombre = p.get('proyecto', '')
        datos = []; desplazamiento = 0; tamano = 50
        while True:
            pagina = cliente.llamar('listar_memorias', {
                'proyecto': nombre, 'orden': 'recientes',
                'desplazamiento': desplazamiento, 'limite': tamano}).get('memorias', [])
            if not isinstance(pagina, list):
                raise ErrorCerebro(f'La lista del proyecto «{nombre}» no es válida.')
            datos.extend(pagina)
            if len(pagina) < tamano:
                break
            desplazamiento += len(pagina)
        grupos.append({'proyecto': nombre,
                       'recuerdos': sum(r.get('tipo') != 'conversacion' for r in datos),
                       'conversaciones': int(p.get('conversaciones', 0)),
                       'registros': datos})
    return {'ok': True, 'consultado': datetime.now(ZoneInfo('America/Santiago')).isoformat(timespec='seconds'),
            'proyectos': grupos}


def obtener_registro_completo(cliente: ClienteCerebro, ident: int) -> dict:
    """Lee un registro por ID para mostrar el contenido entero, sin el recorte del listado."""
    if type(ident) is not int or ident < 1:
        raise ErrorCerebro('El registro seleccionado no tiene un ID válido.')
    resultado = cliente.llamar('consultar_memoria', {'id_memoria': ident})
    filas = resultado.get('memorias', []) if isinstance(resultado, dict) else []
    fila = next((r for r in filas if isinstance(r, dict) and r.get('id') == ident), None)
    if fila is None:
        raise ErrorCerebro('El registro ya no está disponible. Actualiza la biblioteca e inténtalo de nuevo.')
    if not isinstance(fila.get('contenido'), str):
        raise ErrorCerebro('Segundo Cerebro no devolvió el texto del registro.')
    return fila


def nombre_legible(fila):
    titulo=str(fila.get('titulo') or 'Sin título').replace('\n',' ').strip()
    if fila.get('tipo')!='conversacion':return titulo
    titulo=re.sub(r'\s*·\s*\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}(?::\d{2})?$', '', titulo)
    m=re.search(r'(?:^|\n)\s*(?:Usuario|Tú|Tu|You|user)\s*(?::|>)\s*([^\n]+)',str(fila.get('contenido','')),re.I)
    if m:
        muestra=' '.join(m[1].split())
        if muestra and muestra.casefold() not in titulo.casefold():titulo+=' — '+muestra[:72]+('…' if len(muestra)>72 else '')
    return titulo


def texto_visible(fila):
    """Conserva las palabras de la conversación y separa la procedencia del texto."""
    texto=str(fila.get('contenido',''))
    if fila.get('tipo')!='conversacion':return texto
    texto=re.sub(r'^Intercambio local de Jarvis\.\n\n','',texto)
    texto=re.sub(r'\n\nEstado: [^\n]+\n\nOrigen automático: (?:[^\n]+; intercambio local guardado al cerrar la respuesta\.|[^\n]+; evidencia de la conversación local, sin verificación externa\.)\s*$', '', texto)
    fuente={'jarvis':'Jarvis','codex':'Codex','claude_desktop':'Claude','continue':'Continue','openwebui':'Open WebUI'}.get(str(fila.get('fuente','')).casefold(),'Asistente')
    texto=re.sub(r'^Usuario:\n','Tú:\n',texto,count=1)
    texto=re.sub(r'\n\nRespuesta final(?: de Jarvis)?:\n','\n\n'+fuente+':\n',texto,count=1)
    return texto


def texto(datos: dict, max_items: int | None = None) -> str:
    if not datos.get('ok'):
        return datos.get('error', 'No pude consultar los proyectos.')
    lineas = ['Estructura de Segundo Cerebro', f"Consultado: {datos.get('consultado', 'ahora')}"]
    total = 0
    for grupo in datos.get('proyectos', []):
        registros = grupo.get('registros', [])
        lineas.append(f"\n▾ {grupo['proyecto']} ({grupo['recuerdos']} recuerdo(s), {grupo['conversaciones']} conversación(es))")
        lineas.append('  ▾ Recuerdos')
        recuerdos = [r for r in registros if r.get('tipo') != 'conversacion']
        conversaciones = [r for r in registros if r.get('tipo') == 'conversacion']
        for tipo, filas in [('recuerdo', recuerdos), ('conversación', conversaciones)]:
            if tipo == 'conversación':
                lineas.append('  ▾ Conversaciones')
            for r in filas:
                if max_items is not None and total >= max_items:
                    lineas.append(f'… vista limitada a {max_items} registros; usa /estructura NOMBRE para filtrar un proyecto.')
                    return '\n'.join(lineas)
                fecha = _fecha_local(r.get('creado', ''))
                titulo = nombre_legible(r)
                lineas.append(f"    • {titulo} · {fecha[:19].replace('T', ' ')}")
                total += 1
        if not recuerdos and not conversaciones:
            lineas.append('    (proyecto vacío)')
    if not datos.get('proyectos'):
        lineas.append('(sin proyectos)')
    return '\n'.join(lineas)


def _fecha_local(valor: str) -> str:
    if not valor:
        return 'fecha no disponible'
    try:
        fecha = datetime.fromisoformat(valor.replace('Z', '+00:00'))
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=ZoneInfo('UTC'))
        return fecha.astimezone(ZoneInfo('America/Santiago')).strftime('%d-%m-%Y %H:%M:%S (Chile)')
    except (ValueError, TypeError):
        return str(valor)
