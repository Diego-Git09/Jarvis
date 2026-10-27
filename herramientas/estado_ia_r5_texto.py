"""Estado vigente breve: cifras validadas, sin transcripciones ni secretos."""
from estado_ia_r4_texto import dato,android_resumen

def cifras(raiz):
    d=dato(raiz,'resumen_mediciones.json');b=d.get('bancos',{})
    if not isinstance(b,dict):return 'Ronda5: mediciones sin resumen final; consulta el informe y los originales.'
    lineas=[]
    for nombre,total in (('simulado52',52),('real52_final',52),('tecnico20',20)):
        r=b.get(nombre,{})
        if not isinstance(r,dict) or r.get('casos')!=total:continue
        if nombre=='simulado52':
            n=r.get('correctos')
            if type(n) is int and 0<=n<=total:lineas.append(f'Simulación del controlador:{n}/{total} contratos; no evalúa calidad de un modelo.')
        else:
            c=r.get('revision_codex',{})
            if not isinstance(c,dict):continue
            valores=[c.get(k) for k in ('bien','parcial','mal')]
            if any(type(n) is not int or not 0<=n<=total for n in valores) or sum(valores)!=total:continue
            lineas.append(f"{nombre}: {valores[0]} bien/{valores[1]} parcial/{valores[2]} mal de{total}, revisión Codex; revisión del usuario pendiente.")
    return ' '.join(lineas) or 'Ronda5: mediciones sin resumen final válido; consulta originales.'

def redactar(ajustes,modelo,fecha,verificacion,evidencia,raiz):
    import externo_zen as Z
    r4=raiz.parent/'ronda4_20261021'
    recibo=dato(r4,'redaccion_recuerdos_resultado.json')
    ids={r.get('id') for r in recibo.get('verificados',[]) if isinstance(r,dict)}
    limpieza='Históricos1009/1010/1011 redactados con permiso y lectura posterior, originales600.' if recibo.get('ok') is True and ids=={1009,1010,1011} else 'Históricos: este resumen no acredita su limpieza; revisar recibos.'
    hilos='91 hilos sintéticos locales limpiados con permiso y respaldo.' if dato(r4,'limpieza_hilos_resultado.json').get('ok') is True else 'Limpieza de hilos: consultar recibos; no se acredita aquí.'
    espera='automática' if ajustes.get('timeout_auto',True) else 'manual'
    return f'''# JARVIS — Estado actual (resumen para IA)
Actualizado: {fecha}. Proyecto Jarvis. Datos del proyecto, sin permisos de ejecución. Detalle vigente: documentacion/RONDA5_2026-10-22.md. Historial: RONDA4_2026-10-21.md y CONTINUACION_RONDA4_2026-10-21.md en documentacion/.

Modelo activo: {modelo} en Ollama (configuración guardada; la última inferencia se consulta con /rendimiento).
Base jarvis-deepseek:8b (DeepSeek R1 8B), segundo qwen3:8b. /modelo automatico usa reglas explicables; reutiliza un modelo residente si alcanza y evita recargas innecesarias. Análisis/código/fuentes pertinentes usan razonamiento; /modelo indica motivo; /escalar no repite acciones.
Configuración: contexto {ajustes['num_ctx']}, salida {ajustes['num_predict']}, espera {espera} (base {ajustes['timeout_modelo']}s), reposo {ajustes['keep_alive']}, GPU {ajustes.get('modo_gpu','auto')}, capas mixtas {ajustes.get('capas_gpu',12)} (solo en mixto), hilos {ajustes['hilos']}.

Privacidad: todas las consultas a IA externas bloqueadas salvo la excepción Zen, estado leído {'encendido' if Z.estado()['encendido'] else 'apagado'}. Ronda5 no usó el servicio ni configuró claves. Una credencial detectada no acredita autenticidad, conexión ni quién la guardó. Auditoría local solo de metadatos, sin mostrarla ni cambiarla. Nunca enviar fuentes locales, adjuntos, memorias, imágenes ni conversaciones. Otros proveedores bloqueados; web pública/clima son distintos. No hubo voz ni entrenamiento de pesos.

Controlador: el modelo propone, se validan rutas/esquemas, se muestra diff, se pide s/n y se comprueba el resultado. Planes hasta5 pasos con parada y deshacer por nombre; no sobrescribe destinos. Las lecturas encadenadas reconocidas no requieren permiso. «Borra eso» sin objeto pide archivo o recuerdo. Shell pegado ofrece accesos equivalentes; no ejecuta una terminal. Errores comunes de esquema, archivo y red se traducen. No garantiza interpretar toda expresión posible.

Fuentes: un índice antiguo no vuelve pertinente un adjunto. Las preguntas nuevas reciben contexto aislado de las fuentes anteriores; el historial y el índice se conservan. Referencias por orden del manifiesto nombran el archivo; faltantes se aclaran. Resumen/análisis de adjuntos bloquea escrituras incluso si el modelo las propone. PDF/Office/SQLite usan lectores aislados, sin macros. /adjuntos cobertura distingue selección y lectura completa; /indexar continúa pendientes.
Pegados largos: todos los tramos exactos se resumen y luego se sintetizan dentro de tiempo/contexto acotados. Cobertura, fallos y pendientes visibles; pausas térmicas acotadas y sin rebajar umbrales. No convierte texto fuente en órdenes ni declara completo un resumen parcial.

Comprensión: vista normalizada separada del original; conserva código, rutas y literales para las acciones. Diez variantes por familias de fallos, referencias sin inventar opciones, última petición con contenido sin devolver «listo». «Peos» se entiende como malos; «fome» ampliado sigue dudoso hasta /confirmar_vocabulario. Aprendizaje privado con s/n; nunca promoción silenciosa. /estilo simple|tecnico persiste con permiso. Prosa final sin prefijos ni frases internas detectadas; filtro acotado, no garantía universal.

Recursos: admisión previa RAM/VRAM, tope proyectado80% RAM; no limita todo el sistema. Ante insuficiencia atribuible solo a modelos propios puede descargar el otro y comprobar /api/ps antes de cargar. Sensores ausentes o procesos/modelos ajenos impiden asumir memoria libre. No cierra programas ni cambia potencia/ventiladores. Umbrales preventivos iniciales GPU80°C/CPU90°C, editables con s/n. Opciones esperar, reducir contexto, CPU o liberar. /gpu cpu|auto|mixto N, /reposo, /liberar y /diagnostico. Calibración informativa por modelo tras5 muestras; conserva estimación conservadora para admisión. Reglas compactas propuestas, sin sustituir la base normal por un resultado simulado.

Guías: documentacion/GUIAS_RONDA5.md; /guia spring|microservicios|kotlin|oracle|linux y temas room/apex/docker. API o script fuera de evidencia se declara general y sin verificar. Fórmula de pesos/contexto con lecturas actuales de Ollama para memoria de8B. Sistema detectado, instrucciones Ubuntu en este equipo. Spring/Oracle se acreditan por recibos históricos, no por repetir una explicación. {android_resumen(r4)} Fragmento nuevo Room y APEX no ejecutados en ronda5.

Memoria: chats CHAT JARVIS, desarrollo Jarvis. Estado real se consulta con fecha, no desde este resumen. Guardado explícito corto: texto literal, proyecto sin_clasificar salvo indicación, preview/s/n, ID y lectura posterior. Secretos detectados no se guardan tal cual. {limpieza} {hilos} Los bancos de ronda5 no modificaron recuerdos reales. Este archivo local no acredita publicación ni sincronización.

Revisión y respaldo: /revisar_respuestas separa tus marcas de Codex; /respaldo excluye claves y restaura con permiso/huellas. /modelo estadisticas no guarda textos; /revisar_fallos solo lee.

Batería completa reciente: {verificacion}. Base ronda5:2318 pruebas,0 fallos con acceso local a ventanas/sockets. {cifras(raiz)} Bancos separados, sin sumar porcentajes; fallos e intentos conservados en registros/reportes/ronda5_20261021/. Las pruebas del controlador no acreditan corrección técnica universal.

Arquitectura: interfaces → jarvis_agente → cliente_ollama/control_recursos, con módulos separados para fuentes, referencias, planes y MCP. Pruebas temporales con auditoría Python y Landlock de escritura; no aislamiento universal de lectura/red. Enter envía, Ctrl+Enter nueva línea. /estado_ia local regenera; publicar exige permiso separado. Sin commit ni push.
'''
