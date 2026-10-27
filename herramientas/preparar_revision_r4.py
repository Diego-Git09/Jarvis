"""Propuestas de revisión sin modificar ni borrar el historial de origen."""
from datetime import datetime
import hashlib
import json
import re
from entorno_jarvis import PROYECTO,DATOS,REGISTROS
from conversaciones_jarvis import _atomic,_redactar

DESTINO=REGISTROS/'reportes/ronda4_20261021'

def hilos():
    origen=REGISTROS/'reportes/ronda3_20261020/auditoria_hilos_medidor.json'
    candidatos=json.loads(origen.read_text())['candidatos']
    from medir_seleccion_20261020 import CASOS
    preguntas={x[0] for x in CASOS}
    preguntas.update({'explica que es RAM y luego explica que es CPU','usuario@equipo:~$ nvidia-smi\nNVIDIA-SMI\nMemoria GPU: 4096 MiB de 8192 MiB. Temperatura: 60 C.'})
    filas=[]
    for x in candidatos:
        nombre=x['archivo']
        if not re.fullmatch(r'[a-f0-9]{32}\.json',nombre):raise ValueError('Identificador no válido')
        f=DATOS/'hilos'/nombre
        if not f.exists():
            filas.append({'id_local':nombre[:-5],'estado':'ya no está en el directorio local','elegible':False});continue
        if f.is_symlink() or f.stat().st_size>400000:raise ValueError('Hilo no seguro')
        bruto=f.read_bytes();d=json.loads(bruto);objetivo=d.get('objetivo','')
        coincide=objetivo in preguntas
        filas.append({'id_local':nombre[:-5],'fecha':d.get('creado'),'actualizado':d.get('actualizado'),
            'titulo':_redactar(objetivo)[:160] if coincide else 'Objetivo no coincide exactamente con el banco; revisión manual',
            'motivo':'Objetivo exacto de un banco sintético y fecha del incidente; esto no prueba por sí solo su autoría.' if coincide else 'Candidato histórico sin coincidencia actual; no limpiar automáticamente.',
            'sha256':hashlib.sha256(bruto).hexdigest(),'elegible':coincide,'ubicacion':'historial local datos/hilos, no ID de Segundo Cerebro'})
    resultado={'fecha':datetime.now().astimezone().isoformat(),'alcance':'Los91 candidatos de la auditoría anterior son archivos locales. No se presume que sean91 recuerdos en Segundo Cerebro.','total_candidatos':len(filas),'candidatos':filas,'accion_propuesta':'Solo con s/n explícito: respaldar los elegibles con permisos600, verificar hashes y apartarlos del historial activo. Si el puntero último los referencia, respaldarlo y dejarlo sin selección; nunca adivinar un hilo legítimo.','aplicado':False}
    _atomic(DESTINO/'propuesta_hilos.json',resultado)
    md=['# Propuesta de hilos sintéticos','',resultado['alcance'],'',resultado['accion_propuesta'],'','| ID local | Fecha | Título | Motivo |','|---|---|---|---|']
    for x in filas:md.append('| '+x['id_local']+' | '+str(x.get('fecha','no disponible'))+' | '+x.get('titulo',x['estado'] if 'estado' in x else '').replace('|','/')+' | '+x.get('motivo','No elegible')+' |')
    (DESTINO/'PROPUESTA_HILOS.md').write_text('\n'.join(md)+'\n');(DESTINO/'PROPUESTA_HILOS.md').chmod(0o600)
    return resultado

def recuerdos(cliente):
    propuestas=[]
    for ident in (1009,1010,1011):
        filas=cliente.llamar('consultar_memoria',{'id_memoria':ident}).get('memorias',[])
        if len(filas)!=1 or filas[0].get('id')!=ident:raise ValueError('No se recuperó un único recuerdo')
        m=filas[0];original=m['contenido'];nuevo=_redactar(original)
        propuestas.append({'id':ident,'proyecto':m['proyecto'],'titulo':_redactar(m['titulo']),'sha256_esperado':hashlib.sha256(original.encode()).hexdigest(),
            'contenido_propuesto':nuevo,'redaccion_necesaria':nuevo!=original,'aplicado':False,'copia_original':'No creada: requiere que el usuario la solicite expresamente.'})
    _atomic(DESTINO/'propuestas_redaccion_recuerdos.json',{'fecha':datetime.now().astimezone().isoformat(),'propuestas':propuestas})
    md=['# Propuestas de redacción de recuerdos','', 'No se han corregido ni borrado recuerdos. No se guarda copia del texto con credenciales. Cada propuesta requiere permiso explícito y relectura con contenido esperado.']
    for m in propuestas:
        md+=['',f"## ID {m['id']} — {m['titulo']}",'',f"Proyecto: {m['proyecto']}. Redacción necesaria: {m['redaccion_necesaria']}.",'',m['contenido_propuesto']]
    (DESTINO/'PROPUESTAS_REDACTADAS.md').write_text('\n'.join(md)+'\n');(DESTINO/'PROPUESTAS_REDACTADAS.md').chmod(0o600)
    return propuestas

def titulos(cliente):
    patrones=[];total=0
    for proyecto in ('Jarvis','sin_clasificar','CHAT JARVIS'):
        for offset in range(0,1000,100):
            filas=cliente.llamar('listar_memorias',{'proyecto':proyecto,'desplazamiento':offset,'limite':100}).get('memorias',[])
            for m in filas:
                if m.get('tipo','recuerdo')!='recuerdo':continue
                total+=1;contenido=m.get('contenido','').split('\n\nOrigen automático:',1)[0].strip();titulo=m.get('titulo','')
                razones=[]
                if len(contenido)<120 or len(contenido.splitlines())<=1:razones.append('fragmento breve o de una línea')
                if re.search(r'(?i)^(modelos permitidos|pol[ií]tica de privacidad|reglas de trabajo|objetivo|contenido|estado|implementaci[oó]n)$',titulo.strip()):razones.append('título de sección genérico')
                if razones:patrones.append({'id':m['id'],'proyecto':proyecto,'titulo':_redactar(titulo),'caracteres':len(contenido),'lineas':len(contenido.splitlines()),'patrones':razones})
            if len(filas)<100:break
    r={'fecha':datetime.now().astimezone().isoformat(),'recuerdos_leidos':total,'candidatos':patrones,'limite':'Hasta1000 registros por proyecto, solo metadatos de candidatos; las heurísticas no acreditan que el recuerdo sea incorrecto.','modificaciones':False}
    _atomic(DESTINO/'auditoria_titulos.json',r)
    return r

def main():
    from cerebro_mcp import ClienteCerebro
    DESTINO.mkdir(parents=True,exist_ok=True,mode=0o700)
    h=hilos();c=ClienteCerebro();p=recuerdos(c);t=titulos(c)
    # Contraste focal: una búsqueda no identifica un hilo local como recuerdo.
    contraste=[]
    for texto in ['Dame tres consejos para organizar un escritorio sin comprar nada.','Depura este Python como texto: for i in range(3) print(i). No lo ejecutes.','explica que es RAM y luego explica que es CPU']:
        encontrados=c.llamar('buscar_memoria',{'proyecto':'CHAT JARVIS','consulta':texto}).get('memorias',[])
        contraste.append({'consulta_banco':texto,'ids_recuperados':[x['id'] for x in encontrados]})
    _atomic(DESTINO/'contraste_hilos_cerebro.json',{'busquedas_focales':contraste,'limite':'No se equiparan archivos locales con IDs del MCP. No es una búsqueda exhaustiva de toda copia posible.'})
    print(json.dumps({'candidatos_locales':h['total_candidatos'],'elegibles':sum(x['elegible'] for x in h['candidatos']),'recuerdos_requieren_redaccion':[x['id'] for x in p if x['redaccion_necesaria']],'recuerdos_leidos_para_titulos':t['recuerdos_leidos'],'titulos_candidatos':len(t['candidatos']),'mutaciones_mcp':0},ensure_ascii=False))

if __name__=='__main__':main()
