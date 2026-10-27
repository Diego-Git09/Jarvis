"""Umbrales preventivos de Jarvis; no cambian el hardware ni sus límites."""
import json,re
from entorno_jarvis import DATOS
from conversaciones_jarvis import _atomic

ARCHIVO=DATOS/'umbrales_temperatura.json'
DEFAULT={'gpu':80,'cpu':90}

def leer():
    if ARCHIVO.is_symlink() or any(p.is_symlink() for p in ARCHIVO.parents):raise ValueError('Ruta de umbrales no segura')
    try:
        if ARCHIVO.stat().st_size>1000:raise ValueError('Umbrales inválidos')
        d=json.loads(ARCHIVO.read_text())
    except FileNotFoundError:return dict(DEFAULT)
    if not isinstance(d,dict) or set(d)!=set(DEFAULT) or any(type(v) is not int or not 50<=v<=100 for v in d.values()):raise ValueError('Umbrales inválidos; archivo conservado')
    return d

def comando(p,confirmar):
    n=p.strip().casefold()
    if not re.match(r'^/temperatura(?:\s|$)',n):return False,''
    try:
        d=leer()
        if n=='/temperatura':
            import control_recursos as R
            return True,'\n'.join(R.diagnostico_termico())+'\n/temperatura gpu 80 o /temperatura cpu 90 cambia solo el umbral de Jarvis, con s/n.'
        m=re.fullmatch(r'/temperatura (gpu|cpu) (\d{2,3})',n)
        if not m or not 50<=int(m[2])<=100:return True,'Uso: /temperatura gpu|cpu GRADOS, entre 50 y 100. Es una política preventiva, no el máximo del fabricante.'
        nuevo=dict(d);nuevo[m[1]]=int(m[2])
        if not confirmar(f"Umbral {m[1].upper()}: {d[m[1]]} °C → {nuevo[m[1]]} °C. No modifica ventiladores, energía ni el sistema. ¿Guardar?"):return True,'Umbral sin cambios.'
        if leer()!=d:raise ValueError('Los umbrales cambiaron; vuelve a revisarlos')
        _atomic(ARCHIVO,nuevo)
        if leer()!=nuevo:raise ValueError('No se pudo verificar el umbral')
        return True,'Umbral guardado y comprobado. Se aplica antes de la próxima inferencia.'
    except (OSError,ValueError):return True,'No pude leer o guardar los umbrales. Conservé el archivo; no cambié el hardware.'
