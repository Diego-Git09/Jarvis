"""Datos locales de modelos, sin atribuir memoria a partir del nombre del chat."""
import re
from normalizacion_entrada import vista


def modelos_memoria(pedido, cliente):
    n=vista(pedido)
    if not ((re.search(r'\b(?:cuanto (?:pesa|ocupa|consume)|tamano|memoria necesaria)\b',n) or re.search(r'\bq4\b',n) and re.search(r'\b(?:ocupa|pesa|consume)\b',n))
            and re.search(r'\b(?:modelo|8b|8 b)\b',n) and re.search(r'\b(?:vram|ram|memoria|gpu)\b',n)):
        return None
    texto=('El tamaño depende de la precisión, no solo de que diga 8B.\n'
           '1. Pesos teóricos ≈ parámetros × bytes por peso. Para 8.000 millones: FP32 ≈32 GB; FP16 ≈16 GB; Q4 ≈4 GB (decimales, solo pesos).\n'
           '2. La carga real añade metadatos, contexto y memoria de trabajo; una parte puede quedar en RAM.\n')
    try:
        r=cliente.solicitar('/api/ps',timeout=3)
        filas=r.get('models')
        if not isinstance(filas,list):raise ValueError('Lectura incompleta')
        from configuracion_jarvis import MODELO_PREDETERMINADO,MODELO_BASE_DEEPSEEK,MODELO_COTIDIANO
        propios={MODELO_PREDETERMINADO,MODELO_BASE_DEEPSEEK,MODELO_COTIDIANO}
        lineas=[]
        for m in filas:
            if m.get('name') not in propios:continue
            v=m.get('size_vram');s=m.get('size')
            if type(v) is not int or type(s) is not int or not 0<=v<=s:continue
            lineas.append(f"• {m['name']}: VRAM {v/1024**2:.0f} MiB ({v/1024**3:.2f} GiB); carga total {s/1024**3:.2f} GiB; contexto {m.get('context_length','no informado')} tokens.")
        texto+='3. Lectura actual de Ollama:\n'+('\n'.join(lineas) if lineas else 'No hay un modelo de Jarvis con memoria comprobable cargado ahora; no inventaré su consumo.')
    except (OSError,ValueError,ConnectionError,TypeError):
        texto+='3. No pude consultar la carga actual. /diagnostico permite comprobar la conexión; la fórmula anterior no es una medición de tu GPU.'
    return texto
