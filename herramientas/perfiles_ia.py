"""Perfiles persistentes sin secretos en JSON; claves en el llavero de GNOME."""
import json
import os
import tempfile
import threading
import uuid
from entorno_jarvis import DATOS, en_pruebas

ARCHIVO=DATOS/'perfiles_ia.json'
LOCK=threading.RLock()
PRESETS={
    'OpenAI':{'protocolo':'OpenAI','url':'https://api.openai.com/v1/chat/completions','claves':'https://platform.openai.com/api-keys'},
    'Anthropic':{'protocolo':'Anthropic','url':'https://api.anthropic.com/v1/messages','claves':'https://platform.claude.com/settings/keys'},
    'DeepSeek':{'protocolo':'Compatible','url':'https://api.deepseek.com/chat/completions','claves':'https://platform.deepseek.com/'},
    'Compatible':{'protocolo':'Compatible','url':'','claves':''},
}


def _secret(operacion,ident,clave=None):
    if en_pruebas():raise ValueError('El llavero real está desactivado en pruebas.')
    try:
        import gi
        gi.require_version('Secret','1')
        from gi.repository import Secret,Gio
        schema=Secret.Schema.new('org.jarvis.api',Secret.SchemaFlags.NONE,{'credencial':Secret.SchemaAttributeType.STRING})
        c=Gio.Cancellable();timer=threading.Timer(20,c.cancel);timer.daemon=True;timer.start()
        try:
            attrs={'credencial':ident}
            if operacion=='guardar':
                if not Secret.password_store_sync(schema,attrs,Secret.COLLECTION_DEFAULT,'Jarvis · clave API',clave,c):raise ValueError()
                return True
            if operacion=='leer':return Secret.password_lookup_sync(schema,attrs,c) or ''
            return Secret.password_clear_sync(schema,attrs,c)
        finally:timer.cancel()
    except Exception:
        raise ValueError('No pude acceder al llavero de GNOME. Desbloquea «Contraseñas y claves» y vuelve a intentar; no guardé la clave en texto plano.') from None


def leer():
    try:
        if ARCHIVO.stat().st_size>100000:raise ValueError()
        d=json.loads(ARCHIVO.read_text())
        if not isinstance(d,dict) or not isinstance(d.get('perfiles',{}),dict):raise ValueError()
        return d
    except FileNotFoundError:return {'perfiles':{},'preferido':'','automatico':False,'timeout_local':35}
    except (OSError,ValueError,TypeError):raise ValueError('No pude leer los perfiles de IA. No se sobrescribió su configuración.') from None


def _guardar(datos):
    ARCHIVO.parent.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(ARCHIVO.parent,0o700)
    fd,tmp=tempfile.mkstemp(prefix='.perfiles-',dir=ARCHIVO.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f:json.dump(datos,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,ARCHIVO)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def guardar_perfil(proveedor,url,modelo,clave='',preferido=False):
    import internet_jarvis as WEB
    import re
    if proveedor not in PRESETS:raise ValueError('Proveedor no admitido.')
    url=WEB.validar_url(url or PRESETS[proveedor]['url'])
    if proveedor!='Compatible' and url!=PRESETS[proveedor]['url']:raise ValueError('La dirección no corresponde al proveedor elegido.')
    if not isinstance(modelo,str) or not modelo.strip() or len(modelo)>100:raise ValueError('Selecciona un modelo de conversación.')
    if clave and (len(clave)>4096 or re.search(r'[\x00-\x20\x7f]',clave)):raise ValueError('Clave API no válida.')
    with LOCK:
        d=leer();anterior=d['perfiles'].get(proveedor,{})
        ref=anterior.get('credencial','')
        if not clave and (not ref or anterior.get('url')!=url):raise ValueError('Introduce la clave de este proveedor.')
        nuevo_ref=uuid.uuid4().hex if clave else ref
        if clave:_secret('guardar',nuevo_ref,clave)
        nuevo={'proveedor':proveedor,'url':url,'protocolo':PRESETS[proveedor]['protocolo'],'modelo':modelo.strip(),'credencial':nuevo_ref}
        if not clave and modelo.strip()==anterior.get('modelo'):nuevo.update({k:anterior[k] for k in ('verificado','ultimo_error') if k in anterior})
        d['perfiles'][proveedor]=nuevo
        if preferido or not d.get('preferido'):d['preferido']=proveedor
        try:_guardar(d)
        except Exception:
            if clave:
                try:_secret('borrar',nuevo_ref)
                except ValueError:pass
            raise
        if clave and ref:
            try:_secret('borrar',ref)
            except ValueError:pass
    return publico(nuevo)


def publico(p):
    return {k:v for k,v in p.items() if k!='credencial'}|{'clave_guardada':bool(p.get('credencial'))}


def listar():return [publico(p) for p in leer()['perfiles'].values() if p.get('proveedor') in PRESETS]


def configuracion(proveedor=''):
    d=leer();p=d['perfiles'].get(proveedor or d.get('preferido',''))
    if not p:return {}
    if p.get('proveedor') not in PRESETS:raise ValueError('Perfil no válido.')
    # Antes de recuperar una clave, verifica su destino conocido.
    if p['proveedor']!='Compatible' and p.get('url')!=PRESETS[p['proveedor']]['url']:raise ValueError('La dirección guardada no corresponde al proveedor.')
    return dict(p,clave=_secret('leer',p['credencial']))


def opciones():
    d=leer()
    return {'automatico':bool(d.get('automatico',False)),'timeout_local':int(d.get('timeout_local',35)),
            'preferido':d.get('preferido',''),'configurado':bool(d.get('perfiles',{}))}


def guardar_opciones(automatico,preferido='',timeout_local=35):
    if type(automatico) is not bool or type(timeout_local) is not int or not 15<=timeout_local<=120:raise ValueError('Opciones de respaldo no válidas.')
    with LOCK:
        d=leer()
        if preferido and preferido not in d['perfiles']:raise ValueError('Primero configura ese proveedor.')
        d.update(automatico=automatico,timeout_local=timeout_local)
        if preferido:d['preferido']=preferido
        _guardar(d)


def registrar_resultado(proveedor,ok,error=''):
    from datetime import datetime
    with LOCK:
        d=leer();p=d['perfiles'].get(proveedor)
        if not p:return
        if ok:p['verificado']=datetime.now().astimezone().isoformat(timespec='seconds');p.pop('ultimo_error',None)
        else:p['ultimo_error']=error[:700];p.pop('verificado',None)
        _guardar(d)


def eliminar(proveedor):
    with LOCK:
        d=leer();p=d['perfiles'].get(proveedor)
        if not p:return
        _secret('borrar',p['credencial']);d['perfiles'].pop(proveedor)
        if d.get('preferido')==proveedor:d['preferido']=next(iter(d['perfiles']),'')
        _guardar(d)
