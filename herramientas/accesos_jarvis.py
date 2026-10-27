"""Catálogo compartido para completar accesos y sugerir errores sin ejecutarlos."""
import difflib
import re
from lenguaje_jarvis import normalizar

ACCESOS=('/recordatorios','/recordar','/editar_recordatorio','/posponer_recordatorio','/eliminar_recordatorio','/completar_recordatorio','/escritorio','/carpetas','/autorizar_carpeta','/revocar_carpeta','/clima','/ias','/internet','/web','/preguntar_ia','/ia_externa','/ayuda','/proyectos','/estructura','/mejoras','/entrenamiento','/recuerdos','/sin_clasificar','/mas','/anterior','/actualizar','/pagina','/ver',
         '/buscar','/similares','/ultimo_recuerdo','/ultima_conversacion','/tamano','/ultima_accion','/proyecto','/todos','/estado','/sincronizar','/archivos','/leer',
         '/codigo','/mas_documento','/buscar_archivos','/reemplazar','/carpeta','/copiar','/mover','/cambios','/deshacer','/propuestas',
         '/aplicar','/cancelar','/info','/comparar','/encontrar','/diagnostico','/rendimiento','/contexto','/config','/modelos','/modelo','/modo',
         '/escalar','/deshacer_plan','/mensaje_completo','/timeout','/reposo','/liberar','/gpu','/perfil','/ollama_url','/tramos','/tramo','/mas_mensaje','/adjuntar','/indexar','/adjuntos','/resumir','/rango_excel','/estado_ia','/vocabulario','/limpieza','/tareas','/pendientes','/anotar','/hecho','/reabrir','/buscar_tareas','/editar_tarea',
         '/prioridad','/exportar_tareas','/sesiones','/guardar','/continuar','/exportar_sesion','/calcular','/hora','/pegar','/nuevo','/salir')
ALIASES={'/help':'/ayuda','/configuracion':'/config','/renombrar':'/mover','/duplicar':'/copiar',
         '/listar_archivos':'/archivos','/historial':'/cambios','/revertir':'/deshacer','/atras':'/anterior',
         '/siguiente':'/mas','/guardar_sesion':'/guardar','/retomar':'/continuar','/completar':'/hecho',
         '/sync':'/sincronizar','/sincronizacion':'/sincronizar'}
ACCESOS+=('/aprender_palabra','/estilo','/revisar_fallos','/novedades','/guia','/externo')
ACCESOS+=('/revisar_respuestas','/confirmar_vocabulario','/temperatura','/respaldo','/ollama')


def normalizar_acceso(pregunta):
    # Una ruta Unix no es un comando: conservar mayúsculas, tildes y espacios.
    if pregunta.strip().startswith('~/') or re.match(r'^/[^/\s]+/',pregunta.strip()):return pregunta
    partes=re.match(r'^(\S+)(.*)$',pregunta.strip(),re.S)
    if not partes or not partes[1].startswith('/'):return pregunta
    acceso=normalizar(partes[1])
    return ALIASES.get(acceso,acceso)+partes[2]


def sugerir(pregunta):
    acceso=normalizar(pregunta.strip().split()[0])
    candidatos=difflib.get_close_matches(acceso,ACCESOS,n=3,cutoff=0.72)
    if not candidatos:candidatos=difflib.get_close_matches(acceso,ACCESOS,n=3,cutoff=0)
    return 'No reconozco ese acceso. Puedes consultar '+', '.join(candidatos)+'. /ayuda explica los accesos. No ejecuté ninguna acción.'
