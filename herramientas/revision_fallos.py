"""Lectura acotada de conversaciones: propuestas de casos, sin cambios."""
import re
import json
from collections import defaultdict
from conversaciones_jarvis import _redactar
from entorno_jarvis import DATOS

VISTAS=DATOS/'novedades_vistas.json'

def analizar(filas):
    grupos=defaultdict(list)
    for m in filas:
        if m.get('proyecto')!='CHAT JARVIS':continue
        texto=m.get('contenido','')
        if not re.search(r'(?i)inconclus|parcial|incompleta|no pude|sin respuesta|se corto|no reconozco|no entendi',texto):continue
        causa=('recursos' if re.search(r'(?i)vram|memoria|gpu|recursos',texto) else 'conexion o plazo' if re.search(r'(?i)ollama|timeout|conexion|solicitud',texto) else 'interpretacion o cobertura')
        pedido=re.search(r'(?:^|\n)Usuario:\s*\n([\s\S]*?)(?=\n(?:Respuesta|Estado:|Origen automático:)|$)',texto)
        muestra=_redactar(pedido[1].strip()) if pedido else ''
        grupos[causa].append({'id':m['id'],'caso':muestra[:240]})
    return dict(grupos)

def revisar(cliente):
    filas=[]
    for offset in range(0,1000,100):
        r=cliente.llamar('listar_memorias',{'proyecto':'CHAT JARVIS','desplazamiento':offset,'limite':100})
        pag=r.get('memorias',r.get('result',[]))
        if not pag:break
        filas.extend(pag)
        if len(pag)<100:break
    grupos=analizar(filas)
    texto='Revisión de hasta 1000 conversaciones de CHAT JARVIS. Solo lectura; no modifica código ni recuerdos.\n'
    if not grupos:return texto+'No se encontraron conversaciones parciales o fallidas en lo leído. Esto no acredita calidad universal.'
    for causa,casos in grupos.items():
        texto+=f'\n{causa}: {len(casos)} casos.\n'
        for x in casos[:3]:texto+='• ID '+str(x['id'])+': '+x['caso']+'\n'
        texto+='Prueba propuesta: reproducir la pregunta con datos ficticios, conservar la respuesta original y verificar que cubra cada parte sin ejecutar acciones.\n'
    return texto

def novedades(cliente,estado,confirmar=None):
    from entorno_jarvis import PROYECTO
    from datetime import datetime,timezone
    anterior=estado.get('_novedades_vistas')
    if not anterior and not VISTAS.is_symlink() and not any(p.is_symlink() for p in VISTAS.parents):
        try:
            if VISTAS.stat().st_size<4096:anterior=json.loads(VISTAS.read_text()).get('fecha')
            if anterior:datetime.fromisoformat(anterior)
        except (OSError,ValueError,TypeError,AttributeError):anterior=None
    lineas=['Novedades desde '+(anterior or 'la primera consulta registrada')+':']
    p=PROYECTO/'trabajo/JARVIS_CAMBIOS_RECIENTES.md'
    if p.is_file() and not p.is_symlink():
        try:ya_visto=bool(anterior and p.stat().st_mtime<=datetime.fromisoformat(anterior).timestamp())
        except (ValueError,TypeError):ya_visto=False
        if ya_visto:lineas.append('No hay un reporte local posterior a esa consulta.')
        else:lineas.extend(l for l in p.read_text().splitlines() if re.match(r'^\d+\.',l))
    try:
        r=cliente.llamar('buscar_memoria',{'proyecto':'Jarvis','consulta':'JARVIS — Estado actual (resumen para IA)'})
        filas=r.get('memorias',r.get('result',[]))
        lineas.append('Segundo Cerebro: '+('resumen consultado; verificar su fecha' if filas else 'sin resumen recuperado'))
    except (OSError,ValueError,ConnectionError):lineas.append('Segundo Cerebro: lectura no disponible; estas novedades proceden del reporte local.')
    fecha=datetime.now(timezone.utc).isoformat()
    estado['_novedades_vistas']=fecha
    nota='Última consulta recordada solo durante esta conversación.'
    if confirmar and confirmar('Guardar la fecha de esta consulta de novedades para recordarla al volver a abrir Jarvis?'):
        from conversaciones_jarvis import _atomic
        _atomic(VISTAS,{'fecha':fecha});nota='Fecha guardada para la próxima apertura.'
    return '\n'.join(lineas[:-1][:7]+[lineas[-1],nota])
