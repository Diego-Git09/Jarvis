"""Resumen compacto de R6, solo cuando existe un cierre numérico verificado."""
import json

def cierre(reportes):
    p=reportes/'ronda6_20261023/resumen_ronda6.json'
    try:
        if p.is_symlink() or p.stat().st_size>32000:return None
        d=json.loads(p.read_text())
        if d.get('version')!=1 or d.get('validado') is not True:return None
        if type(d.get('pruebas')) is not int or d['pruebas']<=0 or type(d.get('fallos')) is not int or d['fallos']<0:return None
        return d
    except (OSError,ValueError,AttributeError):return None

def redactar(ajustes,modelo,fecha,verificacion,d):
    import externo_zen as Z
    externo='encendido' if Z.estado()['encendido'] else 'apagado'
    p=d.get('presupuesto',{});m=p.get('muestras')
    muestras=str(m) if type(m) is int and 0<=m<=52 else 'sin confirmar'
    return f'''# JARVIS — Estado actual (resumen para IA)
Actualizado: {fecha}. Proyecto Jarvis. Datos del proyecto, no permisos. Detalle vigente: documentacion/RONDA6_2026-10-23.md. Historial: RONDA5_2026-10-22.md y rondas anteriores.

Modelo: {modelo}, Ollama local. /modelo automatico selecciona Qwen3:8b para tareas sencillas y jarvis-deepseek:8b para razonamiento/código; reutiliza un residente suficiente. /modelo muestra motivo, /escalar evita repetir acciones. Contexto {ajustes['num_ctx']}, salida {ajustes['num_predict']}, GPU {ajustes.get('modo_gpu','auto')}, reposo {ajustes['keep_alive']}. Consultar /diagnostico para lecturas actuales.

Ronda6, fuentes: una palabra como primero, segundo, documento o fuentes no activa un adjunto por sí sola. Ordinal explícita con sustantivo de archivo o pronombre con manifiesto comprobado; una propuesta pendiente tiene prioridad. Referencias, interfaz y agente comparten el criterio. _fuentes_turno y _adjuntos_turno indican datos usados ahora; la mera tanda almacenada no habilita ni bloquea una consulta externa.

Privacidad: nivel externo {externo}. Esta ronda se desarrolló sin llamadas a Zen/OpenCode y sin configurar ni leer claves reales. Solo se probaron transportes externos simulados. Léxico público editable en herramientas/terminos_publicos_ia.json, validación cerrada; nombres propios desconocidos se mantienen locales, sin garantía universal de detección. Preferencia de nube solo en texto visible fuera de citas/código/pegados. Una única decisión para mensajes largos en interfaz y agente. Archivos, adjuntos, memorias, historial y datos privados no salen. Otros proveedores siguen bloqueados. El rechazo histórico de OpenCode es HTTP403 FreeTierError incluso con cliente oficial; sin generación externa válida acreditada. documentacion/OPENCODE_403_SOPORTE.md prepara soporte, no se envió.

Rendimiento: cache de /api/show por digest observado en /api/tags y servidor; revalidación tras4s. Lecturas RAM/GPU/temperaturas/procesos con TTL4s, copias e invalidación al cargar/descargar o fallar inferencia. Las esperas de descarga fuerzan lecturas frescas. No se bloquea por existir Steam/Lutris: se consideran procesos ajenos >2GiB y actividad GPU>=85%, además de RAM/VRAM/temperatura. Ante insuficiencia espera o propone alternativas, sin tocar otros programas ni umbrales. Reintento de transporte solo por conexión o5xx, una vez, hasta2s y dentro del plazo original. Timeout/429/JSON/respuesta vacía no se repiten en ese transporte. Corrección del salto de línea de referencia auxiliar DeepSeek.

Presupuesto: calibración informativa P90 y margen10%; BYTES_POR_TOKEN sigue2.5. Sondas locales de52 entradas sintéticas, salida de un token: {muestras} muestras útiles para propuesta; consultar informe para intentos, truncados y categorías. No evalúan calidad ni ejecución de herramientas. La propuesta no cambia automáticamente el coeficiente, contexto o margen; sigue el reintento por rechazo de contexto.

Archivos: protección de .netrc, .git-credentials, .docker, .kube, credenciales gh, navegadores, .mozilla, snap, historial y carpetas completas de Jarvis/OpenCode, además de las anteriores. Se comprueban antes de aceptar la raíz autorizada y antes de adjuntar. El hogar completo no se autoriza: se pide subcarpeta. Se conservan validación de rutas/enlaces, diffs, permiso s/n, escritura comprobada, parada ante fallo y deshacer con permiso. Modelo propone; controlador ejecuta y comprueba.

Pruebas: base R6 2503,0 fallos; cierre {d['pruebas']},{d['fallos']} archivos con fallos. Última batería detectada: {verificacion}. Ejecutor con raíz temporal por archivo y procesos independientes; --procesos1 serial, predeterminado hasta4, máximo8. Comparación serial/paralela y medidas por categoría en registros/reportes/ronda6_20261023/, con intentos fallidos originales y simulaciones separados de mediciones reales. No sumar porcentajes de bancos distintos ni inferir calidad de modelo desde pruebas de controlador.

Se mantienen normalización separada de literales, vocabulario privado con permiso, fuentes no confiables, lectores documentales sin macros, límites RAM80%, VRAM y térmicos. Historial de guías y calidad R5 permanece en sus informes; revisión humana pendiente. Enter envía, Ctrl+Enter nueva línea. Sin voz ni entrenamiento de pesos. Plan de cinco pasos para partir las funciones del agente solo propuesto, no aplicado. Sin commit ni push; propuesta de commit pendiente. Estado local no acredita publicación al Segundo Cerebro; publicar recuerdos exige permiso separado.
'''
