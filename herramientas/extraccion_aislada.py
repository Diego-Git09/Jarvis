"""Lectores en un proceso local con memoria virtual y tiempo acotados.

No es un sandbox general de sistema de archivos. Conserva el control de rutas
de Jarvis y ejecuta exclusivamente sus lectores, nunca el contenido del adjunto.
RLIMIT_AS limita memoria VIRTUAL por proceso, no RSS ni la suma de un árbol de
procesos. Los conversores externos heredan ese mismo límite por proceso.
"""
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
import re

RECURSOS_DEFAULT={'mb_proceso':256,'mb_buffer':8,'segundos_archivo':60,'segundos_tanda':600}
MAX_ENTRADA=16384
MAX_LINEA=131072
MAX_TEXTO=16384
MAX_REF=4096
MAX_META=65536
MAX_RESULTADO=MAX_LINEA-512
PROTOCOLO=1
_METADATOS={'tipo_real','soporte','aviso','cortado','codificacion','bytes_leidos',
            'caracteres_leidos','paginas','paginas_leidas','filas_leidas','hojas',
            'media','sha256_aislado','aislamiento','paginas_extraidas'}
_AVANCE={'bytes_leidos','caracteres_leidos','paginas','paginas_leidas','filas_leidas'}


def validar_recursos(recursos=None):
    if recursos is None:recursos={}
    if not isinstance(recursos,dict) or set(recursos)-set(RECURSOS_DEFAULT):
        raise ValueError('Recursos de extracción desconocidos.')
    r=dict(RECURSOS_DEFAULT,**recursos)
    for k in ('mb_proceso','mb_buffer'):
        a,b=(64,1024) if k=='mb_proceso' else (1,64)
        if type(r[k]) is not int or not a<=r[k]<=b:
            raise ValueError(f'{k} debe ser un entero entre {a} y {b}.')
    for k in ('segundos_archivo','segundos_tanda'):
        if type(r[k]) not in {int,float} or not math.isfinite(r[k]) or not .05<=r[k]<=3600:
            raise ValueError(f'{k} debe estar entre 0,05 y 3600 segundos.')
    return r


def _limitar(recursos):
    """Se llama DENTRO del nuevo Python, nunca mediante preexec_fn de Tk."""
    import resource
    memoria=recursos['mb_proceso']*1024**2
    previo=resource.getrlimit(resource.RLIMIT_AS)[1]
    if previo!=resource.RLIM_INFINITY:memoria=min(memoria,previo)
    resource.setrlimit(resource.RLIMIT_AS,(memoria,memoria))
    cpu=max(1,math.ceil(recursos['segundos_archivo']))
    resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+1))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    return memoria


def _comando_worker():
    # -I descarta PYTHONPATH y el directorio de trabajo del usuario.
    return [sys.executable,'-I','-B',str(Path(__file__).resolve()),'--worker']


def _entorno_worker():
    from entorno_jarvis import PROYECTO,en_pruebas
    # No se copian HOME, claves, tokens, variables de proveedores, sesiones de
    # escritorio, proxies, PYTHONPATH ni el entorno general del proceso GUI.
    return {'PATH':os.defpath,'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
            'JARVIS_DIR':str(PROYECTO),'JARVIS_PRUEBAS':'1' if en_pruebas() else '0'}


def _terminar(proceso):
    """El grupo fue creado por este Popen; no acepta PIDs proporcionados fuera."""
    try:os.killpg(proceso.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:proceso.wait(timeout=.2)
    except subprocess.TimeoutExpired:pass
    # Un descendiente puede ignorar TERM incluso si el líder ya terminó.
    try:os.killpg(proceso.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    try:proceso.wait(timeout=1)
    except subprocess.TimeoutExpired:pass
    for f in (proceso.stdin,proceso.stdout):
        if f and not f.closed:f.close()


def _preparar(item,limites,recursos,operacion='unidades',opciones=None):
    import herramientas_lectura as L
    import tandas_documentales as T
    if not isinstance(item,dict) or not isinstance(item.get('ruta'),str):
        raise ValueError('Fuente de extracción inválida.')
    ruta=L._resolver(item['ruta'])
    if not ruta.is_file():raise ValueError('La fuente no es un archivo normal.')
    l=T.validar_limites(limites)
    if operacion not in {'unidades','analizar'}:raise ValueError('Operación de lectura aislada desconocida.')
    max_bytes=500*1024**2 if operacion=='analizar' else l['mb_archivo']*1024**2
    if ruta.stat().st_size>max_bytes:
        raise ValueError('El archivo supera el límite autorizado de extracción.')
    # El manifiesto usa None para los archivos que no son miembros de un
    # comprimido. Solo los campos presentes llevan un valor textual al IPC.
    fuente={k:item[k] for k in ('nombre','tipo','miembro','contenedor','hash') if k in item and item[k] is not None}
    fuente['ruta']=str(ruta)
    fuente.setdefault('nombre',ruta.name)
    fuente.setdefault('tipo',ruta.suffix.lower())
    if any(not isinstance(fuente[k],str) for k in fuente):raise ValueError('Metadatos de entrada inválidos.')
    if '_pagina_documento' in item:
        if type(item['_pagina_documento']) is not int or not 1<=item['_pagina_documento']<=1_000_000:
            raise ValueError('La página solicitada debe ser un entero entre 1 y 1000000.')
        if item.get('miembro'):raise ValueError('El selector de página no se aplica a miembros de comprimidos.')
        fuente['_pagina_documento']=item['_pagina_documento']
    if len(fuente['nombre'].encode())>MAX_REF or len(str(ruta).encode())>4096:
        raise ValueError('Nombre/ruta de fuente demasiado extenso.')
    if operacion=='analizar':_validar_opciones_analisis(opciones)
    dato={'protocolo':PROTOCOLO,'operacion':operacion,'opciones':opciones or {},'item':fuente,
          'limites':l,'recursos':recursos,'firma_esperada':_firma(ruta)}
    entrada=(json.dumps(dato,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    if len(entrada)>MAX_ENTRADA:raise ValueError('Solicitud de extracción demasiado extensa.')
    return entrada


def _recibir(linea,item,esperado=None):
    try:d=json.loads(linea)
    except (ValueError,UnicodeError) as e:raise ValueError('El lector aislado devolvió un protocolo inválido.') from e
    if not isinstance(d,dict) or d.get('protocolo')!=PROTOCOLO:
        raise ValueError('Versión de protocolo del lector aislado inválida.')
    tipo=d.get('tipo')
    if tipo=='unidad':
        ref,texto=d.get('referencia'),d.get('texto')
        if not isinstance(ref,str) or not isinstance(texto,str) or len(ref.encode())>MAX_REF or len(texto.encode())>MAX_TEXTO:
            raise ValueError('Una unidad del lector excede el límite del protocolo.')
        avance=d.get('avance',{})
        if not isinstance(avance,dict) or set(avance)-_AVANCE or any(type(v) is not int or v<0 for v in avance.values()):
            raise ValueError('Progreso del lector inválido.')
        item.update(avance)
        return tipo,(ref,texto)
    if tipo=='fin':
        meta=d.get('metadatos')
        if not isinstance(meta,dict) or set(meta)-_METADATOS or len(json.dumps(meta,ensure_ascii=False).encode())>MAX_META:
            raise ValueError('Metadatos finales del lector inválidos.')
        huella=meta.get('sha256_aislado');aislado=meta.get('aislamiento');fuente=d.get('fuente')
        if not isinstance(huella,str) or not re.fullmatch('[a-f0-9]{64}',huella):
            raise ValueError('El lector no entregó una huella final válida.')
        if not isinstance(aislado,dict) or type(aislado.get('limite_as_mib')) is not int or not 1<=aislado['limite_as_mib']<=1024 or type(aislado.get('rss_max_kib')) is not int or aislado['rss_max_kib']<0:
            raise ValueError('El lector no confirmó su límite de memoria.')
        if not isinstance(fuente,dict) or set(fuente)!={'firma','sha256'} or not isinstance(fuente['firma'],list) or len(fuente['firma'])!=3 or any(type(n) is not int or n<0 for n in fuente['firma']) or fuente['sha256']!=huella:
            raise ValueError('El lector no confirmó la firma y huella de la fuente.')
        if esperado and (tuple(fuente['firma'])!=tuple(esperado['firma']) or
                         esperado.get('hash') and huella!=esperado['hash'] or
                         aislado['limite_as_mib']>esperado['mb_proceso']):
            raise ValueError('La comprobación final no corresponde a la fuente y recursos autorizados.')
        for k in _METADATOS:item.pop(k,None)
        item.update(meta)
        item['cortado']=bool(meta.get('cortado',False))
        item.setdefault('aviso','')
        item.setdefault('paginas',None)
        return tipo,None
    if tipo=='error':
        from conversaciones_jarvis import _redactar
        mensaje=_redactar(str(d.get('mensaje','Error no especificado.')))[:1200]
        if d.get('fase')=='memoria':raise MemoryError(mensaje)
        if d.get('fase')=='plazo':raise TimeoutError(mensaje)
        raise ValueError(mensaje)
    if tipo=='analisis':
        resultado=d.get('resultado')
        if not isinstance(resultado,dict) or len(json.dumps(resultado,ensure_ascii=False,separators=(',',':')).encode())>MAX_RESULTADO:
            raise ValueError('El análisis excede el límite de resultado del protocolo.')
        item['_resultado_analisis']=resultado
        return tipo,None
    raise ValueError('Mensaje del lector aislado desconocido.')


def _intercambiar(item,limites,control=None,recursos=None,operacion='unidades',opciones=None):
    """Produce (referencia,texto), sin acumular toda la salida en el padre.

    Los metadatos autorizados se incorporan a ``item`` al finalizar. Una salida
    parcial, muerte del lector, cancelación o límite alcanzado produce error;
    quien indexa decide conservar trozos previos y continuar con otra fuente.
    Cerrar el generador también termina su grupo de procesos.
    """
    import herramientas_lectura as L
    r=validar_recursos(recursos)
    entrada=_preparar(item,limites,r,operacion,opciones)
    solicitud=json.loads(entrada)
    esperado={'firma':solicitud['firma_esperada'],'hash':solicitud['item'].get('hash'),
              'ruta':solicitud['item']['ruta'],'mb_proceso':r['mb_proceso']}
    if control:control()
    if os.name!='posix':raise ValueError('El límite de memoria de este lector requiere Linux/POSIX; no se ejecutó sin protección.')
    inicio=time.monotonic();fin=inicio+r['segundos_archivo'];completo=False
    proceso=subprocess.Popen(_comando_worker(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL,bufsize=0,start_new_session=True,env=_entorno_worker())
    try:
        os.set_blocking(proceso.stdin.fileno(),False)
        os.set_blocking(proceso.stdout.fileno(),False)
        pendiente=memoryview(entrada);buffer=bytearray();final_recibido=False;resultado_recibido=False
        with selectors.DefaultSelector() as selector:
            selector.register(proceso.stdin,selectors.EVENT_WRITE,'entrada')
            selector.register(proceso.stdout,selectors.EVENT_READ,'salida')
            while selector.get_map():
                if control:control()
                restante=fin-time.monotonic()
                if restante<=0:raise TimeoutError('La extracción aislada alcanzó su plazo; se detuvo solo su proceso y descendientes.')
                for clave,_ in selector.select(min(.05,restante)):
                    if clave.data=='entrada':
                        try:n=os.write(proceso.stdin.fileno(),pendiente)
                        except BrokenPipeError:
                            selector.unregister(proceso.stdin);proceso.stdin.close();continue
                        pendiente=pendiente[n:]
                        if not pendiente:selector.unregister(proceso.stdin);proceso.stdin.close()
                        continue
                    bloque=os.read(proceso.stdout.fileno(),32768)
                    if not bloque:
                        selector.unregister(proceso.stdout)
                        if buffer:raise ValueError('El lector aislado terminó con un mensaje incompleto.')
                        continue
                    buffer.extend(bloque)
                    while b'\n' in buffer:
                        n=buffer.index(b'\n')
                        if n>MAX_LINEA:raise ValueError('El lector aislado excedió el límite de su salida.')
                        linea=bytes(buffer[:n]);del buffer[:n+1]
                        if final_recibido:raise ValueError('El lector aislado emitió datos después de finalizar.')
                        tipo,unidad=_recibir(linea,item,esperado)
                        if tipo=='unidad':
                            if operacion!='unidades':raise ValueError('El análisis emitió una unidad de otro tipo de operación.')
                            yield unidad
                        elif tipo=='analisis':
                            if operacion!='analizar' or resultado_recibido:raise ValueError('Resultado de análisis repetido o inesperado.')
                            resultado_recibido=True
                        else:final_recibido=True
                    if len(buffer)>MAX_LINEA:raise ValueError('El lector aislado excedió el límite de su salida.')
        restante=max(.01,fin-time.monotonic())
        try:codigo=proceso.wait(timeout=min(1,restante))
        except subprocess.TimeoutExpired:raise TimeoutError('El lector no terminó después de entregar su salida.')
        if not final_recibido or codigo or operacion=='analizar' and not resultado_recibido:
            raise ValueError('El lector terminó sin una comprobación final válida. Puede haber alcanzado memoria, CPU o un error de parser; no se afirmó lectura completa.')
        final=L._resolver(item['ruta'])
        if str(final)!=esperado['ruta'] or _firma(final)!=tuple(esperado['firma']):
            raise ValueError('La fuente cambió o dejó de estar autorizada antes de aceptar el resultado final.')
        completo=True
        item.pop('aislado_incompleto',None)
    finally:
        _terminar(proceso)
        if not completo:
            item['aislado_incompleto']=True
            item['cortado']=True
            item.pop('_resultado_analisis',None)


def unidades(item,limites,control=None,recursos=None):
    """Unidades de texto acotadas; actualiza metadatos de ``item`` al terminar."""
    yield from _intercambiar(item,limites,control,recursos)


def _validar_opciones_analisis(opciones):
    if not isinstance(opciones,dict) or set(opciones)!={'desde','hasta','buscar'}:
        raise ValueError('Opciones de análisis desconocidas.')
    desde,hasta=opciones['desde'],opciones['hasta']
    if type(desde) is not int or type(hasta) is not int or not 1<=desde<=hasta or hasta-desde>1999:
        raise ValueError('Elige hasta 2000 líneas, empezando en 1.')
    if not isinstance(opciones['buscar'],str) or len(opciones['buscar'])>200:
        raise ValueError('Búsqueda literal de hasta 200 caracteres.')


def analizar(ruta,*,control=None,recursos=None,desde=1,hasta=10,buscar=''):
    """Estadísticas aisladas hasta 500 MiB, separadas del índice de 20 MiB.

    No envía ni conserva el archivo en un modelo. El resultado puede ser parcial
    por límites del lector, plazo o recorte declarado del JSON de salida.
    """
    import tandas_documentales as T
    item={'ruta':str(ruta)}
    opciones={'desde':desde,'hasta':hasta,'buscar':buscar}
    for _ in _intercambiar(item,T.DEFAULT,control,recursos,'analizar',opciones):
        raise ValueError('Se recibió texto de otra operación durante un análisis.')
    resultado=item.pop('_resultado_analisis')
    resultado['aislamiento']=item['aislamiento']
    resultado['sha256_aislado']=item['sha256_aislado']
    if len(json.dumps(resultado,ensure_ascii=False,separators=(',',':')).encode())>MAX_RESULTADO:
        resultado=_acotar_resultado(resultado)
    return resultado


def _emitir(dato):
    dato=dict(dato,protocolo=PROTOCOLO)
    texto=json.dumps(dato,ensure_ascii=False,separators=(',',':')).encode()+b'\n'
    if len(texto)>MAX_LINEA:raise ValueError('Un mensaje del lector supera el protocolo acotado.')
    sys.stdout.buffer.write(texto);sys.stdout.buffer.flush()


def _limpiar_meta(valor,profundidad=0,recortes=None):
    from conversaciones_jarvis import _redactar
    if profundidad>6:
        if recortes is not None:recortes.append('profundidad')
        return '[METADATOS PROFUNDOS OMITIDOS]'
    if isinstance(valor,str):
        if len(valor)>4096 and recortes is not None:recortes.append('texto')
        return _redactar(valor)[:4096]
    if type(valor) in {int,bool} or valor is None:return valor
    if isinstance(valor,float):return valor if math.isfinite(valor) else None
    if isinstance(valor,list):
        if len(valor)>1000 and recortes is not None:recortes.append('lista')
        return [_limpiar_meta(v,profundidad+1,recortes) for v in valor[:1000]]
    if isinstance(valor,dict):
        import re
        if len(valor)>1000 and recortes is not None:recortes.append('diccionario')
        return {str(k)[:100]:('[REDACTADO]' if re.search(r'(?i)(?:api.?key|token|password|secret|credential)',str(k)) else _limpiar_meta(v,profundidad+1,recortes)) for k,v in list(valor.items())[:1000]}
    return '[METADATO NO REPRESENTABLE]'


def _acotar_resultado(resultado):
    recortes=[];r=_limpiar_meta(resultado,recortes=recortes)
    if not isinstance(r,dict):raise ValueError('El lector no entregó estadísticas estructuradas.')
    def tam():return len(json.dumps(r,ensure_ascii=False,separators=(',',':')).encode())
    campos=[]
    if tam()>MAX_RESULTADO:
        preservar={'archivo','tipo_real','bytes','sha256','sha256_aislado','segundos','indexado','completo','soporte','aviso','aislamiento'}
        grandes=sorted((k for k in r if k not in preservar),key=lambda k:len(json.dumps(r[k],ensure_ascii=False).encode()),reverse=True)
        for k in grandes:
            campos.append(k);r.pop(k)
            if tam()<=MAX_RESULTADO-2048:break
    if recortes or campos:
        r['resultado_recortado']=True;r['completo']=False;r['campos_omitidos']=campos[:100]
        r['aviso']=str(r.get('aviso',''))[:2000]+' Resultado JSON acotado: se omitieron campos o detalles extensos; no se afirmó cobertura completa.'
    if tam()>MAX_RESULTADO:raise ValueError('Las estadísticas no caben en el protocolo acotado.')
    return r


def _trozos(texto,referencia):
    # El texto YA está redactado; este corte nunca divide una clave sin filtrar.
    import re
    m=re.search(r' · desde línea (\d+)$',referencia)
    base=referencia[:m.start()] if m else referencia
    linea=int(m[1]) if m else None;columna=1;i=0;fragmento=0
    while i<len(texto):
        n=min(len(texto),i+MAX_TEXTO//4)
        if n<len(texto):
            corte=texto.rfind('\n',i,n)
            if corte>=i:n=corte+1
        t=texto[i:n];fragmento+=1
        if len(t.encode())>MAX_TEXTO:raise ValueError('Unidad Unicode fuera de límite.')
        if linea is not None:
            prefijo=base+(f' · continuación desde carácter {columna}' if columna!=1 else '')
            ref=prefijo+f' · desde línea {linea}'
        else:ref=referencia+(f' · fragmento {fragmento}, desde carácter {i+1}' if i or n<len(texto) else '')
        yield ref,t
        saltos=t.count('\n')
        if linea is not None:linea+=saltos
        columna=len(t.rsplit('\n',1)[-1])+1 if saltos else columna+len(t)
        i=n


def _huella(p,control):
    import hashlib
    h=hashlib.sha256()
    with p.open('rb') as f:
        while True:
            control();b=f.read(1024**2)
            if not b:return h.hexdigest()
            h.update(b)


def _firma(p):
    s=p.stat();return s.st_size,s.st_mtime_ns,s.st_ino


def _worker():
    reserva=None
    try:
        raw=sys.stdin.buffer.readline(MAX_ENTRADA+1)
        if len(raw)>MAX_ENTRADA or not raw.endswith(b'\n'):raise ValueError('Solicitud de lector aislado fuera de límite.')
        dato=json.loads(raw)
        if not isinstance(dato,dict) or dato.get('protocolo')!=PROTOCOLO:raise ValueError('Protocolo de entrada inválido.')
        recursos=validar_recursos(dato.get('recursos'))
        cap=_limitar(recursos)
        reserva=bytearray(131072) # Permite comunicar un MemoryError sin un traceback privado.
        import resource
        import herramientas_lectura as L
        import tandas_documentales as T
        from conversaciones_jarvis import _redactar
        item=dato['item'];limites=T.validar_limites(dato['limites']);operacion=dato.get('operacion','unidades')
        if operacion not in {'unidades','analizar'}:raise ValueError('Operación de lectura desconocida.')
        opciones=dato.get('opciones',{})
        if operacion=='analizar':_validar_opciones_analisis(opciones)
        p=L._resolver(item['ruta'])
        max_bytes=500*1024**2 if operacion=='analizar' else limites['mb_archivo']*1024**2
        if not p.is_file() or p.stat().st_size>max_bytes:
            raise ValueError('Fuente ausente o superior al límite autorizado.')
        inicio=time.monotonic();fin=inicio+recursos['segundos_archivo']
        def control():
            if time.monotonic()>=fin:raise TimeoutError('Plazo del lector aislado alcanzado.')
        # Los parsers XML reciben además un buffer estructural de hasta 8 MiB.
        T.recursos=lambda:dict(recursos,mb_buffer=min(8,recursos['mb_buffer']))
        antes=_firma(p)
        if list(antes)!=dato.get('firma_esperada'):raise ValueError('La fuente cambió antes de iniciar el parser.')
        sha=_huella(p,control)
        if item.get('hash') and item['hash']!=sha:raise ValueError('La huella de la fuente cambió antes de extraerla.')
        selector=item.get('_pagina_documento');resultado=None
        if operacion=='analizar':
            if selector is not None:raise ValueError('El selector de página no forma parte del análisis estadístico.')
            import lectores_adjuntos as R
            resultado=_acotar_resultado(R.analizar(p,recursos=recursos,**opciones));control()
            for k in ('tipo_real','soporte','aviso','codificacion'):
                if k in resultado:item[k]=resultado[k]
            lector=iter(())
        elif selector is not None:
            if type(selector) is not int or not 1<=selector<=1_000_000 or item.get('miembro'):
                raise ValueError('Selector interno de página inválido.')
            import lectores_adjuntos as R
            ext,aviso=R.detectar(p,item['tipo'])
            if ext!='.pdf':raise ValueError('El selector de página requiere un PDF real.')
            from documentos_jarvis import _pdf
            def una_pagina():
                control();texto,total,cortado=_pdf(p,selector);control()
                item.update(tipo_real='.pdf',soporte='PARCIAL',paginas=total,paginas_leidas=selector,
                            paginas_extraidas=1,cortado=bool(cortado),aviso=aviso)
                if not texto.strip():item['aviso']=R.combinar(aviso,'Esta página no tiene texto extraíble. Puede ser una imagen escaneada; no hice OCR.')
                yield item['nombre']+f' · página {selector}',texto
            lector=una_pagina()
        else:lector=T._unidades(item,limites,control)
        privada=False
        import re
        for ref,texto in lector:
            control()
            if not isinstance(ref,str) or not isinstance(texto,str):raise ValueError('El parser no entregó una unidad textual.')
            if len(texto)>8*1024**2:raise ValueError('Una unidad del parser supera el máximo estructural de 8 MiB.')
            if privada:
                m=re.search(r'-----END [^-]*PRIVATE KEY-----',texto)
                if m:texto=texto[m.end():];privada=False
                else:texto=''
            m=re.search(r'-----BEGIN [^-]*PRIVATE KEY-----',texto)
            if m and not re.search(r'-----END [^-]*PRIVATE KEY-----',texto[m.end():]):
                texto=texto[:m.start()]+'[CLAVE PRIVADA REDACTADA]';privada=True
            texto=_redactar(texto);ref=_redactar(ref)
            if len(ref.encode())>MAX_REF:raise ValueError('Referencia demasiado extensa para el protocolo.')
            avance={k:item[k] for k in _AVANCE if type(item.get(k)) is int and item[k]>=0}
            for cita,t in _trozos(texto,ref):_emitir({'tipo':'unidad','referencia':cita,'texto':t,'avance':avance})
        control()
        final=L._resolver(item['ruta'])
        if final!=p or _firma(p)!=antes or _huella(p,control)!=sha:
            raise ValueError('La fuente cambió durante la extracción; no se afirmó lectura completa.')
        meta={k:_limpiar_meta(item[k]) for k in _METADATOS if k in item}
        meta['sha256_aislado']=sha
        meta['aislamiento']={'limite_as_mib':cap//1024**2,'rss_max_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                            'segundos_worker':round(time.monotonic()-inicio,4),'alcance':'Memoria virtual por proceso; no RSS ni total del árbol.'}
        if len(json.dumps(meta,ensure_ascii=False).encode())>MAX_META:
            meta.pop('hojas',None);meta['aviso']=str(meta.get('aviso',''))[:2000]+' Metadatos de hojas omitidos por tamaño del protocolo.'
        if resultado is not None:_emitir({'tipo':'analisis','resultado':resultado})
        _emitir({'tipo':'fin','metadatos':meta,'fuente':{'firma':antes,'sha256':sha}})
        return 0
    except MemoryError:
        reserva=None
        _emitir({'tipo':'error','fase':'memoria','mensaje':'El parser alcanzó su techo de memoria virtual. Se detuvo la lectura; no se afirmó que el archivo estuviera completo.'})
        return 2
    except BaseException as e:
        reserva=None
        try:
            from errores_adjuntos import explicar
            fuente=locals().get('item',{})
            mensaje=explicar(e,fuente.get('tipo_real',fuente.get('tipo','')) if isinstance(fuente,dict) else '')
        except BaseException:mensaje='El parser no pudo completar una lectura segura.'
        _emitir({'tipo':'error','fase':'plazo' if isinstance(e,TimeoutError) else 'lectura','mensaje':mensaje})
        return 2


if __name__=='__main__':
    # La única ruta importable bajo -I es el directorio de código de Jarvis.
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    if sys.argv[1:]!=['--worker']:raise SystemExit('Uso interno del lector aislado.')
    raise SystemExit(_worker())
