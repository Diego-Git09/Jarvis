"""Respaldos explícitos de una lista cerrada. Nunca recorre credenciales."""
import base64, fcntl, hashlib, json, os, re, uuid
from datetime import datetime,timezone
from entorno_jarvis import DATOS
from conversaciones_jarvis import _atomic,_redactar

PERMITIDOS={'configuracion.json','vocabulario_privado.json','confirmaciones_vocabulario.json','revision_respuestas.json','umbrales_temperatura.json'}
MAXIMO=2_500_000
class ErrorRestauracion(ValueError):pass
def _ruta(p):
    if p.is_symlink() or any(x.is_symlink() for x in p.parents):raise ValueError('Ruta con enlace; no se usa')
def _leer(p):
    _ruta(p)
    try:
        if p.stat().st_size>MAXIMO:raise ValueError('Archivo demasiado grande')
        return p.read_bytes()
    except FileNotFoundError:return None
def _sha(b):return hashlib.sha256(b).hexdigest() if b is not None else 'ausente'
def _validar(nombre,b):
    if nombre not in PERMITIDOS or len(b)>MAXIMO:raise ValueError('Archivo fuera de la lista permitida')
    texto=b.decode('utf-8');d=json.loads(texto)
    if _redactar(texto)!=texto or re.search(r'"(?:api[_-]?key|password|passwd|secret|authorization|token|clave)"\s*:',texto,re.I):raise ValueError('Se detectaron posibles credenciales; no se copia ni restaura')
    if nombre=='configuracion.json':
        import configuracion_jarvis as C
        C.validar(d)
    elif nombre=='vocabulario_privado.json':
        import vocabulario_privado as V
        if not isinstance(d,dict) or len(d)>500:raise ValueError('Vocabulario inválido')
        for k,v in d.items():V.validar(k,v)
    elif nombre=='umbrales_temperatura.json':
        if not isinstance(d,dict) or set(d)!={'gpu','cpu'} or any(type(v) is not int or not 50<=v<=100 for v in d.values()):raise ValueError('Umbrales inválidos')
    elif nombre=='confirmaciones_vocabulario.json':
        if not isinstance(d,dict) or any(not isinstance(k,str) or not isinstance(v,dict) or v.get('estado') not in {'observado','pasivo'} for k,v in d.items()):raise ValueError('Confirmaciones inválidas')
    elif not isinstance(d,dict) or d.get('version')!=1 or not isinstance(d.get('marcas'),dict):raise ValueError('Marcas inválidas')
    return b
def _actuales():
    resultado={}
    for n in sorted(PERMITIDOS):
        b=_leer(DATOS/n)
        if b is not None:resultado[n]=_validar(n,b)
    return resultado
def _guardar(copias):
    ident=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:12]
    p=DATOS/'respaldos'/('respaldo_'+ident+'.json');_ruta(p)
    d={'version':1,'fecha':datetime.now(timezone.utc).isoformat(),'archivos':{n:{'sha256':_sha(b),'base64':base64.b64encode(b).decode()} for n,b in copias.items()}}
    _atomic(p,d)
    if _cargar(ident)!=copias:raise ValueError('No se pudo comprobar el respaldo')
    return ident
def _cargar(ident):
    if not re.fullmatch(r'\d{8}T\d{6}_[a-f0-9]{12}',ident):raise ValueError('ID de respaldo inválido; usa /respaldo listar')
    p=DATOS/'respaldos'/('respaldo_'+ident+'.json');_ruta(p)
    if p.stat().st_size>20_000_000:raise ValueError('Respaldo demasiado grande')
    d=json.loads(p.read_text())
    if not isinstance(d,dict) or set(d)!={'version','fecha','archivos'} or d['version']!=1 or not isinstance(d['archivos'],dict) or not d['archivos']:raise ValueError('Respaldo inválido')
    salida={}
    for n,v in d['archivos'].items():
        if n not in PERMITIDOS or not isinstance(v,dict) or set(v)!={'sha256','base64'}:raise ValueError('Contenido no permitido en el respaldo')
        b=base64.b64decode(v['base64'],validate=True)
        if _sha(b)!=v['sha256']:raise ValueError('Huella de respaldo incorrecta')
        salida[n]=_validar(n,b)
    return salida
def crear(confirmar):
    copias=_actuales()
    if not copias:return 'No hay archivos de configuración para respaldar.'
    if not confirmar('Crear respaldo privado de:\n'+'\n'.join(f'{n}: {len(b)} bytes, SHA256 {_sha(b)}' for n,b in copias.items())+'\nSe excluyen claves, conversaciones, originales privados, adjuntos y credenciales. ¿Crear?'):return 'Respaldo cancelado.'
    if _actuales()!=copias:raise ValueError('La configuración cambió; vuelve a pedir el respaldo')
    return 'Respaldo creado y verificado, permisos 600: '+_guardar(copias)
def listar():
    p=DATOS/'respaldos';_ruta(p)
    archivos=sorted(p.glob('respaldo_*.json'),reverse=True)
    lineas=[]
    for a in archivos[:100]:
        ident=a.stem.removeprefix('respaldo_')
        try:d=_cargar(ident);lineas.append(ident+' · '+str(len(d))+' archivos verificados')
        except (OSError,ValueError,TypeError,KeyError):lineas.append(ident+' · inválido; no restaurar')
    return 'Respaldos locales (hasta 100 recientes):\n'+('\n'.join(lineas) or 'Todavía no hay respaldos.')
def restaurar(ident,confirmar):
    nuevo=_cargar(ident);antes={n:_leer(DATOS/n) for n in nuevo}
    for n,b in antes.items():
        if b is not None:_validar(n,b)
    cambios={n:b for n,b in nuevo.items() if b!=antes[n]}
    if not cambios:return 'La configuración ya coincide con ese respaldo. No se escribió nada.'
    vista='\n'.join(n+': '+_sha(antes[n])+' → '+_sha(b) for n,b in cambios.items())
    if not confirmar('Restaurar solo estos archivos:\n'+vista+'\nLos demás se conservan. Se crea respaldo previo de los archivos reemplazados. ¿Restaurar?'):return 'Restauración cancelada.'
    if _cargar(ident)!=nuevo or any(_leer(DATOS/n)!=b for n,b in antes.items()):raise ValueError('El respaldo o el destino cambió; vuelve a revisar')
    _ruta(DATOS);DATOS.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(DATOS/'respaldos.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        if any(_leer(DATOS/n)!=b for n,b in antes.items()):raise ValueError('Los archivos cambiaron antes de restaurar')
        previas={n:antes[n] for n in cambios if antes[n] is not None}
        previo=_guardar(previas) if previas else None;hechos=[]
        try:
            for n,b in cambios.items():
                # La escritura atómica conserva el JSON original, incluido su formato.
                _escribir_bytes(DATOS/n,b);hechos.append(n)
                if _leer(DATOS/n)!=b:raise ValueError('La comprobación no coincidió')
        except (OSError,ValueError):
            pendientes=[]
            for n in reversed(hechos):
                try:
                    if _leer(DATOS/n)!=cambios[n]:pendientes.append(n);continue
                    if antes[n] is None:(DATOS/n).unlink()
                    else:_escribir_bytes(DATOS/n,antes[n])
                except (OSError,ValueError):pendientes.append(n)
            raise ErrorRestauracion('Restauración detenida; se revirtieron las escrituras propias comprobables. Respaldo previo: '+str(previo)+'. Revisión manual: '+(', '.join(pendientes) or 'ninguna'))
    return 'Restauración verificada por SHA256 de '+str(len(cambios))+' archivos, permisos 600. Respaldo previo: '+str(previo)+'. Reinicia Jarvis para cargar toda la configuración restaurada.'
def _escribir_bytes(p,b):
    import tempfile
    _ruta(p);fd,tmp=tempfile.mkstemp(prefix='.restaurar-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def comando(p,confirmar):
    if not re.match(r'^/respaldo(?:\s|$)',p.strip(),re.I):return False,''
    partes=p.strip().split()
    try:
        if partes==['/respaldo','crear']:return True,crear(confirmar)
        if partes==['/respaldo','listar']:return True,listar()
        if len(partes)==3 and partes[:2]==['/respaldo','restaurar']:return True,restaurar(partes[2],confirmar)
        return True,'1. /respaldo crear pide s/n.\n2. /respaldo listar muestra los ID.\n3. /respaldo restaurar ID muestra cambios y pide s/n. Excluye claves y conversaciones.'
    except ErrorRestauracion as e:return True,str(e)
    except (OSError,ValueError,TypeError,KeyError):return True,'No pude completar el respaldo o la restauración. No se autorizan archivos fuera de la lista ni datos con posibles credenciales. Revisa el archivo elegido y vuelve a intentarlo.'
