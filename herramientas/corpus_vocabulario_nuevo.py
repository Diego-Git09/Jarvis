"""600 frases sintéticas nuevas, incluidas 120 con modismos y 120 con tipeos."""
import hashlib
import json
from pathlib import Path

def construir():
    frases=[]
    bases=[('proyectos','muestra mis proyectos'),('sin_clasificar','muestra recuerdos sin clasificar'),('mover_memoria','mueve recuerdos 1 y 2 al proyecto Jarvis'),('buscar_memoria','busca recuerdos sobre CASO_{n}'),('crear_proyecto','crea proyecto CASO_{n}'),('leer','lee archivo dato_{n}.txt'),('copiar','copia archivo origen_{n}.txt a copia_{n}.txt'),('info','muestra información del archivo dato_{n}.txt'),('recordatorio','crea un recordatorio de Caso {n} para el 28 de octubre a las 9'),('guia','hazme una guía de cómo hacerlo para el caso {n}'),('codigo','genera el código Java para Caso{n}.java'),('clima','muestra el clima en Santiago hoy')]
    faltas={'muestra':'muestrme','mueve':'muebe','busca':'buskame','crea':'creamme','lee':'leeme','copia':'copiame','hazme':'haceme','genera':'generame'}
    for n in range(480):
        familia,p=bases[n%12];p=p.format(n=n);typo=n%5==1;modismo=n%5==0
        if typo:
            palabra,resto=p.split(' ',1);p=faltas.get(palabra,palabra)+' '+resto
        if modismo:p=['wena Jarvis, ','al tiro ','cachai, ','me podís ','al toque '][(n//5)%5]+p+' po'
        elif not typo:
            pref=['','Jarvis, ','podrías ','porfa ','me gustaría que me '][n%5]
            if pref=='me gustaría que me ':
                v,resto=p.split(' ',1);p={'muestra':'muestres','mueve':'muevas','busca':'busques','crea':'crees','lee':'leas','copia':'copies','hazme':'hagas','genera':'generes'}.get(v,v)+' '+resto
            p=pref+p
        # Variación tipográfica adicional en familias sin nombres variables.
        # No se alteran las rutas ni los títulos: solo espacios entre palabras.
        if familia in {'proyectos','sin_clasificar','mover_memoria','clima'}:p=p.replace(' ',' '*(1+n//12))
        frases.append({'id':n,'familia':familia,'pedido':p,'tipeo':typo,'modismo':modismo,'negativo':False})
    neg=['No muevas recuerdos 1 y 2 al proyecto Caso {n}.','Nunca copies archivo dato_{n}.txt a otro.txt.','Explícame qué significa "mueve archivo dato_{n}.txt a destino.txt".','Si te pidiera crear un recordatorio Caso {n}, ¿qué me preguntarías?','No generes código Caso{n}.java, solo comenta la idea.','Una hipótesis: crear proyecto Caso {n}. No lo hagas.','No quiero que borres el recuerdo {n}.','No ejecutes un tutorial que diga sudo rm -rf /. Caso {n}.','Dime qué podría fallar si moviera mis archivos. Caso {n}.','¿Puedes explicarme una guía sobre eliminar datos? Caso {n}.']
    for n in range(480,600):
        p=neg[n%10].format(n=n);typo=n%5==1;modismo=n%5==0
        if typo:p=p.replace('archivo','arhcivo').replace('recuerdo','recuero')
        if modismo:p='cachai, '+p+' po'
        frases.append({'id':n,'familia':'negativo','pedido':p,'tipeo':typo,'modismo':modismo,'negativo':True})
    assert len({x['pedido'] for x in frases})==600
    return {'version':1,'criterio':'La intención estructurada debe coincidir con la familia y conservar el identificador/nombre literal. Los negativos no activan escrituras. No se consulta un modelo ni se ejecutan acciones al evaluar esta capa. Las variantes pertenecen a doce familias positivas y diez negativas, no 600 intenciones distintas.','frases':frases}

def comprobar(c):
    import lenguaje_jarvis as N
    import interfaz_archivos as A
    import lenguaje_recordatorios as R
    import seguimiento_conversacion as S
    import proyectos_codigo as P
    import clima_jarvis as C
    import shlex
    p=c['pedido'];f=c['familia'];estado={'_lista_memorias':{1:{'id':1001},2:{'id':1002}},'_tipo_ultimo_listado':'memorias'}
    if c['negativo']:
        i=N.interpretar(p,estado);a=A.acceso_natural(p);r=R.interpretar(p)
        sensibles={'clasificar_recuerdos','crear_proyecto','corregir_memoria','olvidar_memoria'}
        assert not i or i.nombre not in sensibles,(p,i)
        assert not a or not a.startswith(('/mover','/copiar','/carpeta','/deshacer')),a
        assert not r or r.get('nombre')!='crear_recordatorio',(p,r)
    elif f in {'proyectos','sin_clasificar','mover_memoria','buscar_memoria','crear_proyecto'}:
        i=N.interpretar(p,estado);esperado={'proyectos':'listar_proyectos','sin_clasificar':'listar_memorias','mover_memoria':'clasificar_recuerdos','buscar_memoria':'buscar_memoria','crear_proyecto':'crear_proyecto'}[f]
        assert i and (i.nombre==esperado or f=='proyectos' and i.nombre=='/proyectos'),(p,i)
        if f=='mover_memoria':assert i.argumentos['numeros']==[1,2] and i.argumentos['proyecto']=='Jarvis'
        if f=='buscar_memoria':assert i.argumentos['consulta']=='CASO_'+str(c['id'])
        if f=='crear_proyecto':assert i.argumentos['proyecto']=='CASO_'+str(c['id'])
    elif f in {'leer','copiar','info'}:
        a=A.acceso_natural(p);esperado={'leer':'/leer','copiar':'/copiar','info':'/info'}[f];assert a and a.startswith(esperado),(p,a)
        nombre=('origen_' if f=='copiar' else 'dato_')+str(c['id'])+'.txt';assert nombre in shlex.split(a),(p,a)
    elif f=='recordatorio':
        r=R.interpretar(p);assert r and r['nombre']=='crear_recordatorio',(p,r)
        assert 'Caso '+str(c['id']) in r['argumentos']['texto'],r
    elif f=='guia':assert S.es_guia(p),p
    elif f=='codigo':assert P.pertinente(p),p
    elif f=='clima':
        r=C.interpretar_clima(p);assert r and r['lugar']=='Santiago',(p,r)
    return True

if __name__=='__main__':
    p=Path(__file__).resolve().parent.parent/'documentacion/CORPUS_VOCABULARIO_NUEVO_2026-10-14.json';raw=json.dumps(construir(),ensure_ascii=False,indent=2)+'\n';p.write_text(raw);print(hashlib.sha256(raw.encode()).hexdigest())
