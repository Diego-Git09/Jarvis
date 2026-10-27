"""Estimaciones por componente; el total real solo lo devuelve Ollama.

El esquema JSON se cuenta de forma conservadora aunque su coste de entrada
depende del motor. No se presenta esta medida como tokenización exacta.
"""
import json
import math

BYTES_POR_TOKEN=2.5


def calibrar(estado,modelo,componentes,reales):
    """Solo información: la admisión conserva siempre la estimación conservadora."""
    estimados=componentes.get('entrada_tokens_estimados')
    if type(reales) is not int or type(estimados) is not int or not 0<reales or not 0<estimados:return
    ratio=reales/estimados
    if not .25<=ratio<=2:return
    tabla=estado.setdefault('_calibracion_contexto',{})
    muestras=tabla.setdefault(modelo,[])
    muestras.append(ratio);del muestras[:-52]
    componentes['muestras_calibracion']=len(muestras)
    if len(muestras)>=5:
        p90=sorted(muestras)[math.ceil(len(muestras)*.9)-1]
        componentes['entrada_calibrada_tokens']=round(estimados*p90)
        componentes['factor_calibracion']=round(p90,3)
        componentes['entrada_p90_margen_tokens']=math.ceil(estimados*p90*1.1)
        componentes['metodo_calibracion']='percentil 90 con margen informativo del 10 %; coeficiente global sin modificar'


def tokens(dato):
    texto=dato if isinstance(dato,str) else json.dumps(dato,ensure_ascii=False,separators=(',',':'))
    return math.ceil(len(texto.encode('utf-8'))/BYTES_POR_TOKEN)


def limites(num_ctx,num_predict):
    salida=min(num_predict,num_ctx//3)
    margen=max(640,num_ctx//10)
    return {'ventana_tokens':num_ctx,'salida_reservada_tokens':salida,'margen_tokens':margen,
            'entrada_limite_tokens':num_ctx-salida-margen}


def componentes(cuerpo,num_ctx,num_predict,indices_resultados=()):
    reglas=[];historial=[];resultados=[]
    for indice,m in enumerate(cuerpo.get('messages',[])):
        limpio={k:v for k,v in m.items() if k not in {'images','thinking'}}
        destino=reglas if m.get('role')=='system' else resultados if indice in indices_resultados or m.get('role')=='tool' or m.get('tool_calls') else historial
        destino.append(limpio)
    herramientas={'tools':cuerpo.get('tools',[]),'format':cuerpo.get('format',{})}
    r=limites(num_ctx,num_predict)
    r.update(reglas_tokens_estimados=tokens(reglas),herramientas_tokens_estimados=tokens(herramientas),
             historial_tokens_estimados=tokens(historial),resultados_tokens_estimados=tokens(resultados),
             tokenizacion_exacta=False)
    r['entrada_tokens_estimados']=sum(r[k] for k in ('reglas_tokens_estimados','herramientas_tokens_estimados','historial_tokens_estimados','resultados_tokens_estimados'))
    r['herramientas_anunciadas']=len(cuerpo.get('tools',[]))
    return r


def fijo(cuerpo):
    return tokens([m for m in cuerpo.get('messages',[]) if m.get('role')=='system'])+tokens({'tools':cuerpo.get('tools',[]),'format':cuerpo.get('format',{})})


def presentar(r):
    lineas=['Último presupuesto de contexto enviado/preparado:',
            f"• Ventana: {r['ventana_tokens']} tokens; salida reservada: {r['salida_reservada_tokens']}; margen: {r['margen_tokens']}."]
    for titulo,clave in [('Reglas','reglas'),('Herramientas y esquema','herramientas'),('Historial y pregunta','historial'),('Resultados de herramientas y referencias','resultados')]:
        lineas.append(f"• {titulo}: ~{r[clave+'_tokens_estimados']} tokens.")
    lineas.append(f"• Entrada estimada: ~{r['entrada_tokens_estimados']} / {r['entrada_limite_tokens']} disponibles.")
    if type(r.get('tokens_entrada_reales')) is int:lineas.append(f"• Entrada real comunicada por Ollama: {r['tokens_entrada_reales']} tokens en total.")
    else:lineas.append('• Entrada real: todavía no disponible para esta preparación.')
    lineas.append('El desglose es una estimación de bytes UTF-8, no un tokenizador exacto; la cifra real total se comprueba tras la respuesta.')
    if 'entrada_calibrada_tokens' in r:
        lineas.append(f"• Estimación informativa calibrada con {r['muestras_calibracion']} respuestas de este modelo: ~{r['entrada_calibrada_tokens']} tokens. La admisión conserva el tope conservador anterior.")
        if 'entrada_p90_margen_tokens' in r:lineas.append(f"• P90 más margen del 10 %: ~{r['entrada_p90_margen_tokens']} tokens; propuesta informativa, sin ampliar la ventana.")
    return '\n'.join(lineas)
