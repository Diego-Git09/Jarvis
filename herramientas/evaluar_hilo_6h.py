"""Corpus congelado de continuidad: controlador sintético, sin IA ni Segundo Cerebro."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

RAIZ = Path(__file__).resolve().parents[1]
REPORTES = RAIZ/'registros/reportes/mejora_6h_20261014'


def construir():
    casos=[]
    familias=[('opciones',12),('confirmaciones',12),('reapertura',6),('cambio_tema',8),('reintento',8),('largo',8),('negativos',6)]
    confirmaciones=['dale','ya po','sipo','obvio','sí te confirmo','hazlo','mándale','adelante','perfecto empecemos','SI te confirmo empecemos','sigamos','continúa']
    ordinales=['empecemos con el 1','el segundo','la última','opción 2','el primero','la tercera']
    n=0
    for familia,cantidad in familias:
        for variante in range(cantidad):
            n+=1;marca=f'CENTRO_{n:03d}';cifra=str(270+n)
            inicial=f'Ayúdame con el caso de la tienda {marca} en Kotlin Android Studio. El nombre literal será "Lápiz Rosado {n}". El presupuesto es {cifra}.'
            propuesta=f'El caso de tienda {marca} tiene cuatro accesos.\n1. Crear proyecto Kotlin.\n2. Diseñar la pantalla de accesos.\n3. Comprobar datos sintéticos.\n¿Empezamos?'
            pasos=[{'tipo':'usuario','texto':inicial},{'tipo':'asistente','texto':propuesta},{'tipo':'usuario','texto':'Elige el nombre literal "Lápiz Rosado '+str(n)+'" y conserva el presupuesto '+cifra+'.'},
                   {'tipo':'asistente','texto':'Conservaré la decisión literal. La propuesta pendiente mantiene sus tres pasos.'}]
            if familia=='opciones':
                frase=ordinales[variante%len(ordinales)];numero=[1,2,3,2,1,3][variante%6]
                pasos.extend([{'tipo':'usuario','texto':frase,'espera':{'seleccion':numero,'contiene':[marca]}},{'tipo':'asistente','texto':'Siguiente paso: realizar la explicación seleccionada; sin crear archivos.'},
                              {'tipo':'usuario','texto':'y después?','espera':{'contiene':[marca],'continuacion':True}}])
            elif familia=='confirmaciones':
                pasos.extend([{'tipo':'usuario','texto':confirmaciones[variante],'espera':{'aceptada':True,'contiene':[marca]}},
                              {'tipo':'asistente','texto':'Paso concreto: abre el asistente de proyecto y comprueba Kotlin.'},
                              {'tipo':'usuario','texto':'eso','espera':{'contiene':[marca],'continuacion':True}}])
            elif familia=='reapertura':
                pasos.extend([{'tipo':'usuario','texto':'empecemos con el 1'},{'tipo':'asistente','texto':'Primero crea el proyecto en una carpeta nueva.'},
                              {'tipo':'reinicio'},{'tipo':'usuario','texto':'volvamos al caso de la tienda','espera':{'contiene':[marca,cifra],'sin_propuesta':True}}])
            elif familia=='cambio_tema':
                pasos.extend([{'tipo':'usuario','texto':'otro tema: explícame cómo hacer arroz','espera':{'excluye':[marca],'sin_tanda':True}},
                              {'tipo':'asistente','texto':'Para cocinar arroz prepara agua y una olla.'},
                              {'tipo':'usuario','texto':'hazme una guía de eso','espera':{'contiene':['arroz'],'excluye':[marca]}},
                              {'tipo':'asistente','texto':'Lava el arroz, hierve el agua y cocina a fuego bajo.'},
                              {'tipo':'usuario','texto':'vuelve al caso de la tienda','espera':{'contiene':[marca]}}])
            elif familia=='reintento':
                pregunta='Explica el anexo 3 del caso '+marca
                pasos.extend([{'tipo':'usuario','texto':pregunta},{'tipo':'fallo','texto':'Ollama agotó el tiempo de espera.', 'acciones':variante%2==1},
                              {'tipo':'reinicio'},{'tipo':'usuario','texto':'reintenta' if variante%2==0 else 'sigue',
                               'espera':{'pedido':pregunta,'tanda':'a'*32} if variante%2==0 else {'aclaracion':True,'no_reintento':True}},
                              {'tipo':'asistente','texto':'El estado previo quedó conservado; no se verifica ninguna escritura.'}])
            elif familia=='largo':
                for k in range(4):
                    pasos.extend([{'tipo':'usuario','texto':f'Explícame el concepto secundario {k} sin cambiar nuestras decisiones.'},
                                  {'tipo':'asistente','texto':('Explicación secundaria de datos sintéticos. '*50)}])
                pasos.append({'tipo':'usuario','texto':'como dijimos, dime nombre y presupuesto del caso','espera':{'contiene':[marca,'Lápiz Rosado '+str(n),cifra]}})
            else:
                frase=['no hagas eso','si dijera "hazlo" no quiero que lo ejecutes','el documento dice "el segundo"','no uses el documento; explica álgebra','cambia de tema: continúa con geografía','hola'][variante]
                espera={'no_aceptada':True}
                if variante in {3,4}:espera.update({'excluye':[marca],'sin_tanda':True})
                pasos.extend([{'tipo':'usuario','texto':frase,'espera':espera},{'tipo':'asistente','texto':'No se ejecutó ninguna acción.'},
                              {'tipo':'usuario','texto':'gracias','espera':{'no_aceptada':True}}])
            casos.append({'id':f'H6-{n:03d}','familia':familia,'pasos':pasos})
    return casos


def congelar():
    REPORTES.mkdir(parents=True,exist_ok=True)
    p=REPORTES/'corpus_hilo_60.json'
    if p.exists():raise ValueError('El corpus ya existe: no se sobrescribe')
    texto=json.dumps(construir(),ensure_ascii=False,indent=2)+'\n';p.write_text(texto,encoding='utf-8')
    huella=hashlib.sha256(texto.encode()).hexdigest()
    (REPORTES/'corpus_hilo_60.sha256').write_text(huella+'  corpus_hilo_60.json\n')
    return huella


def construir_v2():
    """Amplía V1 sin reemplazar sus casos, rúbrica, huella ni auditorías.

    V1 tenía 4–7 mensajes de usuario y solo 3–6 respuestas, con cierres pendientes:
    servía de comprobación del controlador, pero no acreditaba 60 guiones de
    5–15 turnos completos. V2 añade cierres y seguimientos con oráculos explícitos.
    Las respuestas siguen siendo fixtures; no se presentan como respuestas de IA.
    """
    ruta=REPORTES/'corpus_hilo_60.json';contenido=ruta.read_bytes()
    if hashlib.sha256(contenido).hexdigest()!=(REPORTES/'corpus_hilo_60.sha256').read_text().split()[0]:raise ValueError('V1 cambió')
    casos=json.loads(contenido)
    for caso in casos:
        n=int(caso['id'].split('-')[-1]);marca=f'CENTRO_{n:03d}';cifra=str(270+n)
        pasos=caso['pasos'];familia=caso['familia']
        if pasos[-1]['tipo']=='usuario':
            pasos.append({'tipo':'asistente','texto':'Continuamos con el tema vigente sin crear ni ejecutar archivos.'})
        if familia=='reapertura':
            pasos.extend([{'tipo':'usuario','texto':'el segundo','espera':{'aclaracion':True,'no_aceptada':True,'sin_propuesta':True}},
                          {'tipo':'asistente','texto':'¿Qué opción quieres retomar? La lista anterior perdió vigencia al reabrir.'}])
        if familia=='reintento' and (n-1)%8%2==1:
            pasos.extend([{'tipo':'usuario','texto':'reintenta','espera':{'aclaracion':True,'no_reintento':True,'no_aceptada':True}},
                          {'tipo':'asistente','texto':'La acción interrumpida debe comprobarse antes de repetirla.'}])
        while sum(p['tipo']=='usuario' for p in pasos)<6:
            turno=sum(p['tipo']=='usuario' for p in pasos)
            if turno%2==0:
                if familia=='negativos' and n==58:  # «no uses el documento»: objetivo álgebra.
                    espera={'contiene':['álgebra'],'excluye':[marca],'sin_tanda':True}
                elif familia=='negativos' and n==59:  # Cambio explícito a geografía.
                    espera={'contiene':['geografía'],'excluye':[marca],'sin_tanda':True}
                else:espera={'contiene':[marca,cifra,'Lápiz Rosado '+str(n)]}
                pasos.extend([{'tipo':'usuario','texto':'como dijimos, conserva el objetivo y dime qué dato literal falta para continuar','espera':espera},
                              {'tipo':'asistente','texto':'El estado conserva las decisiones literales; preguntar por un dato no autoriza operaciones.'}])
            else:
                pasos.extend([{'tipo':'usuario','texto':'No crees archivos, no compiles y no ejecutes código; solo sigue explicando.','espera':{'no_aceptada':True}},
                              {'tipo':'asistente','texto':'Continúo con una explicación; no se ejecutan herramientas desde este guion sintético.'}])
        caso['id']='H6V2-'+str(n).zfill(3)
        caso['version']=2
        caso['respuesta']='fixture sintético del controlador; no generada por Ollama'
    _validar_turnos(casos)
    return casos


def _validar_turnos(casos):
    for caso in casos:
        abierto=False;completos=0
        for paso in caso['pasos']:
            if paso['tipo']=='usuario':
                if abierto:raise ValueError(caso['id']+': turno sin respuesta antes del siguiente usuario')
                abierto=True
            elif paso['tipo'] in {'asistente','fallo'}:
                if not abierto:raise ValueError(caso['id']+': respuesta sin usuario')
                abierto=False;completos+=1
        if abierto or not 5<=completos<=15:raise ValueError(caso['id']+': exige 5–15 pares usuario/respuesta completos')


def congelar_v2():
    REPORTES.mkdir(parents=True,exist_ok=True)
    p=REPORTES/'corpus_hilo_60_v2.json'
    if p.exists():raise ValueError('V2 ya está congelado: no sobrescribir')
    texto=json.dumps(construir_v2(),ensure_ascii=False,indent=2)+'\n'
    p.write_text(texto,encoding='utf-8');sha=hashlib.sha256(texto.encode()).hexdigest()
    (REPORTES/'corpus_hilo_60_v2.sha256').write_text(sha+'  '+p.name+'\n')
    return {'sha256':sha,'casos':60,'tipo':'60 guiones de 6–7 turnos completos; controlador sintético'}


def congelar_correcciones_v2():
    """Preserva los tres oráculos de cierre mal asociados por número de caso.

    La corrección es del arnés, no del código ni de la interpretación. La ronda
    bruta y el corpus original siguen intactos. La fuente de cada corrección
    es el propio mensaje de cambio de tema dentro del guion congelado.
    """
    p=REPORTES/'correcciones_arnes_hilo_v2.json'
    if p.exists():raise ValueError('Las correcciones ya están congeladas')
    fuente=REPORTES/'corpus_hilo_60_v2.json';sha=hashlib.sha256(fuente.read_bytes()).hexdigest()
    casos=json.loads(fuente.read_text());cambios=[]
    for caso in casos:
        if caso['id'] not in {'H6V2-057','H6V2-058','H6V2-059'}:continue
        n=int(caso['id'].split('-')[-1]);marca=f'CENTRO_{n:03d}'
        for i,paso in enumerate(caso['pasos']):
            if paso.get('texto')!='como dijimos, conserva el objetivo y dime qué dato literal falta para continuar':continue
            nueva=({'contiene':[marca,str(270+n),'Lápiz Rosado '+str(n)]} if n==57 else
                   {'contiene':['álgebra' if n==58 else 'geografía'],'excluye':[marca],'sin_tanda':True})
            cambios.append({'id':caso['id'],'indice_paso':i,'antes':paso['espera'],'despues':nueva,
                            'motivo':'Desfase de un ID al asociar el objetivo de cierre. No se cambia la petición, respuesta fixture ni criterio de aislamiento del tema.'})
    datos={'sha256_corpus':sha,'correcciones':cambios,'cambia_codigo_controlador':False}
    texto=json.dumps(datos,ensure_ascii=False,indent=2)+'\n';p.write_text(texto,encoding='utf-8')
    huella=hashlib.sha256(texto.encode()).hexdigest();p.with_suffix('.sha256').write_text(huella+'  '+p.name+'\n')
    return datos|{'sha256_correcciones':huella}


def evaluar(ronda,version=1,arnes_corregido=False):
    import seguimiento_conversacion as S
    sufijo='_v2' if version==2 else ''
    p=REPORTES/('corpus_hilo_60'+sufijo+'.json');contenido=p.read_bytes();sha=hashlib.sha256(contenido).hexdigest()
    if sha!=(REPORTES/('corpus_hilo_60'+sufijo+'.sha256')).read_text().split()[0]:raise ValueError('El corpus cambió')
    casos=json.loads(contenido)
    if version==2:_validar_turnos(casos)
    sha_correcciones=''
    if arnes_corregido:
        p=REPORTES/'correcciones_arnes_hilo_v2.json';sha_correcciones=hashlib.sha256(p.read_bytes()).hexdigest()
        if sha_correcciones!=p.with_suffix('.sha256').read_text().split()[0]:raise ValueError('Las correcciones cambiaron')
        datos=json.loads(p.read_text())
        if datos['sha256_corpus']!=sha:raise ValueError('Corrección para otro corpus')
        por_id={c['id']:c for c in casos}
        for cambio in datos['correcciones']:
            paso=por_id[cambio['id']]['pasos'][cambio['indice_paso']]
            if paso['espera']!=cambio['antes']:raise ValueError('El oráculo original no coincide')
            paso['espera']=cambio['despues']
    H=None
    if ronda!='primero' or version==2:import hilo_conversacion as H
    filas=[]
    with tempfile.TemporaryDirectory() as temporal:
        if H is not None:H.CARPETA=Path(temporal)/'hilos'
        for caso in casos:
            estado={'_tanda_documentos':'a'*32};historial=[];pedido='';resultados=[]
            for paso in caso['pasos']:
                tipo=paso['tipo'];texto=paso.get('texto','')
                if tipo=='usuario':
                    pedido=texto
                    if H is None:
                        contexto=S.contexto(historial,texto);resultado={'contexto':contexto,'pedido':texto,'continuacion':bool(contexto),'seleccion':S.eleccion(texto),
                          'aceptada':S.inicio_confirmado(texto),'tanda':estado.get('_tanda_documentos'),'aclaracion':'','reintento':False}
                    else:resultado=H.iniciar_turno(estado,texto,historial)
                    historial.append({'role':'user','content':resultado['pedido']})
                    if 'espera' in paso:
                        errores=[];espera=paso['espera'];contexto=resultado.get('contexto','')
                        for t in espera.get('contiene',[]):
                            if t not in contexto:errores.append('falta literal: '+t)
                        for t in espera.get('excluye',[]):
                            if t in contexto:errores.append('arrastra tema: '+t)
                        for clave in ['seleccion','pedido','tanda','continuacion','aceptada']:
                            if clave in espera and resultado.get(clave)!=espera[clave]:errores.append(clave)
                        if espera.get('sin_propuesta') and estado.get('_hilo_conversacion',{}).get('propuesta'):errores.append('propuesta restaurada')
                        if espera.get('sin_tanda') and estado.get('_tanda_documentos'):errores.append('tanda arrastrada')
                        if espera.get('aclaracion') and not resultado.get('aclaracion'):errores.append('sin aclaración')
                        if espera.get('no_reintento') and resultado.get('reintento'):errores.append('repite una acción')
                        if espera.get('no_aceptada') and resultado.get('aceptada'):errores.append('confirma negación/ejemplo')
                        resultados.append({'pedido':texto,'errores':errores,'resultado':resultado})
                elif tipo in {'asistente','fallo'}:
                    historial.append({'role':'assistant','content':texto})
                    if H is not None:H.terminar_turno(estado,pedido,texto,fallido=tipo=='fallo',hubo_acciones=paso.get('acciones',False))
                elif tipo=='reinicio':
                    if H is not None:
                        ident=estado['_hilo_conversacion']['id'];estado={};H.recuperar(estado,ident)
                    else:estado={}
                    historial=[]
            completos=sum(p['tipo'] in {'asistente','fallo'} for p in caso['pasos'])
            filas.append({'id':caso['id'],'familia':caso['familia'],'ok':all(not r['errores'] for r in resultados),'comprobaciones':resultados,'sha256_corpus':sha,'ronda':ronda,
                          'turnos_usuario':sum(p['tipo']=='usuario' for p in caso['pasos']),'turnos_completos':completos,'tipo':'controlador sintético sin Ollama',
                          'sha256_correcciones_arnes':sha_correcciones})
    salida=REPORTES/f'hilo{sufijo}_{ronda}.jsonl'
    if salida.exists():raise ValueError('La ronda existe: no sobrescribir')
    salida.write_text(''.join(json.dumps(f,ensure_ascii=False)+'\n' for f in filas),encoding='utf-8')
    return {'ronda':ronda,'casos':len(filas),'aprobados':sum(f['ok'] for f in filas),'fallos':[f['id'] for f in filas if not f['ok']],
            'familias':{fa:{'total':sum(f['familia']==fa for f in filas),'ok':sum(f['familia']==fa and f['ok'] for f in filas)} for fa in sorted({f['familia'] for f in filas})},'sha256':sha,
            'turnos_completos_min':min(f['turnos_completos'] for f in filas),'turnos_completos_max':max(f['turnos_completos'] for f in filas),
            'referencias_comprobadas':sum(len(f['comprobaciones']) for f in filas),'comprobaciones_correctas':sum(not r['errores'] for f in filas for r in f['comprobaciones']),
            'sha256_correcciones_arnes':sha_correcciones,
            'alcance':'Respuestas fixture: comprueba el controlador; no evalúa calidad ni bucles generados por Ollama.'}


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('accion',choices=['congelar','primero','final','congelar-v2','evaluar-v2','congelar-correcciones-v2','evaluar-v2-corregido']);a.add_argument('--ronda',default='cierre');v=a.parse_args()
    resultado=congelar() if v.accion=='congelar' else congelar_v2() if v.accion=='congelar-v2' else congelar_correcciones_v2() if v.accion=='congelar-correcciones-v2' else evaluar(v.ronda,2,v.accion=='evaluar-v2-corregido') if v.accion.startswith('evaluar-v2') else evaluar(v.accion)
    print(json.dumps(resultado,ensure_ascii=False,indent=2))
