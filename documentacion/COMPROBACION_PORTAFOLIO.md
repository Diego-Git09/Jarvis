# Comprobación de la copia de Jarvis

Fecha: 27 de octubre de 2026.

## Resultado

- 169 archivos de pruebas revisados mediante ejecución.
- 2762 casos contados: 2761 aprobados y 1 omitido por integración externa no configurada.
- Las 34 pruebas gráficas inicialmente omitidas se ejecutaron después con Tk real y pasaron.
- Resultado combinado de una pasada completa y repeticiones de los archivos afectados. No se suman las repeticiones como pruebas nuevas.
- 377 archivos Python sin errores de sintaxis; recursos JSON legibles.
- 21 archivos del componente TkinterDnD coinciden con las huellas del manifiesto incluido.
- Inicio del modo de terminal, ayuda y salida comprobados con servicios simulados y carpeta temporal.

## Correcciones de preparación

La copia inicial omitió la guía que lee el programa y un corpus de pruebas. Se incorporaron tras revisar su contenido. Los vocabularios actualizados contienen reglas generales, por lo que se revisaron y conservaron como recursos base.

La prueba de orden del servidor dependía de una ruta fija del equipo original. Ahora requiere SEGUNDO_CEREBRO_DIR explícito; solo se omite esa comprobación externa cuando no se configura. Si se configura una ruta incorrecta, sigue fallando. Sus otras dos comprobaciones se ejecutan normalmente. No se cambió el servidor externo ni se copió a este proyecto.

Las versiones de cuatro complementos Python se anotaron en requirements.txt. No se instalaron paquetes ni se actualizaron servicios.

## Privacidad

La copia no contiene datos, conversaciones de trabajo, registros, respaldos, historial Git original ni configuraciones privadas. La búsqueda de formatos comunes de credenciales y rutas personales originales no encontró coincidencias. Los bloques de claves en las pruebas se construyen con texto ficticio. Los correos revisados corresponden a ejemplos o créditos de terceros, que se conservaron.

Esta comprobación estática no garantiza detectar cualquier dato privado. Se conservaron nombres ficticios y el nombre Diego en algunos ejemplos; eso no implica que se haya publicado una conversación real.

## Alcance y pendientes

Se usó Python 3.14.4 y dependencias ya disponibles en este equipo. No se verificó una instalación desde cero ni compatibilidad con otras versiones de Python, sistemas o equipos.

No se ejecutó inferencia con modelos reales ni se comprobaron cuentas externas. Las pruebas de transporte utilizan servidores de prueba o respuestas simuladas. No se cambió la instalación original de Jarvis.

Para el componente externo, define SEGUNDO_CEREBRO_DIR solo si quieres comprobar su código de servidor. Jarvis no incluye ese servidor.

Antes de publicar: revisar la licencia del código propio, preparar imágenes con datos ficticios y comprobar la instalación siguiendo el README desde un entorno limpio.

El resumen por archivo está en RESULTADOS_COMPROBACION.json. Los registros detallados se mantienen fuera de la carpeta para publicar.

## Comprobación posterior de instalación e inferencia

Se completó la instalación en un entorno virtual nuevo y una respuesta real a través del controlador. El resultado vigente de esa comprobación es 2760 aprobados y 2 omitidos, con 34 pruebas gráficas reales. Los límites y resultados se detallan en INSTALACION_VERIFICADA.md. Los pendientes anteriores relativos a inferencia y entorno Python ya fueron comprobados en el alcance indicado; sigue pendiente otro equipo o sistema nuevo.
