"""Entrada de una o varias líneas, sin ejecutar cada línea pegada por separado."""
MAX_PEGADO=200000


class TextoPegado(str):
    pass


def completar_rutas(texto,linea,inicio):
    """Completa nombres en trabajo y carpetas personales autorizadas."""
    import shlex
    import herramientas_lectura as L
    from accesos_jarvis import normalizar_acceso
    prefijo=normalizar_acceso(linea).split(maxsplit=1)[0] if linea.strip() else ''
    if prefijo not in {'/leer','/info','/archivos','/copiar','/mover','/comparar','/carpeta','/reemplazar','/exportar_tareas','/exportar_sesion'}:return []
    if inicio==0 or any(c in texto for c in '"\''):return []
    try:
        argumento=len(shlex.split(linea[:inicio]))
        permitidos={'/copiar':{1,2},'/mover':{1,2},'/comparar':{1,2},'/exportar_sesion':{2}}
        if argumento not in permitidos.get(prefijo,{1}):return []
        fragmento=L.Path(texto)
        carpeta=L._resolver(texto if texto.endswith('/') else fragmento.parent)
        if not carpeta.is_dir():return []
        resultado=[]
        for p in sorted(carpeta.iterdir()):
            if len(resultado)>=100:break
            if not p.name.startswith(fragmento.name if texto and not texto.endswith('/') else ''):continue
            if p.is_symlink():continue
            ruta=L.etiqueta_ruta(p)+('/' if p.is_dir() else '')
            resultado.append(shlex.quote(ruta))
        return resultado
    except (L.FueraDeAlcance,OSError,ValueError):return []


def leer_pregunta(entrada=input,mostrar=print):
    pregunta=entrada('\nTú> ').strip()
    if pregunta.casefold()!='/pegar':return pregunta
    mostrar('Pega el texto. Escribe /fin para enviarlo; /cancelar lo descarta. Máximo 200000 caracteres; los mensajes largos se leen por tramos.')
    lineas=[];cantidad=0;descartado=False
    while True:
        try:linea=entrada('… ')
        except (EOFError,KeyboardInterrupt):
            mostrar('Texto descartado; no se envió al modelo.');return ''
        if linea.strip().casefold()=='/cancelar':
            mostrar('Texto descartado; no se envió al modelo.');return ''
        if linea.strip().casefold()=='/fin':return '' if descartado else TextoPegado('\n'.join(lineas).strip())
        if descartado:continue
        cantidad+=len(linea)+1
        if cantidad>MAX_PEGADO:
            mostrar('El texto supera 200000 caracteres. Se descartó. Escribe /fin o /cancelar para volver; adjunta un archivo para indexarlo.')
            descartado=True;lineas=[];continue
        lineas.append(linea)
