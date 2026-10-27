"""Aplica únicamente propuestas revisadas, con permiso y contenido esperado."""
import hashlib
import json
import os
import re
import uuid
from entorno_jarvis import DATOS,REGISTROS
from conversaciones_jarvis import _atomic,_redactar

PROPUESTAS=REGISTROS/'reportes/ronda4_20261021'

def _segura(p):
    if p.is_symlink() or any(x.is_symlink() for x in p.parents):raise ValueError('La ruta contiene un enlace; no se limpia')

def _copia(p,contenido):
    _segura(p);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    for carpeta in (p.parent,*p.parent.parents):
        if carpeta==DATOS or DATOS in carpeta.parents:os.chmod(carpeta,0o700)
        if carpeta==DATOS:break
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(contenido);f.flush();os.fsync(f.fileno())
    if p.read_bytes()!=contenido:raise ValueError('No se comprobó el respaldo; no limpiar')

def apartar_hilos(confirmar):
    fuente=PROPUESTAS/'propuesta_hilos.json';_segura(fuente)
    d=json.loads(fuente.read_text());filas=[x for x in d['candidatos'] if x.get('elegible') is True]
    if not filas or len(filas)>100:raise ValueError('La propuesta de hilos no es válida')
    carpeta=DATOS/'hilos';_segura(carpeta);archivos=[]
    for x in filas:
        if not re.fullmatch(r'[a-f0-9]{32}',x.get('id_local','')):raise ValueError('ID local inválido')
        p=carpeta/(x['id_local']+'.json');_segura(p);bruto=p.read_bytes()
        if hashlib.sha256(bruto).hexdigest()!=x['sha256']:raise ValueError('Un hilo cambió desde la propuesta; volver a revisar antes de limpiar')
        archivos.append((p,bruto,x))
    if not confirmar(f"Apartar {len(archivos)} hilos locales de la propuesta revisada? Primero se copian y comprueban todos en un respaldo privado600 fuera de Git. No se borran recuerdos de Segundo Cerebro. Si el puntero último señala uno de estos hilos, se respalda y se deja sin selección automática."):
        return {'ok':False,'motivo':'Sin permiso; no se respaldó ni se apartó ningún hilo.'}
    respaldo=DATOS/'limpieza_r4'/uuid.uuid4().hex;_segura(respaldo)
    for p,bruto,_ in archivos:_copia(respaldo/p.name,bruto)
    ultimo=carpeta/'ultimo.json';puntero=None
    if ultimo.exists():
        _segura(ultimo);puntero=ultimo.read_bytes();_copia(respaldo/'ultimo.json',puntero)
    apartados=[];error=''
    for p,bruto,x in archivos:
        try:
            _segura(p)
            if p.read_bytes()!=bruto:raise ValueError('Un hilo cambió durante la limpieza')
            p.unlink();apartados.append(x['id_local'])
        except (OSError,ValueError) as e:error=type(e).__name__+'; se detuvo la limpieza y se conservó el respaldo';break
    puntero_retirado=False
    if not error and puntero is not None:
        _segura(ultimo)
        if ultimo.exists() and ultimo.read_bytes()==puntero and json.loads(puntero).get('id') in apartados:
            ultimo.unlink();puntero_retirado=True
    r={'ok':not error,'respaldo':str(respaldo),'apartados':apartados,'puntero_retirado':puntero_retirado,'error':error,'memorias_mcp_modificadas':0}
    _atomic(respaldo/'resultado.json',r);_atomic(PROPUESTAS/'limpieza_hilos_resultado.json',r)
    return r

def redactar_recuerdos(cliente,confirmar,copia_original=False):
    p=PROPUESTAS/'propuestas_redaccion_recuerdos.json';_segura(p);d=json.loads(p.read_text());plan=[]
    if sorted(x['id'] for x in d['propuestas'])!=[1009,1010,1011]:raise ValueError('La propuesta debe contener exactamente los tres IDs revisados')
    for x in d['propuestas']:
        ident=x['id']
        if ident not in {1009,1010,1011}:raise ValueError('ID fuera del plan revisado')
        filas=cliente.llamar('consultar_memoria',{'id_memoria':ident}).get('memorias',[])
        if len(filas)!=1:raise ValueError('Lectura no única')
        m=filas[0]
        if m.get('id')!=ident or m.get('proyecto')!=x['proyecto'] or hashlib.sha256(m['contenido'].encode()).hexdigest()!=x['sha256_esperado']:
            raise ValueError('El recuerdo cambió desde la propuesta; no se modifica')
        nuevo=x['contenido_propuesto'].strip()
        if nuevo!=_redactar(m['contenido']).strip():raise ValueError('La propuesta no coincide con la redacción de credenciales; no modificar otros datos')
        plan.append((m,nuevo))
    texto='Redactar solo las credenciales señaladas en las versiones revisadas de1009,1010 y1011? No se borran recuerdos. '+('Se conservarán originales privados600 fuera de Git porque lo solicitaste.' if copia_original else 'No se guardará una copia local de los originales con credenciales.')
    if not confirmar(texto):return {'ok':False,'motivo':'Sin permiso; recuerdos intactos.'}
    respaldo=None
    if copia_original:
        respaldo=DATOS/'originales_privados_r4'/uuid.uuid4().hex
        for m,_ in plan:_copia(respaldo/(str(m['id'])+'.txt'),m['contenido'].encode())
    verificados=[]
    for m,nuevo in plan:
        if nuevo!=m['contenido']:
            r=cliente.llamar('corregir_memoria',{'id_memoria':m['id'],'contenido_esperado':m['contenido'],'contenido_nuevo':nuevo})
            if not r.get('ok'):raise ValueError('No se confirmó la redacción; comprobar el estado antes de repetir')
        leido=cliente.llamar('consultar_memoria',{'id_memoria':m['id']}).get('memorias',[])
        if len(leido)!=1 or leido[0].get('id')!=m['id'] or leido[0].get('proyecto')!=m['proyecto'] or leido[0].get('contenido')!=nuevo:
            raise ValueError('No coincide la lectura posterior; no confirmar éxito')
        verificados.append({'id':m['id'],'sha256':hashlib.sha256(nuevo.encode()).hexdigest()})
    r={'ok':True,'verificados':verificados,'copia_original':str(respaldo) if respaldo else None}
    _atomic(PROPUESTAS/'redaccion_recuerdos_resultado.json',r)
    return r
