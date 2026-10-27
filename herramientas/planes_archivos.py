"""Planes acotados de archivos: vista previa, un permiso y comprobación por paso.

La autorización vive en un ContextVar, nunca en texto del modelo o estado
persistido. Solo permite los argumentos exactos del paso en ejecución.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import difflib
import hashlib
import re
import shlex
import herramientas_lectura as L
import herramientas_escritura as E
from interfaz_archivos import acceso_natural,renderizar_archivos
import ordenes_compuestas as ORD

_ACTIVO=ContextVar('plan_archivos_activo',default=None)


def huella(p):
    if not p.exists():return None
    if p.is_dir():return {'tipo':'carpeta'}
    if not p.is_file():raise ValueError('Ruta no regular: '+str(p))
    return {'tipo':'archivo','sha256':E._hash_archivo(p),'bytes':p.stat().st_size}


def validar_hash(p,sha):
    activo=_ACTIVO.get()
    if activo:
        esperada=activo['antes'].get(str(p))
        if esperada and esperada.get('sha256')!=sha:raise ValueError('El archivo cambió después del permiso del plan; no se escribió.')


def comprobar_paso(paso):
    for p,esperada in paso['antes'].items():
        if huella(L._resolver(p))!=esperada:raise ValueError('Una ruta cambió después de mostrar el plan: '+p)


def permiso_paso(nombre,args):
    activo=_ACTIVO.get()
    if activo is None:return False
    if activo.get('consumido') or activo['nombre']!=nombre or activo['args']!=args:
        raise ValueError('La acción no coincide con el paso autorizado del plan.')
    comprobar_paso(activo)
    activo['consumido']=True
    return True


@contextmanager
def autorizacion(paso):
    token=_ACTIVO.set(dict(paso,consumido=False))
    try:yield
    finally:_ACTIVO.reset(token)


def interpretar(texto,anterior):
    texto=re.sub(r'(?i)^renombra la copia\s+', 'renómbralo ',texto)
    texto=ORD.referencia_archivo(texto,anterior)
    acceso=texto if texto.startswith('/') else acceso_natural(texto)
    if not acceso:raise ValueError('Paso ambiguo: «'+texto+'». Indica archivo, operación y destino exactos.')
    p=shlex.split(acceso);a=p[0].casefold()
    if a in {'/copiar','/mover','/renombrar'} and len(p)==3:
        return ('copiar_archivo' if a=='/copiar' else 'mover_archivo'),{'origen':p[1],'destino':p[2]}
    if a=='/carpeta' and len(p)==2:return 'crear_carpeta',{'ruta':p[1]}
    if a=='/reemplazar' and (len(p)==4 or (len(p)==5 and p[4]=='--todos')):
        return 'reemplazar_texto',{'ruta':p[1],'texto_actual':p[2],'texto_nuevo':p[3],'todas':len(p)==5}
    if a=='/leer' and len(p)==2:return 'leer_archivo',{'ruta':p[1]}
    raise ValueError('Paso sin plan seguro: «'+texto+'». Usa copiar, mover, crear carpeta, leer o /reemplazar con rutas exactas.')


def preparar(partes):
    virtual={};contenidos={};pasos=[];anterior=None
    def estado(p):
        k=str(p)
        if k not in virtual:virtual[k]=huella(p)
        return virtual[k]
    def texto(p):
        if str(p) in contenidos:return contenidos[str(p)]
        if estado(p)['bytes']>E.MAX_BYTES_ESCRIBIR:raise ValueError('Para mostrar el diff completo del plan, el texto debe tener como máximo 100 KB. Usa la operación individual para archivos mayores.')
        t=p.read_bytes().decode('utf-8');contenidos[str(p)]=t;return t
    for i,t in enumerate(partes,1):
        try:
            nombre,args=interpretar(t,anterior);args=dict(args);antes={};despues={};diff=''
            if nombre in {'copiar_archivo','mover_archivo'}:
                origen=L._resolver(args['origen']);destino=L._resolver(args['destino'])
                src=estado(origen)
                if not src or src['tipo']!='archivo':raise ValueError('El origen no es un archivo: '+args['origen'])
                if estado(destino)=={'tipo':'carpeta'}:destino=destino/origen.name
                if estado(destino) is not None:raise ValueError('El destino ya existe: '+str(destino))
                if estado(destino.parent)!={'tipo':'carpeta'}:raise ValueError('La carpeta destino no existe; añade primero su creación al plan: '+str(destino.parent))
                antes={str(origen):dict(src),str(destino):None,str(destino.parent):{'tipo':'carpeta'}}
                args={'origen':str(origen),'destino':str(destino)};contenido=texto(origen)
                diff=''.join(difflib.unified_diff([] if nombre=='copiar_archivo' else contenido.splitlines(True),contenido.splitlines(True),fromfile='/dev/null' if nombre=='copiar_archivo' else str(origen),tofile=str(destino)))
                if not diff:diff=f'--- {origen}\n+++ {destino}\nContenido sin cambios (SHA256 {src["sha256"]}).'
                virtual[str(destino)]=dict(src);contenidos[str(destino)]=contenido;despues[str(destino)]=dict(src)
                if nombre=='mover_archivo':virtual[str(origen)]=None;despues[str(origen)]=None
                anterior=str(destino)
            elif nombre=='crear_carpeta':
                p=L._resolver(args['ruta'])
                if estado(p) is not None:raise ValueError('La ruta ya existe: '+str(p))
                if estado(p.parent)!={'tipo':'carpeta'}:raise ValueError('Primero crea la carpeta padre.')
                antes={str(p):None,str(p.parent):{'tipo':'carpeta'}};args={'ruta':str(p)}
                virtual[str(p)]={'tipo':'carpeta'};despues[str(p)]={'tipo':'carpeta'};diff='+ carpeta '+str(p);anterior=None
            elif nombre=='reemplazar_texto':
                p=L._resolver(args['ruta']);v=estado(p)
                if not v or v['tipo']!='archivo':raise ValueError('No encontré el archivo a editar.')
                viejo=texto(p);actual=args['texto_actual'];veces=viejo.count(actual)
                if not actual or not veces or (veces>1 and not args['todas']):raise ValueError('El reemplazo no es inequívoco; indica el texto exacto o --todos.')
                nuevo=viejo.replace(actual,args['texto_nuevo'],-1 if args['todas'] else 1)
                if len(nuevo.encode())>E.MAX_BYTES_ESCRIBIR or nuevo==viejo:raise ValueError('Edición sin cambio o demasiado grande.')
                antes={str(p):dict(v)};args['ruta']=str(p)
                diff=''.join(difflib.unified_diff(viejo.splitlines(True),nuevo.splitlines(True),fromfile=str(p)+' (actual)',tofile=str(p)+' (propuesto)'))
                virtual[str(p)]={'tipo':'archivo','sha256':hashlib.sha256(nuevo.encode()).hexdigest(),'bytes':len(nuevo.encode())};contenidos[str(p)]=nuevo;despues[str(p)]=dict(virtual[str(p)]);anterior=None
            else:
                p=L._resolver(args['ruta']);v=estado(p)
                if not v or v['tipo']!='archivo':raise ValueError('No encontré el archivo a leer.')
                antes={str(p):dict(v)};args={'ruta':str(p)};diff='Lectura sin escritura: '+str(p);anterior=None
            if len(diff)>20000:raise ValueError('El diff completo supera 20.000 caracteres; divide el plan para revisarlo sin recortes.')
            pasos.append({'nombre':nombre,'args':args,'antes':antes,'despues':despues,'diff':diff})
        except (OSError,ValueError) as e:raise ValueError(f'Paso {i}: {e}. No ejecuté ningún paso.') from e
    return pasos


def ejecutar(partes,accion,confirmar,estado):
    try:pasos=preparar(partes)
    except (OSError,ValueError) as e:return 'Me detuve al preparar el plan. '+str(e)
    vista='Plan de '+str(len(pasos))+' pasos. Un permiso para este plan exacto; me detendré si falla una comprobación.\n\n'+'\n\n'.join(f'{i}. {p["nombre"]}: {p["args"]}\n{p["diff"]}' for i,p in enumerate(pasos,1))
    if not confirmar(vista):return 'Plan sin autorizar. No ejecuté ningún paso.'
    cambios=[];resultados=[];estado['_ultimo_plan_archivos']={'cambios':cambios}
    for i,p in enumerate(pasos,1):
        try:
            comprobar_paso(p)
            with autorizacion(p):r=accion(p['nombre'],p['args'])
            if r.get('id_cambio'):cambios.append(r['id_cambio'])
            if not r.get('ok') or (p['nombre']!='leer_archivo' and not r.get('verificado')):raise ValueError(r.get('error','El controlador no comprobó la escritura.'))
            for ruta,esperada in p['despues'].items():
                if huella(L._resolver(ruta))!=esperada:raise ValueError('El resultado real no coincide con el plan autorizado.')
            resultados.append(f'Paso {i} comprobado: '+renderizar_archivos(p['nombre'],r))
        except (OSError,ValueError) as e:
            resultados.append(f'Paso {i} falló: {e}. Me detuve; no ejecuté los pasos posteriores.')
            break
    if cambios:resultados.append('Cambios registrados: '+str(len(cambios))+'. Puedes usar /deshacer_plan para revisar y deshacer en orden inverso con un nuevo permiso. Si cambió un archivo, se detendrá.')
    return '\n\n'.join(resultados)


def deshacer(accion,confirmar,estado):
    ids=estado.get('_ultimo_plan_archivos',{}).get('cambios',[])
    if not ids:return 'No hay cambios de un plan en esta conversación.'
    # La reversión comprueba hashes y no sobrescribe rutas; autorización nueva
    # limitada a los IDs inmutables de este plan, sin autorización persistente.
    vistas=[]
    for ident in reversed(ids):
        try:
            c=E._cargar_json(E.CAMBIOS,ident)
            vistas.append(ident+': '+c['tipo']+' · '+c['ruta']+(' → '+c['origen'] if c.get('origen') else '')+' · SHA256 esperado '+str(c.get('hash_despues','carpeta vacía')))
        except (OSError,ValueError,KeyError):return 'No pude revisar uno de los registros del plan; no deshice cambios.'
    if not confirmar('Deshacer estos cambios del último plan, en orden inverso:\n'+'\n'.join(vistas)+'\nSe detendrá si una ruta cambió o una carpeta contiene archivos.'):return 'No deshice el plan.'
    resultados=[]
    for ident in list(reversed(ids)):
        paso={'nombre':'revertir_cambio','args':{'id_cambio':ident},'antes':{}}
        with autorizacion(paso):r=accion(paso['nombre'],paso['args'])
        if not r.get('ok') or not r.get('verificado'):
            resultados.append('Me detuve: '+r.get('error','Reversión sin comprobar.'));break
        ids.remove(ident)
        registro=E._cargar_json(E.CAMBIOS,ident)
        resultados.append('Cambio deshecho y comprobado: '+registro['ruta']+(' → '+registro['origen'] if registro.get('origen') else '')+' ('+registro['tipo']+').')
    return '\n'.join(resultados)
