"""Cálculos pequeños mediante un árbol validado; nunca evalúa código arbitrario."""
import ast
import math
import operator
import re

BINARIOS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,
          ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
FUNCIONES={'raiz':math.sqrt,'sqrt':math.sqrt,'abs':abs,'redondear':round}


def calcular(expresion):
    if not isinstance(expresion,str) or not expresion.strip() or len(expresion)>500:raise ValueError('Escribe una expresión de hasta 500 caracteres')
    original=expresion.strip()
    texto=re.sub(r'(?<=\d),(?=\d)','.',original).replace('×','*').replace('÷','/').replace('^','**')
    porcentaje=re.fullmatch(r'\s*([+-]?\d+(?:\.\d+)?)\s*%\s*(?:de|del)\s*([+-]?\d+(?:\.\d+)?)\s*',texto,re.I)
    if porcentaje:texto=f'({porcentaje[1]}/100)*({porcentaje[2]})'
    try:arbol=ast.parse(texto,mode='eval')
    except (SyntaxError,ValueError):raise ValueError('No pude interpretar el cálculo. Ejemplo: /calcular (12 + 8) * 3 o /calcular 15% de 200') from None
    if sum(1 for _ in ast.walk(arbol))>80:raise ValueError('El cálculo tiene demasiadas operaciones')
    def visitar(nodo,profundidad=0):
        if profundidad>20:raise ValueError('El cálculo tiene demasiados niveles')
        if isinstance(nodo,ast.Constant) and type(nodo.value) in (int,float):resultado=nodo.value
        elif isinstance(nodo,ast.UnaryOp) and isinstance(nodo.op,(ast.UAdd,ast.USub)):
            resultado=visitar(nodo.operand,profundidad+1)*(1 if isinstance(nodo.op,ast.UAdd) else -1)
        elif isinstance(nodo,ast.BinOp) and type(nodo.op) in BINARIOS:
            a,b=visitar(nodo.left,profundidad+1),visitar(nodo.right,profundidad+1)
            if isinstance(nodo.op,ast.Pow) and abs(b)>100:raise ValueError('El exponente es demasiado grande (máximo 100)')
            resultado=BINARIOS[type(nodo.op)](a,b)
        elif isinstance(nodo,ast.Call) and isinstance(nodo.func,ast.Name) and nodo.func.id in FUNCIONES and len(nodo.args)==1 and not nodo.keywords:
            resultado=FUNCIONES[nodo.func.id](visitar(nodo.args[0],profundidad+1))
        else:raise ValueError('Solo se permiten números, operaciones y raiz, abs o redondear con un argumento')
        if type(resultado) not in (int,float) or not math.isfinite(resultado) or abs(resultado)>1e100:
            raise ValueError('El resultado es demasiado grande o no es un número real')
        return resultado
    try:resultado=visitar(arbol.body)
    except ZeroDivisionError:raise ValueError('No se puede dividir entre cero') from None
    except (OverflowError,RecursionError):raise ValueError('El cálculo supera los límites permitidos') from None
    except ValueError as e:
        if str(e)=='math domain error':raise ValueError('La raíz requiere un número no negativo') from None
        raise
    return {'expresion':original,'resultado':resultado}


def presentar(resultado):
    numero=resultado['resultado']
    return f"{resultado['expresion']} = {numero:.12g}" if isinstance(numero,float) else f"{resultado['expresion']} = {numero}"
