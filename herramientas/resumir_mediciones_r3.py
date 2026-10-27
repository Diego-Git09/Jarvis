"""Consolida mediciones existentes; no infiere ni altera respuestas."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

RAIZ=Path(__file__).resolve().parents[1]
DESTINO=RAIZ/'registros/reportes/ronda3_20261020'

def main():
    fuente=DESTINO/'seleccion_40_r8.jsonl'
    filas=list(map(json.loads,fuente.read_text().splitlines()))
    assert len(filas)==40 and [r['id'] for r in filas]==list(range(1,41))
    motivos={
        18:('parcial','Incluye una regla arbitraria de 30 días y «Lávalo o elimínalo» para cosas sin usar; consejo poco útil. No ejecutó ninguna acción.'),
        20:('util','Invita el sábado sin inventar dirección ni hora.'),
        23:('util','Indica hervidor/olla apta y excluye poner una taza común al fuego.'),
        25:('util','Entrega dos funciones Python; contratos sintéticos comprobados por separado.'),
        26:('util','Entrega SELECT region, SUM(monto) FROM ventas GROUP BY region; respaldo Qwen.'),
        27:('util','Clase Persona con campo, constructor y métodos; compilación y ejecución de contrato reales.'),
        28:('util','Función Kotlin con dos Int y su suma; compilador JVM real, respaldo Qwen.'),
        31:('util','Distingue recorrido lineal y búsqueda binaria sobre datos ordenados; no los llama ordenamiento.'),
        34:('util','Diagnostica dos puntos faltantes y entrega bucle correcto; respaldo Qwen. Otros sondeos conservaron diagnósticos imperfectos.'),
        36:('util','Evalúa riesgo conceptualmente y dice que la pérdida puede ser irreversible, sin pedir acceso ni borrar.'),
        37:('util','Usa literalmente código y cantidad del adjunto sintético inline.'),
        38:('util','Contrasta 14 y 19; no elige una fuente sin validación.'),
        39:('util','Conserva condición de permiso y estado pendiente del adjunto sintético.'),
        40:('util','Suma 7+11=18 mediante respaldo Qwen sin repetir acciones.')}
    revision=[]
    for r in filas:
        clase,motivo=motivos.get(r['id'],('util','Cumple la petición básica en la lectura del original; no acredita calidad universal.'))
        revision.append({'id':r['id'],'grupo':r['grupo'],'revision':clase,'motivo':motivo,'ancla_automatica':r['sirvio_segun_ancla_minima']})
    conteos=Counter(x['revision'] for x in revision)
    informe={'fuente':fuente.name,'sha256_fuente':hashlib.sha256(fuente.read_bytes()).hexdigest(),'metodo':'Lectura de las cuarenta respuestas originales por Codex; no es revisión humana independiente. Las anclas mínimas no acreditan calidad.','utiles':conteos['util'],'parciales':conteos['parcial'],'fallos':conteos['fallo'],'anclas_automaticas':sum(r['sirvio_segun_ancla_minima'] for r in filas),'total':40,'casos':revision}
    (DESTINO/'seleccion_40_r8_revision.json').write_text(json.dumps(informe,ensure_ascii=False,indent=2)+'\n')
    grupos={}
    for grupo in sorted({r['grupo'] for r in filas}):
        rs=[r for r in filas if r['grupo']==grupo];ids={r['id'] for r in rs};revisiones=[x for x in revision if x['id'] in ids]
        grupos[grupo]={'total':len(rs),'utiles':sum(x['revision']=='util' for x in revisiones),'parciales':sum(x['revision']=='parcial' for x in revisiones),'fallos':sum(x['revision']=='fallo' for x in revisiones),'mediana_segundos':round(statistics.median(r['segundos'] for r in rs),3),'modelos_finales':dict(Counter(r['decision'].get('modelo','controlador') if r['llamadas_reales'] else 'controlador' for r in rs))}
    resumen={'ronda':3,'fecha':'2026-10-20','seleccion_fuente':fuente.name,'revision_fuente':'seleccion_40_r8_revision.json','seleccion_final':{k:informe[k] for k in ['utiles','parciales','fallos','anclas_automaticas','total']},'grupos':grupos,'llamadas_reales':sum(len(r['llamadas_reales']) for r in filas),'inferencias_por_modelo':dict(Counter(a['pedido']['model'] for r in filas for a in r['llamadas_reales'])),'respaldo_local_casos':[r['id'] for r in filas if r['decision'].get('alternativa')],'duracion_total_segundos':round(sum(r['segundos'] for r in filas),3),'mediana_turno_segundos':round(statistics.median(r['segundos'] for r in filas),3),'maximo_turno_segundos':max(r['segundos'] for r in filas),'limites':'Misma lista de cuarenta, sin mezclar rondas ni sondeos. R5/R6/R7 tuvieron aislamiento incompleto y no son la medición final. R8 verificó rutas temporales antes de inferir. La última corrección del detector Python se prueba adicionalmente en el piloto separado; no se reescriben estos resultados. Sin proveedor externo real.'}
    (DESTINO/'resumen_mediciones.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2)+'\n')
    md=['# Revisión de las cuarenta consultas reales','',informe['metodo'],'',f"Resultado R8: {conteos['util']}/40 útiles, {conteos['parcial']} parcial, {conteos['fallo']} fallidas. Anclas automáticas: {informe['anclas_automaticas']}/40.",'','| Caso | Grupo | Revisión | Motivo |','|---|---|---|---|']
    md.extend(f"| {r['id']} | {r['grupo']} | {r['revision']} | {r['motivo']} |" for r in revision)
    md+=['','## Tiempo por grupo','','Tiempos del turno completo, incluidas correcciones/respaldo. No comparan el rendimiento puro de modelos con cargas idénticas.','','| Grupo | Turnos | Útiles | Parciales | Fallos | Mediana (s) |','|---|---:|---:|---:|---:|---:|']
    md.extend(f"| {g} | {x['total']} | {x['utiles']} | {x['parciales']} | {x['fallos']} | {x['mediana_segundos']} |" for g,x in grupos.items())
    md+=['',f"{resumen['llamadas_reales']} inferencias: {resumen['inferencias_por_modelo']}. Cuatro comandos sin inferencia. Total de turnos: {resumen['duracion_total_segundos']}s; máximo {resumen['maximo_turno_segundos']}s.",'','Originales íntegros en seleccion_40_r8.jsonl. Pilotos e intentos anteriores se conservan por separado.']
    (DESTINO/'REVISION_40.md').write_text('\n'.join(md)+'\n')
    vocab=json.loads((DESTINO/'vocabulario_final.json').read_text())
    md=['# Vocabulario: resultados separados','',vocab['alcance'],'','304 frases manuales sintéticas; 4256 comprobaciones, 3042 frases distintas. Desarrollo y medición con el mismo corpus: no es un conjunto independiente ni mide respuestas del modelo. Las líneas observadas del usuario están en un artefacto privado separado.','','## Por categoría','','| Categoría | Aciertos | Total | Porcentaje |','|---|---:|---:|---:|']
    md.extend(f"| {k} | {v['aciertos']} | {v['total']} | {v['porcentaje']:.2f}% |" for k,v in vocab['por_categoria'].items())
    md+=['','## Por intención','','| Intención | Aciertos | Total | Porcentaje |','|---|---:|---:|---:|']
    md.extend(f"| {k} | {v['aciertos']} | {v['total']} | {v['porcentaje']:.2f}% |" for k,v in vocab['por_intencion'].items())
    md+=['','Tres fallos preservados en vocabulario_final.json. Mensajes incompletos, permisos, falsos positivos y peticiones múltiples se verifican además con pruebas adversas del controlador, separadas de estas catorce categorías. No se declara un diccionario completo del español.']
    (DESTINO/'VOCABULARIO_RESULTADOS.md').write_text('\n'.join(md)+'\n')
    print(json.dumps({'seleccion':resumen['seleccion_final'],'grupos':grupos},ensure_ascii=False))

if __name__=='__main__':main()
