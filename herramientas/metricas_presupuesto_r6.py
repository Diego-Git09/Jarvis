"""Propuesta informativa basada en P90; nunca cambia la ventana ni coeficientes."""
import math

def propuesta(filas,margen=.1):
    validas=[f for f in filas if f.get('ok') and not f.get('riesgo_truncado') and type(f.get('tokens_reales')) is int and f['tokens_reales']>0 and type(f.get('bytes_componentes')) is int and f['bytes_componentes']>0]
    if len(validas)<5:return {'estado':'muestras insuficientes','muestras':len(validas)}
    densidades=sorted(f['tokens_reales']/f['bytes_componentes'] for f in validas)
    p90=densidades[math.ceil(len(densidades)*.9)-1]
    return {'estado':'propuesta pendiente de revisión','muestras':len(validas),'metodo':'P90 de tokens reales/bytes serializados de los componentes, más 10 %','p90_tokens_por_byte':p90,'margen':margen,'bytes_por_token_propuesto':round(1/(p90*(1+margen)),3),'coeficiente_aplicado':False}
