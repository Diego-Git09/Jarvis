"""Propone limpieza; aplica únicamente reclasificaciones seleccionadas con permiso."""
import hashlib
import json
import re
from difflib import SequenceMatcher
from entorno_jarvis import DATOS
from conversaciones_jarvis import _atomic

ARCHIVO=DATOS/'propuesta_limpieza.json'

def analizar(filas,contradicciones=()):
    propuestas=[];normalizadas=[]
    def agregar(m,motivo,accion='revisar',destino=None):
        p={'id':m['id'],'titulo':m.get('titulo',''),'proyecto':m.get('proyecto',''),'motivo':motivo,'accion':accion,'contenido_sha256':hashlib.sha256(m.get('contenido','').encode()).hexdigest()}
        if destino:p['destino']=destino
        propuestas.append(p)
    for m in filas:
        t=m.get('contenido','');base=t.split('\n\nOrigen automático:',1)[0];palabras=re.findall(r'\w+',base)
        if len(palabras)<5:agregar(m,'Menos de cinco palabras útiles; revisar antes de conservar u olvidar.')
        if re.search(r'(?:\.{3}|respuesta incompleta|se cort[oó]|sin respuesta final)',base,re.I):agregar(m,'Posible fragmento o conversación inconclusa; comprobar original, no borrar automáticamente.')
        if m.get('proyecto')=='personal' and re.search(r'\bjarvis\b',base,re.I) and m.get('id') in {65,849,866}:
            agregar(m,'Conversación sobre desarrollo de Jarvis en personal; clasificación por confirmar.','clasificar','Jarvis')
        if m.get('titulo','').casefold().startswith('conversación jarvis') and m.get('proyecto') not in {'CHAT JARVIS'}:
            agregar(m,'Intercambio con Jarvis separado del desarrollo del programa.','clasificar','CHAT JARVIS')
        if m.get('proyecto')=='Prueba':agregar(m,'Proyecto de prueba: confirmar si aún se necesita; no hay eliminación automática de proyectos.')
        titulo=m.get('titulo','')
        comunes={'de','del','la','el','los','las','para','con','una','uno','sobre','por','jarvis','conversacion','conversación'}
        claves={x.casefold() for x in re.findall(r'\w{4,}',titulo)}-comunes
        contenido={x.casefold() for x in palabras}
        if len(claves)>=3 and len(palabras)>=30 and not claves&contenido:
            agregar(m,'Posible título ajeno al contenido: no comparte palabras principales. Es una pista léxica, no prueba; revisar el texto original y proponer otro título solo con aprobación.')
        # Omite la plantilla común: la similitud se calcula sobre el diálogo útil.
        n=re.sub(r'(?i)intercambio local de jarvis\.|estado:.*|origen automático:.*','',base)
        n=' '.join(re.findall(r'\w+',n.casefold()))[:6000]
        if len(n)>=80:normalizadas.append((m,n))
    for i,(m,t) in enumerate(normalizadas):
        for anterior,u in normalizadas[:i]:
            if abs(len(t)-len(u))>max(len(t),len(u))*.2:continue
            a,b=set(t.split()),set(u.split())
            if len(a&b)/max(1,len(a|b))<.75:continue
            similitud=SequenceMatcher(None,t,u,autojunk=True).ratio()
            if similitud>=.92:agregar(m,f'Contenido parecido a ID {anterior["id"]}: {similitud:.1%}. Revisar diferencias y fuentes; no se borra.');break
    for c in contradicciones:
        m=next((x for x in filas if x['id']==c.get('id_anterior')),None)
        if m:agregar(m,f'Contradicción pendiente contra ID {c.get("id_nuevo")}; puede ser una respuesta histórica errónea, no un cambio de preferencia. Revisar en el panel.')
    return propuestas

def generar(cliente):
    estado=cliente.llamar('consultar_estado_cerebro',{});filas=[]
    for offset in range(0,2000,100):
        r=cliente.llamar('listar_memorias',{'desplazamiento':offset,'limite':100})
        pag=r.get('memorias',[])
        if not pag:break
        for m in pag:
            # Comparaciones y hashes siempre sobre original completo, no vista recortada.
            completa=cliente.llamar('consultar_memoria',{'id_memoria':m['id']}).get('memorias',[])
            if completa:filas.append(completa[0])
        if len(pag)<100:break
    d={'version':1,'consultado':estado.get('consultado',''),'estado':'PROPUESTO, sin cambios en Segundo Cerebro','limite_lectura':2000,'propuestas':analizar(filas,estado.get('contradicciones',[]))}
    _atomic(ARCHIVO,d);return d

def presentar(d):
    filas=d['propuestas'];return d['estado']+'\nConsulta: '+d.get('consultado','')+'\n'+'\n'.join(f"ID {p['id']} · {p['titulo']} · {p['motivo']} · sugerencia: {p['accion']}"+(f" a {p['destino']}" if p.get('destino') else '') for p in filas)+'\nPara autorizar solo reclasificaciones: /limpieza aplicar ID,ID. Cada una comprueba el original y pide permiso. Olvidos/correcciones requieren una petición específica.'

def aplicar(ids,cliente,confirmar):
    d=json.loads(ARCHIVO.read_text());candidatos=[p for p in d['propuestas'] if p['id'] in ids and p['accion']=='clasificar'];resultado=[]
    if set(ids)!={p['id'] for p in candidatos}:return 'La selección incluye acciones ambiguas/no ejecutables. Elige solo IDs con reclasificación concreta.'
    for p in candidatos:
        filas=cliente.llamar('consultar_memoria',{'id_memoria':p['id']}).get('memorias',[])
        if len(filas)!=1:resultado.append(f"ID {p['id']}: ya no disponible.");continue
        m=filas[0]
        if m['proyecto']!=p['proyecto'] or hashlib.sha256(m['contenido'].encode()).hexdigest()!=p['contenido_sha256']:
            resultado.append(f"ID {p['id']}: cambió; genera otra propuesta.");continue
        if not confirmar(f"Mover ID {p['id']} «{p['titulo']}» de {m['proyecto']} a {p['destino']}?\n{m['contenido']}"):
            resultado.append(f"ID {p['id']}: sin permiso, no se movió.");continue
        r=cliente.llamar('clasificar_memoria',{'id_memoria':p['id'],'proyecto':p['destino'],'proyecto_esperado':m['proyecto'],'contenido_esperado':m['contenido']})
        if not r.get('ok'):resultado.append(f"ID {p['id']}: servidor rechazó el cambio.");continue
        final=cliente.llamar('consultar_memoria',{'id_memoria':p['id']}).get('memorias',[])
        resultado.append(f"ID {p['id']}: "+('reclasificación comprobada.' if final and final[0]['proyecto']==p['destino'] and final[0]['contenido']==m['contenido'] else 'resultado sin confirmar; vuelve a consultar.'))
    return '\n'.join(resultado)
