"""Clima por datos meteorológicos públicos; no depende de que un LLM lo invente."""
import json
import math
import re
from urllib.parse import urlencode
import internet_jarvis as W
from lenguaje_jarvis import normalizar,limpiar

CODIGOS={0:'despejado',1:'principalmente despejado',2:'parcialmente nublado',3:'cubierto',45:'niebla',48:'niebla con escarcha',
         51:'llovizna leve',53:'llovizna',55:'llovizna intensa',61:'lluvia leve',63:'lluvia',65:'lluvia intensa',
         71:'nieve leve',73:'nieve',75:'nieve intensa',80:'chubascos leves',81:'chubascos',82:'chubascos intensos',95:'tormenta',96:'tormenta con granizo',99:'tormenta con granizo fuerte'}


def _json(url):
    b,_,_=W.solicitar_publico(url);d=json.loads(b)
    if not isinstance(d,dict) or d.get('error'):raise ValueError('La fuente meteorológica no devolvió datos válidos.')
    return d


def _numero(v):
    if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('La fuente meteorológica omitió un valor necesario.')
    return v


def consultar_clima(lugar,periodo='hoy',pais=''):
    try:
        if not isinstance(lugar,str) or not 1<=len(lugar.strip())<=100:raise ValueError('Indica una ciudad y, si es ambigua, su país.')
        if periodo not in ('hoy','manana','semana'):raise ValueError('Elige hoy, mañana o semana.')
        if pais and not re.fullmatch('[A-Za-z]{2}',pais):raise ValueError('El país debe ser un código de dos letras, como CL.')
        if normalizar(lugar).strip() in ('santiago','santiago de chile','santiago chile') and not pais:pais='CL';lugar='Santiago'
        params={'name':lugar,'count':5,'language':'es','format':'json'}
        if pais:params['countryCode']=pais.upper()
        geo=_json('https://geocoding-api.open-meteo.com/v1/search?'+urlencode(params)).get('results',[])
        if not geo:raise ValueError('No encontré esa ciudad. Prueba con ciudad y país.')
        if len({x.get('country_code') for x in geo})>1 and not pais:
            raise ValueError('Hay varios lugares con ese nombre: '+', '.join(dict.fromkeys(x.get('name','')+', '+x.get('country','') for x in geo))+'. Indica el país.')
        ciudad=max(geo,key=lambda x:x.get('population',0));lat=_numero(ciudad['latitude']);lon=_numero(ciudad['longitude'])
        if not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Coordenadas inválidas.')
        url='https://api.open-meteo.com/v1/forecast?'+urlencode({'latitude':lat,'longitude':lon,'timezone':'auto',
           'current':'temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m',
           'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code','forecast_days':7 if periodo=='semana' else 2 if periodo=='manana' else 1})
        d=_json(url);actual=d['current'];daily=d['daily'];dias=[]
        for i,fecha in enumerate(daily['time']):
            if periodo=='manana' and i==0:continue
            dias.append({'fecha':fecha,'minima':_numero(daily['temperature_2m_min'][i]),'maxima':_numero(daily['temperature_2m_max'][i]),
                         'probabilidad_lluvia':_numero(daily['precipitation_probability_max'][i]),'estado':CODIGOS.get(daily['weather_code'][i],'condiciones no traducidas')})
        return {'ok':True,'lugar':ciudad['name']+', '+ciudad.get('country',''),'zona':d.get('timezone',''),
                'hora_datos':actual['time'],'temperatura':_numero(actual['temperature_2m']), 'sensacion':_numero(actual['apparent_temperature']),
                'humedad':_numero(actual['relative_humidity_2m']),'viento':_numero(actual['wind_speed_10m']),
                'estado':CODIGOS.get(actual['weather_code'],'condiciones no traducidas'),'dias':dias,'url':url,'consultado':W.fecha()}
    except (OSError,ValueError,TypeError,KeyError,IndexError,W.http.client.HTTPException) as e:
        if isinstance(e,W.ErrorHTTP):
            return {'ok':False,'causa':'servicio','error':f'El servicio meteorológico respondió HTTP {e.codigo}. Intenta nuevamente más tarde.'}
        if isinstance(e,(OSError,W.http.client.HTTPException)):
            return {'ok':False,'causa':'red','error':'Falló la conexión de red o se agotó su tiempo. Comprueba Internet y reintenta; no confirma que el servicio esté caído.'}
        from errores_usuario import presentar
        return {'ok':False,'causa':'datos','error':presentar(str(e))[:300]}


def presentar(r):
    if not r.get('ok'):return 'No pude verificar el clima: '+r.get('error','sin respuesta')+'. No inventaré datos meteorológicos.'
    return (f"Clima en {r['lugar']} · {r['hora_datos']} ({r['zona']})\n"
            f"{r['estado'].capitalize()}: {r['temperatura']:g} °C; sensación {r['sensacion']:g} °C.\n"
            f"Humedad: {r['humedad']:g} %. Viento: {r['viento']:g} km/h.\n\n"+
            '\n'.join(f"{x['fecha']}: {x['minima']:g}–{x['maxima']:g} °C · {x['estado']} · probabilidad de precipitación {x['probabilidad_lluvia']:g} %." for x in r['dias'])+
            f"\n\nFuente: Open-Meteo (estimaciones meteorológicas). Consulta: {r['consultado']}\n{r['url']}")


def interpretar_clima(p):
    n=normalizar(limpiar(p))
    if re.search(r'\b(?:ejemplo|condicion|conceptualmente|solo explica(?:lo)?|por que llueve|que (?:es|significa) (?:el )?clima)\b',n):return None
    if re.search(r'\bno (?:quiero|consultes|busques|verifiques|revises)\b',n):return None
    if re.search(r'\b(?:y (?:luego|despues|edita|mueve|crea)|despues|ademas)\b',n):return None
    if not re.search(r'\b(?:clima|pronostico|temperatura|llover|llueve|tiempo)\b',n):return None
    m=re.search(r'\b(?:en|de|para)\s+(.+)',limpiar(p),re.I)
    if not m:return None
    lugar=re.sub(r'\b(?:hoy|ahora|mañana|manana|esta semana|durante la semana|por favor)\b','',m[1],flags=re.I).strip(' ?.,')
    if not lugar:return None
    periodo='semana' if 'semana' in n else 'manana' if 'manana' in n else 'hoy'
    return {'lugar':lugar,'periodo':periodo}
