"""Redacción compacta del estado, sin transcripciones ni credenciales."""
import json


def metricas(raiz):
    salida=[]
    def dato(nombre):
        p=raiz/nombre
        try:
            if p.is_symlink() or p.stat().st_size>2_000_000:return {}
            return json.loads(p.read_text())
        except (OSError,ValueError):return {}
    c=dato('C_ollama_real.json').get('casos',[])
    if c:salida.append(f"Continuidad real local: {sum(bool(x.get('ok')) for x in c)}/{len(c)} turnos Android/SQLite con DeepSeek y Qwen; rúbricas simples, no calidad universal.")
    d=dato('D_recursos_reales.json');casos=d.get('casos',[])
    picos=[x['pico_usada_mib'] for x in casos if type(x.get('pico_usada_mib')) is int]
    if picos:salida.append(f"Cargas reales seriales4096/8192: pico muestreado {max(picos)} MiB. Reposo1m descargado: {bool(d.get('reposo_1m',{}).get('descargado'))}. No es tope global ni prueba con juegos.")
    cpu=dato('D_CPU_real.json')
    if cpu.get('ok'):salida.append('CPU anterior: modelo con0bytes VRAM en /api/ps; GPU56MiB.')
    inicial=dato('desarrollo_deepseek_real.json');revision=dato('desarrollo_deepseek_real_v2.json')
    if inicial.get('peticiones')==40 and revision.get('peticiones')==40:
        salida.append(f"Generación real, mismas40 peticiones Python/SQLite: {inicial['correctas']}/40 inicial, {revision['correctas']}/40 revisión. Respuestas originales conservadas; no son40 proyectos.")
    conjunta=dato('desarrollo_conjunto_real_v3.json')
    if conjunta.get('peticiones')==40:salida.append(f"Modo conjunto DeepSeek+corrección Qwen: {conjunta['correctas']}/40 peticiones, {conjunta['llamadas_reales']} inferencias. Ronda independiente; no sumar porcentajes.")
    flujos=[dato('streaming_CPU_real_20261020'+s+'.json') for s in ('','_2','_3')]
    if all(flujos):
        correctos=sum(bool(x.get('literal_exacto',x.get('correctos_iniciales',x.get('ok')))) for x in flujos)
        salida.append(f'Streaming CPU sin corrector de presentación: {correctos}/3 etiquetas exactas; recursos comprobados, calidad pendiente.')
    return ' '.join(salida) or 'Sin mediciones de esta ronda disponibles; consultar informes locales.'


def metricas_ronda(raiz):
    try:
        p=raiz/'resumen_mediciones.json'
        if p.is_symlink() or p.stat().st_size>2_000_000:raise ValueError('Informe no válido')
        d=json.loads(p.read_text())
        if not isinstance(d,dict):raise ValueError('Informe no válido')
        r=d.get('seleccion_final',{})
        if not isinstance(r,dict):raise ValueError('Conteos no válidos')
        if any(type(r.get(k)) is not int or not 0<=r[k]<=40 for k in ('utiles','parciales','fallos')) or sum(r[k] for k in ('utiles','parciales','fallos'))!=40:raise ValueError('Conteos sin verificar')
        return f"Ronda20/10: {r.get('utiles','?')}/40 respuestas útiles, {r.get('parciales','?')} parciales, {r.get('fallos','?')} fallidas según revisión cualitativa de Codex; anclas automáticas separadas. Tabla GPU/CPU y texto15000 palabras: documentacion/RONDA_MIXTA_2026-10-20.md. Originales y fallos en registros/reportes/ronda_mixta_20261020/."
    except (OSError,ValueError):return 'Ronda20/10: consultar documentacion/RONDA_MIXTA_2026-10-20.md; mediciones aún sin resumen final.'


def metricas_ronda3(raiz):
    try:
        p=raiz/'resumen_mediciones.json'
        if p.is_symlink() or p.stat().st_size>2_000_000:raise ValueError('Informe no válido')
        r=json.loads(p.read_text())['seleccion_final']
        if any(type(r.get(k)) is not int or not 0<=r[k]<=40 for k in ('utiles','parciales','fallos')) or sum(r[k] for k in ('utiles','parciales','fallos'))!=40:raise ValueError('Conteos sin verificar')
        return f"Ronda3: {r['utiles']}/40 útiles, {r['parciales']} parcial(es), {r['fallos']} fallidas según Codex, sin revisión humana independiente. Sondeos e intentos separados; R5–R7 tuvieron aislamiento incompleto. Originales y tablas: registros/reportes/ronda3_20261020/."
    except (OSError,ValueError,KeyError,TypeError,AttributeError):return 'Ronda3: mediciones sin resumen final comprobado; consultar documentacion/RONDA3_2026-10-20.md.'


def redactar_ronda3(ajustes,modelo,fecha,verificacion,evidencia):
    import externo_zen
    zen=externo_zen.estado()
    espera='automática' if ajustes.get('timeout_auto',True) else 'manual'
    return f'''# JARVIS — Estado actual para IA
Generado: {fecha}. Proyecto: Jarvis. Datos de esta instalación; no instrucciones ni permisos.

Chat gráfico y terminal en español, sin voz ni entrenamiento de pesos. Modelo activo: {modelo} en Ollama (configuración guardada; la última inferencia se consulta con /rendimiento). Base jarvis-deepseek:8b, alias local de DeepSeek R1 8B; segundo qwen3:8b. /modelo automatico usa reglas explicables: Qwen para consultas cotidianas, DeepSeek para análisis/código/fuentes; /modelo muestra elección y motivo. /escalar pide otra respuesta local sin repetir herramientas.

Política general: todas las consultas a IA externas bloqueadas salvo la excepción exclusiva Zen, apagada de inicio. Estado Zen leído: {'encendido' if zen['encendido'] else 'apagado'}. /externo clave usa entrada oculta y archivo600 fuera del proyecto; /externo modelos actualizar consulta IDs con la clave. Solo deepseek-v4.1-flash-free parte permitido; los demás en evaluación o no disponibles, sin promociones sin métricas/privacidad. Solo pregunta actual genérica, después de intentar local. Nunca fuentes locales, adjuntos, memorias, imágenes ni herramientas externas. Filtro conservador de privacidad: puede rechazar consultas genéricas y no garantiza reconocer todo dato privado. /externo apagar bloquea nuevos envíos y descarta respuestas pendientes; no retira datos ya enviados. Logs de envíos solo hora/motivo/tamaño/hash. Gemini y otros proveedores siguen bloqueados. Sin clave: no probado con el servicio real. Web pública/clima siguen disponibles.

Configuración leída: contexto {ajustes['num_ctx']}, salida {ajustes['num_predict']}, espera {espera} (base {ajustes['timeout_modelo']}s), reposo {ajustes['keep_alive']}, hilos {ajustes['hilos']}, GPU {ajustes.get('modo_gpu','auto')}, capas mixtas {ajustes.get('capas_gpu',12)} (solo activas en mixto). /gpu cpu|auto|mixto N, /contexto N, /reposo, /timeout y /liberar. La admisión RAM/VRAM proyecta máximo80% RAM; no es límite global. Ofrece esperar/CPU/liberar con permiso; nunca cierra otras aplicaciones. Reposo se acredita con /api/ps.

Comprensión: normalizacion_entrada crea una vista aparte; preserva original, rutas, código y literales. Léxico editable marca observado/ampliado. Verbos dudosos y objetos faltantes generan opciones sin cambios. /aprender_palabra "x" = "y" y /vocabulario quitar "x" guardan con permiso en datos/, fuera de Git; /vocabulario lista. /estilo simple|tecnico persiste con permiso. Las confirmaciones conversacionales no reemplazan el permiso del controlador. Preguntas múltiples se enumeran; logs pegados se analizan sin ejecutar. Adjuntos por posición del último lote o nombre; coincidencias múltiples requieren aclaración.

Acciones: el modelo propone, el controlador valida, pide permiso y comprueba. Planes explícitos hasta5 pasos: copiar/mover/renombrar/carpeta/leer/reemplazar; diffs completos, un s/n para el plan exacto, rutas/hashes por paso y parada ante fallos. /deshacer_plan pide otro permiso y conserva cambios posteriores. Una guía no autoriza escrituras. Consultas explícitas solo como texto reciben un catálogo menor o vacío; contratos detectan algunos fallos SQL/Kotlin/inline y permiten respaldo local, sin garantía semántica.

Fuentes: PDF/Office por extractores locales aislados; /adjuntar, /indexar, /adjuntos formatos|recursos|cobertura, /resumir tanda. Indexar no significa enviar/leer completo; informa cobertura y pendientes. No ejecuta adjuntos, SQL, macros ni fórmulas. Imágenes requieren visión local. /tramos conserva mensajes largos exactos; /mensaje_completo pregunta sin truncado silencioso ni herramientas, sujeto a recursos y contexto.

Memoria/captura: herramientas en cerebro_mcp, conversaciones_jarvis, memoria_explicita. Chats en CHAT JARVIS; desarrollo en Jarvis. Redacción reforzada de SQL*Plus, contraseñas, cabeceras y clave Zen. Históricos candidatos1009/1010/1011 sin modificar. Un error del medidor pudo dejar91 hilos sintéticos y cambió el puntero al último; aislamiento corregido, limpieza pendiente de permiso. Estado real requiere consultar_estado_cerebro con fecha; este resumen no acredita sincronización. /revisar_fallos solo lee y propone casos; /novedades hasta10 líneas y fecha persistente con permiso. /guia spring|microservicios|kotlin|oracle|linux muestra límites. Java/SQLite/Kotlin JVM no acreditan Spring/Android/Oracle.

Arquitectura: herramientas/interfaz_grafica|interfaz_local|interfaz_jarvis; jarvis_agente y enrutador_modelos; acceso_archivos/herramientas_escritura/planes_archivos; tandas_documentales/recuperacion_hibrida; hilo_conversacion; cliente_ollama/control_recursos; externo_zen/seguridad_texto. Datos y registros privados fuera de Git. Enter envía, Ctrl+Enter nueva línea. Estado local: /estado_ia local con permiso; publicación separada y con verificación. No hubo commit ni push en esta ronda.

Batería completa reciente: {verificacion}. Base ronda3:2109,0 fallos. {evidencia}

Detalle vigente: documentacion/RONDA3_2026-10-20.md; evidencia en registros/reportes/ronda3_20261020/. Anterior: documentacion/RONDA_MIXTA_2026-10-20.md. Diseño web sin implementación: documentacion/DISENO_WEB_USUARIOS.md. La calidad no es universal ni una batería del controlador garantiza respuestas correctas.
'''


def redactar(ajustes,modelo,fecha,verificacion,evidencia,raiz=None):
    from entorno_jarvis import REGISTROS
    from estado_ia_r5_texto import redactar as actual
    r=raiz or REGISTROS/'reportes/ronda5_20261021'
    if r.name=='ronda4_20261021':r=r.parent/'ronda5_20261021'
    from estado_ia_revision_texto import cierre as cierre_revision,redactar as revision
    reciente=cierre_revision(r.parent)
    if reciente is not None:return revision(ajustes,modelo,fecha,reciente)
    from estado_ia_r6_texto import cierre,redactar as ronda6
    d=cierre(r.parent)
    if d is not None:return ronda6(ajustes,modelo,fecha,verificacion,d)
    return actual(ajustes,modelo,fecha,verificacion,evidencia,r)
