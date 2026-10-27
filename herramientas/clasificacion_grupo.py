"""Clasifica una selección estable del último resultado con una autorización."""
from clasificacion_interfaz import coincide_registro

def clasificar(numeros, proyecto, estado, cliente, confirmar, registrar):
    mapa = dict(estado.get('_lista_memorias', {}))
    cache = estado.setdefault('_memorias', {})
    faltan = [n for n in numeros if n not in mapa or mapa[n] not in cache]
    if faltan:
        return {'ok': False, 'error': f'Los números {faltan} no están disponibles en el último listado. Abre /recuerdos o /sin_clasificar de nuevo.'}
    seleccion = []
    for numero in numeros:
        ident = mapa[numero]
        visto = dict(cache[ident])
        try:
            r = cliente.llamar('consultar_memoria', {'id_memoria': ident})
        except ConnectionError:
            return {'ok': False, 'error': 'No pude verificar toda la selección. No moví ningún recuerdo.'}
        actuales = r.get('memorias', [])
        if not r.get('ok') or not actuales or not coincide_registro(visto,actuales[0]):
            return {'ok': False, 'error': f'El recuerdo {numero} cambió o ya no existe. Actualiza el listado. No moví ningún recuerdo.'}
        seleccion.append((numero, ident, dict(actuales[0])))
    pendientes = [(n, i, m) for n, i, m in seleccion if m.get('proyecto', '').casefold() != proyecto.casefold()]
    resultados = [{'numero':n, 'titulo':m.get('titulo',''), 'estado':'ya_clasificado'} for n,i,m in seleccion if (n,i,m) not in pendientes]
    if not pendientes:
        return {'ok': True, 'resultados': resultados, 'proyecto': proyecto}
    detalles = [f"{n}. {m.get('titulo', 'Sin título')}\nProyecto actual: {m.get('proyecto', '')}\nContenido:\n{m['contenido']}" for n,i,m in pendientes]
    pedido = f"Mover {len(pendientes)} recuerdo(s) al proyecto «{proyecto}»:\n\n" + '\n\n'.join(detalles)
    if not confirmar(pedido):
        registrar('clasificar_recuerdos', {'cantidad':len(pendientes)}, False, 'permiso denegado')
        return {'ok': False, 'error': 'No autorizaste la selección. No se movió ningún recuerdo.'}
    for n, ident, m in pendientes:
        try:
            r = cliente.llamar('clasificar_memoria', {'id_memoria':ident,'proyecto':proyecto,
                'contenido_esperado':m['contenido'],'proyecto_esperado':m.get('proyecto','')})
        except ConnectionError:
            r = {'ok': False, 'error':'Se perdió la conexión. Consulta este recuerdo antes de repetirlo; el servidor podría haberlo movido.'}
        ok = r.get('ok') and r.get('estado') == 'clasificada'
        registrar('clasificar_memoria', {'id_memoria':ident}, bool(ok), 'completado' if ok else 'falló; verificar')
        if not ok:
            return {'ok': False, 'resultados': resultados, 'error': f"Me detuve en el recuerdo {n}: {r.get('error', 'el servidor no confirmó el cambio')}", 'proyecto':proyecto}
        destino = r.get('proyecto', proyecto)
        cache[ident] = dict(m, proyecto=destino)
        for fila in estado.get('_listado_completo', []) + estado.get('_ultima_pagina_visible', {}).get('memorias', []):
            if fila.get('id') == ident:
                fila['proyecto'] = destino
        resultados.append({'numero':n, 'titulo':m.get('titulo',''), 'estado':'clasificado'})
    return {'ok': True, 'resultados': sorted(resultados,key=lambda r:r['numero']), 'proyecto':proyecto,
            'nota':'Usa /sin_clasificar para actualizar el listado restante.'}
