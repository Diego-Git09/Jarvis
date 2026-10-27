"""Una edición JSON inválida no impide abrir Jarvis ni se sobrescribe."""
import json
from pathlib import Path
import warnings

def validar(valor,base):
    if type(valor) is not type(base):raise ValueError('Tipo de vocabulario incorrecto')
    if isinstance(base,dict):
        for clave,ejemplo in base.items():
            if clave not in valor:raise ValueError('Falta '+clave)
            validar(valor[clave],ejemplo)
    elif isinstance(base,list):
        if not valor or len(valor)>1000 or any(not isinstance(x,str) or len(x)>300 for x in valor):raise ValueError('Lista de variantes inválida')
    elif isinstance(base,str) and len(valor)>2000:raise ValueError('Variante demasiado larga')
    return valor

def cargar(nombre,carpeta=None):
    carpeta=Path(carpeta or Path(__file__).parent)
    base=json.loads((carpeta/(Path(nombre).stem+'_base.json')).read_text())
    try:
        p=carpeta/nombre
        if p.stat().st_size>200000:raise ValueError('Vocabulario demasiado grande')
        return validar(json.loads(p.read_text()),base)
    except (OSError,ValueError,TypeError,KeyError):
        warnings.warn(nombre+' no es válido; cargué el vocabulario base. Conservé tu archivo para corregirlo.',RuntimeWarning)
        return base
