"""Estado compacto de la revisión, únicamente con un cierre local comprobado."""
import json

def cierre(reportes):
    p=reportes/'revision_20261025/cierre.json'
    try:
        if p.is_symlink() or p.stat().st_size>64000:return None
        d=json.loads(p.read_text())
        if not isinstance(d,dict) or d.get('version')!=1 or d.get('validado') is not True:return None
        if any(type(d.get(k)) is not int for k in ('base_pruebas','pruebas','fallos')):return None
        if not 0<d['base_pruebas']<=d['pruebas']<=100000 or d['fallos']!=0:return None
        return d
    except (OSError,ValueError,RecursionError):return None

def redactar(ajustes,modelo,fecha,d):
    import externo_zen
    externo='encendido' if externo_zen.estado()['encendido'] else 'apagado'
    inicio='activado' if ajustes.get('autoinicio_ollama',True) else 'desactivado'
    return f"""# JARVIS — Estado actual (resumen para IA)
Actualizado: {fecha}. Proyecto Jarvis. Datos documentados, no permisos. Informe vigente: documentacion/REVISION_2026-10-25.md. Historia: RONDA6_2026-10-23.md y rondas anteriores. Consultar /diagnostico para el estado vivo.

Motor guardado: {modelo}, Ollama local. Selección {ajustes['seleccion_modelo']}; /modelo automatico elige Qwen3:8b para tareas sencillas y jarvis-deepseek:8b para razonamiento/código, reutilizando un residente suficiente. /modelo muestra motivo y /escalar evita repetir acciones. Contexto {ajustes['num_ctx']}, salida {ajustes['num_predict']}, GPU {ajustes.get('modo_gpu','auto')}, reposo {ajustes['keep_alive']}. No se cambió el coeficiente global de contexto: sigue2.5; calibración P90+10% informativa.

Revisión25/10: inicio automático de Ollama {inicio}, autorizado expresamente por el usuario. Si el servidor local no acepta conexiones, Jarvis inicia su propio ollama serve sin sudo ni systemctl. Un servidor que ya respondió se conserva al cerrar. Las sesiones de una misma instalación y dirección comparten supervisor y registros privados; solo al salir la última se detiene el proceso propio. Se comprueba la propiedad del puerto y no se señalan PIDs procedentes de los registros. Caídas de clientes, supervisor, arranques concurrentes, metadatos inválidos y cierre durante inicio tienen pruebas sintéticas. /ollama muestra conexión y gestión; /ollama reintentar recupera el inicio.

El hijo usa hogar privado, pesos instalados, escucha local, nube deshabilitada y sin poda de blobs. No instala ni descarga modelos. Conexión rechazada, timeout, HTTP de error, respuesta inválida y modelo ausente se distinguen; un servidor caído no provoca probar otro modelo del mismo servidor. La pregunta permanece recuperable. Los accesos directos de archivos/tareas/memoria siguen disponibles. El catálogo valida capacidades y nombres, omite remotos y duplicados. El cuerpo HTTP y NDJSON tienen plazo total y tamaño acotados; esto no acredita aislamiento universal ni un plazo absoluto para toda negociación de cabeceras.

Cierre e interfaz: confirmaciones pendientes terminan sin autorizar. Cancelar por cierre no inicia respaldos locales ni externos; se descartan resultados HTTP y líneas tardías. No se despachan turnos ni consultas iniciales que empiezan después. La ventana guarda la respuesta y la muestra antes de sincronizar; un fallo MCP no la vuelve fallida. La terminal también conserva la respuesta y continúa si falla la sincronización; no anuncia un guardado local sin confirmarlo. Sincronización gráfica al salir en segundo plano. Avisos visibles fuera del historial del modelo; estado en fila propia con ajuste, probado con Tk real y ventanas invisibles. Enter envía, Ctrl+Enter inserta línea. Imports/variables innecesarios retirados; funciones, pruebas y alias conservados. Resumen por archivo atómico/privado, rechazo de enlaces y aviso de configuración ilegible.

Privacidad: externo {externo}. Esta revisión no consultó Zen/OpenCode, no leyó ni configuró claves reales y no habilitó proveedores. El rechazo histórico403 FreeTierError sigue sin causa concreta adicional acreditada; OPENCODE_403_SOPORTE.md está preparado, no enviado. La excepción Zen conserva filtro de pregunta actual genérica, preferencias fuera de citas y bloqueo de archivos, adjuntos, memoria, historial y datos privados. Las pruebas externas fueron simuladas; no hay generación externa válida nueva.

Se mantienen las correcciones R6 de ordinales/referencias, propuestas del hilo prioritarias, fuentes pertinentes por turno y decisión común de textos largos. _fuentes_turno/_adjuntos_turno representan uso actual. La normalización no altera código, rutas o literales. Aprender vocabulario, escribir archivos/recuerdos y deshacer exigen permiso; el modelo propone y el controlador ejecuta/comprueba. Lectores aislados sin macros ni SQL del adjunto; rutas de credenciales/perfiles protegidas y hogar completo no autorizable.

Recursos: admisión RAM/VRAM, tope proyectado80% RAM y umbrales preventivos vigentes, sin rebajarlos ni tocar otros programas. Cachés por digest y sensores4s; invalidación al cambiar/cargar/descargar. Timeout/429/JSON no repiten transporte; conexión/5xx tienen un solo intento acotado. /reposo, /liberar y /gpu cpu|auto|mixto N conservados.

Verificación de esta revisión: base {d['base_pruebas']}/0; batería completa {d['pruebas']}/{d['fallos']} archivos con fallos, con datos temporales y producción bloqueada. Binario real en puerto temporal: inicio, puerto propio, mismo catálogo de seis modelos y cierre; servidor preexistente conservado. No se cargaron modelos ni se evaluó generación: CPU observada97–98°C, sobre el umbral preventivo90°C; límites conservados. Fallos, estabilidad prolongada, categorías y recibos en registros/reportes/revision_20261025/. No sumar bancos ni inferir calidad de IA desde pruebas de controlador.

Sin voz, entrenamiento de pesos, commit ni push. Históricos de calidad y guías Android/Room/APEX mantienen sus límites en informes anteriores. Refactorización grande y commit siguen como propuestas. Publicar o corregir recuerdos requiere permiso separado; un archivo local no acredita sincronización. Reabrir Jarvis para usar el código nuevo.
"""
