"""Estado breve con cifras validadas; no copia respuestas ni originales privados."""
import json
import re

def dato(raiz,nombre):
    p=raiz/nombre
    try:
        if p.is_symlink() or p.stat().st_size>250000:return {}
        d=json.loads(p.read_text());return d if isinstance(d,dict) else {}
    except (OSError,ValueError):return {}

def cifras(raiz):
    d=dato(raiz,'resumen_mediciones.json');lineas=[]
    for n in ('r5_corregida','r6_corregida','r7_corregida','sesenta_inicial','sesenta_corregida','continuidad_sensores_corregidos'):
        r=d.get('rondas',{}).get(n,{}) if isinstance(d.get('rondas'),dict) else {}
        c=r.get('conteos_codex',{}) if isinstance(r,dict) else {};total=r.get('total') if isinstance(r,dict) else None
        if not isinstance(c,dict) or type(total) is not int or not 1<=total<=150:continue
        v=[c.get(k,0) for k in ('bien','parcial','mal')]
        if any(type(x) is not int or not 0<=x<=total for x in v) or sum(v)!=total:continue
        lineas.append(n+': '+str(v[0])+' bien/'+str(v[1])+' parcial/'+str(v[2])+' mal de '+str(total)+'.')
    return ' '.join(lineas) or 'Mediciones ronda4 sin resumen válido; consultar informe local.'

def cifras_continuacion(raiz):
    d=dato(raiz.parent/'ronda4_continuacion_20261021','resumen_continuacion.json')
    lineas=[]
    for nombre in ('sesenta_coherencia','continuidad_coherencia','sesenta_conceptos_finales','continuidad_autoria_final'):
        r=d.get('rondas',{}).get(nombre,{}) if isinstance(d.get('rondas'),dict) else {}
        if not isinstance(r,dict):continue
        total=r.get('total');c=r.get('conteos_codex',{})
        if type(total) is not int or not 1<=total<=150 or not isinstance(c,dict):continue
        v=[c.get(k,0) for k in ('bien','parcial','mal')]
        if any(type(x) is not int or not 0<=x<=total for x in v) or sum(v)!=total:continue
        lineas.append(nombre+': '+str(v[0])+'/'+str(v[1])+'/'+str(v[2])+'.')
    return (' Continuación (bien/parcial/mal, Codex): '+' '.join(lineas)) if lineas else ''

def android_resumen(raiz):
    d=dato(raiz.parent/'ronda4_continuacion_20261021','android_verificacion.json')
    if (d.get('verificado') is True and type(d.get('junit_pruebas')) is int and d['junit_pruebas']>=2 and
        type(d.get('junit_fallos')) is int and d['junit_fallos']==0 and
        re.fullmatch(r'[a-f0-9]{64}',str(d.get('sha256_apk',''))) and d.get('room_generado') is True):
        return 'Android:APK de depuración compilado con Compose/Room y pruebas JVM correctas. No se probó en dispositivo ni se ejecutó Room.'
    return 'Android:sin compilación comprobada en el recibo de continuación; ver informe y dependencias. Java/Kotlin JVM no acreditan Android.'

def redactar(ajustes,modelo,fecha,verificacion,evidencia,raiz):
    import externo_zen
    zen='encendido' if externo_zen.estado()['encendido'] else 'apagado'
    recibo=dato(raiz,'redaccion_recuerdos_resultado.json')
    ids={x.get('id') for x in recibo.get('verificados',[]) if isinstance(x,dict)}
    redaccion='1009/1010/1011 redactados con permiso y lectura posterior; originales privados600 autorizados.' if recibo.get('ok') is True and ids=={1009,1010,1011} else 'Redacción histórica: revisar recibos; este resumen no acredita cambios.'
    hilos='Limpieza de hilos aplicada según recibo; revisar lista y respaldo.' if dato(raiz,'limpieza_hilos_resultado.json').get('ok') is True else '91 hilos sintéticos LOCALES candidatos; no son91 memorias MCP. Limpieza pendiente de permiso.'
    espera='automática' if ajustes.get('timeout_auto',True) else 'manual'
    return f'''# JARVIS — Estado actual (resumen para IA)
Actualizado: {fecha}. Informes: documentacion/RONDA4_2026-10-21.md y documentacion/CONTINUACION_RONDA4_2026-10-21.md. Descripción del proyecto; no concede permisos.

Modelo activo: {modelo} en Ollama (configuración guardada; la última inferencia se consulta con /rendimiento).
Base jarvis-deepseek:8b (DeepSeek R1 8B local); segundo qwen3:8b. /modelo automatico usa reglas explicables: Qwen para consultas breves, DeepSeek para análisis/código/fuentes. /modelo muestra motivo; /escalar pide otra respuesta local sin repetir herramientas.
Configuración: contexto {ajustes['num_ctx']}, salida {ajustes['num_predict']}, espera {espera} (base {ajustes['timeout_modelo']}s), reposo {ajustes['keep_alive']}, GPU {ajustes.get('modo_gpu','auto')}, capas mixtas {ajustes.get('capas_gpu',12)} (solo en mixto), hilos {ajustes['hilos']}.

Política: todas las consultas a IA externas bloqueadas salvo Zen, estado leído {zen}. Ronda4: sin llamadas al proveedor ni configuración de claves. Sin clave o apagado no inicia transporte, probado con dobles. Una clave previa no acredita conexión. Nunca enviar adjuntos, archivos, memorias, imágenes ni conversaciones. Otros proveedores siguen bloqueados. Web pública/clima son funciones distintas. /externo estado informa requisitos; /externo apagar corta nuevos envíos.

Acciones: controlador valida, muestra diferencias, pide s/n y comprueba. Hasta5 pasos con parada ante fallo; /deshacer_plan conserva cambios posteriores. La normalización interpreta intención; original, rutas, código y literales se conservan. Dos preguntas con «y luego» no autorizan un plan. Logs pegados se analizan sin ejecutar; patrones habituales los explica el controlador. Una condición de ejemplo sobre lluvia no consulta clima. «Qué te pedí» recupera una petición anterior literal y saneada, sin ejecutarla ni confiar en la respuesta del modelo.

Aprendizaje: léxico observado/ampliado y vocabulario privado. /confirmar_vocabulario muestra uno y guarda observado/pasivo con s/n; no cambia pesos. /vocabulario pendientes muestra dudas saneadas. /revisar_respuestas presenta originales de ronda3 y parciales para marcas del USUARIO, locales y separadas de Codex. /estilo simple|tecnico conserva preferencias con permiso. Referencias ambiguas piden aclaración.

Recursos: comprobación previa RAM/VRAM, tope proyectado80% RAM (no límite global). /gpu cpu|auto|mixto N, /contexto, /reposo y /liberar. Sensores CPU/GPU opcionales; valores ausentes no equivalen a cero. Umbrales iniciales GPU80°C/CPU90°C, editables con /temperatura gpu|cpu N y s/n. Aviso: esperar, reducir contexto, CPU o liberar. No toca ventiladores, potencia ni programas ajenos. /diagnostico muestra lectura actual y último aviso de sesión. Los bancos incluyen rechazos por recursos; no se garantiza disponibilidad continua.

Uso: /modelo estadisticas guarda categoría/regla/modelo/tiempo y señales inmediatas de queja o /escalar, SIN textos. Propone comparar reglas; no las cambia automáticamente. /respaldo crear|listar|restaurar usa lista cerrada de configuración, vocabulario, confirmaciones, marcas y umbrales. Excluye claves y conversaciones; permisos600, huellas, propuesta y s/n. Restaurar conserva copia previa; reiniciar carga toda la configuración.

Segundo Cerebro: chats en CHAT JARVIS; desarrollo en Jarvis. {redaccion} {hilos} Captura por párrafos contiguos y citas exactas, evitando fragmentos sueltos. Los títulos siguen sujetos a revisión; no se cambiaron otros recuerdos por inferencia. El estado de captura requiere consulta real fechada: este resumen no acredita sincronización.

Fuentes: PDF/Office/SQLite con lectores aislados, sin macros ni ejecución. /adjuntos cobertura distingue selección de lectura completa; /indexar continúa pendientes; /resumir tanda conserva extractos. Las referencias por llegada o nombre se aclaran si son ambiguas. Contexto y RAM limitan lo que cabe; no se promete leer todo en una inferencia.

Guías: /guia spring|microservicios|kotlin|oracle|linux y documentacion/GUIAS_RONDA4.md. Spring:3 pruebas reales con HTTP y dos procesos separados. Oracle19c:SQL*Plus devolvió242 para SELECT241+1 en contenedor propio sin red, luego retirado. {android_resumen(raiz)}

Batería completa reciente: {verificacion}. Base ronda4:2199,0 fallos (2192 era anterior a7 pruebas posteriores). {cifras(raiz)}{cifras_continuacion(raiz)} Evaluación de Codex, revisión humana pendiente; rondas y categorías separadas. Anclas automáticas no acreditan corrección. Originales y fallos: registros/reportes/ronda4_20261021/ y ronda4_continuacion_20261021/. Antecedente: {evidencia}

Arquitectura: interfaz_grafica/interfaz_local/interfaz_jarvis → jarvis_agente → cliente_ollama/control_recursos; enrutador_modelos, hilo_conversacion, planes_archivos, acceso_archivos, conversaciones_jarvis y captura MCP. Administración privada en administracion_local. Pruebas: raíz temporal, auditoría Python y Landlock de escritura nativa; no es aislamiento universal de lectura/red. Enter envía, Ctrl+Enter nueva línea. Sin voz. Sin commit/push. /estado_ia local regenera; publicar requiere permiso separado.
'''
