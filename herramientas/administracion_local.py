"""Controles personales: no van al modelo, hilo explicativo ni captura MCP."""
import re

def es_entrada(p,estado):
    n=p.strip().casefold()
    if re.match(r'^/(?:revisar_respuestas|confirmar_vocabulario|temperatura|respaldo)(?:\s|$)',n) or n=='/modelo estadisticas':return True
    if estado.get('_confirmacion_vocabulario') and n in {'si','sí','s','no','n','a veces'}:return True
    return bool(estado.get('_revision_respuestas') and (re.fullmatch(r'(bien|parcial|mal)(?:\s*[:;,]?\s+.+)?',n,re.S) or n in {'siguiente','anterior'}))

def comando(p,estado,confirmar):
    import revision_humana
    import confirmar_vocabulario
    try:
        if p.strip().casefold()=='/modelo estadisticas' or re.match(r'^/(?:respaldo|temperatura)(?:\s|$)',p.strip(),re.I):
            estado.pop('_revision_respuestas',None);estado.pop('_confirmacion_vocabulario',None)
        if p.strip().casefold()=='/modelo estadisticas':
            import metricas_modelos
            return True,metricas_modelos.presentar()
        import respaldos_configuracion
        hecho,t=respaldos_configuracion.comando(p,confirmar)
        if hecho:return True,t
        import politica_termica
        hecho,t=politica_termica.comando(p,confirmar)
        if hecho:return True,t
        if p.strip().casefold().startswith('/revisar_respuestas'):estado.pop('_confirmacion_vocabulario',None)
        hecho,t=confirmar_vocabulario.comando(p,estado,confirmar)
        return (hecho,t) if hecho else revision_humana.comando(p,estado,confirmar)
    except (OSError,ValueError,KeyError,TypeError):return True,'No pude abrir o guardar esa revisión. Conservé los archivos; revisa la fuente y vuelve a intentarlo.'
