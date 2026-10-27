"""Movimiento explícito de recuerdos seleccionados desde la interfaz gráfica."""
from __future__ import annotations
import hashlib


def coincide_registro(visto, actual):
    """Verifica contenido completo o su huella cuando el listado traía una muestra."""
    if visto.get('id') != actual.get('id') or visto.get('proyecto') != actual.get('proyecto'):
        return False
    contenido=actual.get('contenido','')
    if visto.get('recortado'):
        huella=visto.get('contenido_sha256')
        return bool(isinstance(contenido,str) and huella and hashlib.sha256(contenido.encode('utf-8')).hexdigest()==huella)
    return contenido==visto.get('contenido')


def mover_varios(cliente, registros: list[dict], destino: str, confirmar) -> dict:
    """Verifica toda la selección y la mueve con una sola autorización."""
    if not isinstance(registros, list) or not registros or len(registros) > 1000:
        return {'ok': False, 'error': 'Selecciona entre 1 y 1000 registros.'}
    if any(not isinstance(r, dict) or type(r.get('id')) is not int for r in registros):
        return {'ok': False, 'error': 'La selección contiene un registro no válido.'}
    if len({r['id'] for r in registros}) != len(registros):
        return {'ok': False, 'error': 'La selección contiene registros duplicados; actualiza la lista.'}
    destino = destino.strip()
    if not destino or len(destino) > 100:
        return {'ok': False, 'error': 'Escribe un nombre de proyecto de 1 a 100 caracteres.'}
    verificados=[]
    for registro in registros:
        consulta=cliente.llamar('consultar_memoria', {'id_memoria':registro['id']})
        actuales=consulta.get('memorias', [])
        if not consulta.get('ok') or not actuales:
            return {'ok':False,'error':f"No pude verificar «{registro.get('titulo','Sin título')}». Actualiza la lista; no moví ninguno."}
        actual=actuales[0]
        if not coincide_registro(registro,actual):
            return {'ok':False,'error':f"«{registro.get('titulo','Sin título')}» cambió desde que abriste la lista. Actualízala; no moví ninguno."}
        verificados.append(actual)

    lista = cliente.llamar('listar_proyectos', {}).get('proyectos', [])
    existente = next((p.get('proyecto', '') for p in lista
                      if isinstance(p, dict) and p.get('proyecto', '').casefold() == destino.casefold()), None)
    nombre_destino = existente or destino
    crear = existente is None
    pendientes=[r for r in verificados if r.get('proyecto','').casefold() != nombre_destino.casefold()]
    if not pendientes:
        return {'ok':True,'sin_cambios':True,'proyecto':nombre_destino,
                'titulos':[r.get('titulo') or 'Sin título' for r in verificados]}
    aviso_creacion = f"También se creará el proyecto «{nombre_destino}» vacío.\n\n" if crear else ''
    detalles=[]
    for indice, registro in enumerate(pendientes,1):
        contenido=registro.get('contenido','')
        detalle=f"{indice}. {registro.get('titulo') or 'Sin título'} · {registro.get('proyecto','')} → {nombre_destino}"
        if contenido:
            detalle+='\n   '+contenido[:420].replace('\n',' ')
            if len(contenido)>420: detalle+='…'
        detalles.append(detalle)
    pedido=f"{aviso_creacion}Mover {len(pendientes)} registro(s):\n\n"+'\n\n'.join(detalles)
    if not confirmar(pedido):
        return {'ok': False, 'error': 'No autorizaste el cambio; los registros permanecen en sus proyectos.'}

    if crear:
        creado = cliente.llamar('crear_proyecto', {'proyecto': nombre_destino})
        if not creado.get('ok'):
            return {'ok': False, 'error': creado.get('error', 'No se pudo crear el proyecto.')}
        nombre_destino = creado.get('proyecto', nombre_destino)

    movidos=[]
    for registro in pendientes:
        resultado=cliente.llamar('clasificar_memoria', {
            'id_memoria':registro['id'],'proyecto':nombre_destino,
            'contenido_esperado':registro.get('contenido',''),
            'proyecto_esperado':registro.get('proyecto',''),
        })
        if not resultado.get('ok') or resultado.get('estado') != 'clasificada':
            return {'ok':False,'proyecto_creado':crear,'movidos':movidos,
                    'error':resultado.get('error','Segundo Cerebro no confirmó el movimiento. Actualiza la lista antes de repetirlo.')}
        movidos.append(registro.get('titulo') or 'Sin título')
    return {'ok':True,'proyecto':nombre_destino,'titulos':movidos,'cantidad':len(movidos)}


def mover(cliente, registro: dict, destino: str, confirmar) -> dict:
    """Compatibilidad para llamar el movimiento con un único registro."""
    return mover_varios(cliente,[registro],destino,confirmar)
