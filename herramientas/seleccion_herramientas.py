"""Catálogos pequeños por intención; nunca ejecuta ni concede permisos."""
import re
from lenguaje_jarvis import normalizar


def memoria(pregunta):
    n=normalizar(pregunta)
    lectura={'buscar_memoria_semantica','buscar_memoria','ver_recuerdo'}
    nombres=set()
    if re.search(r'\b(?:estado|funciona|pendientes|sincronizacion|sincroniza|errores|contradicciones)\b',n):
        nombres.add('consultar_estado_cerebro')
    if re.search(r'\bproyectos?\b',n):nombres.add('listar_proyectos')
    if re.search(r'\b(?:ultimo|ultima|reciente)\b.*\bconversacion\b|\bconversacion\b.*\b(?:ultima|reciente)\b',n):
        nombres|={'consultar_ultima_conversacion','ver_recuerdo'}
    elif re.search(r'\b(?:ultimo|ultima|reciente)\b',n):
        nombres|={'consultar_ultimo_recuerdo','ver_recuerdo'}
    if re.search(r'\b(?:busca|buscar|hablamos|dijimos|conversamos|dije|recuerdas|recuerdas|encuentra|encuentres|relacionado)\b',n):nombres|=lectura
    if re.search(r'\b(?:lista|listar|muestra|muestrame|guardado|guardadas|clasificar|clasificados|recuerdos|memorias)\b',n) and not re.search(r'\bproyectos?\b',n):
        nombres|={'listar_memorias','ver_recuerdo'}
    if re.search(r'\b(?:corrige|corregir|modifica|actualiza)\b',n):nombres|=lectura|{'corregir_memoria'}
    if re.search(r'\b(?:olvida|olvidar|elimina|borra)\b',n):nombres|=lectura|{'olvidar_memoria'}
    if re.search(r'\b(?:clasifica|clasificar|mueve|mover|traslada|asigna|reubica|agrega|anade)\b',n):
        nombres|={'listar_memorias','ver_recuerdo','listar_proyectos','clasificar_memoria','clasificar_recuerdos'}
    if re.search(r'\b(?:crea|crear|nuevo)\b.*\bproyecto\b',n):nombres|={'crear_proyecto','listar_proyectos'}
    return nombres or lectura|{'listar_memorias'}


GENERICAS={'listar_archivos','encontrar_archivos','consultar_proyecto_codigo','buscar_memoria_semantica','listar_proyectos','calcular'}
