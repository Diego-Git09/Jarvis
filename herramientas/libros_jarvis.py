"""Excel por hoja/rango con lectura XML progresiva; fórmulas nunca se ejecutan."""
import re
from zip_acotado import ZipFileAcotado
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import sqlite3
import tempfile
import os
from pathlib import PurePosixPath
from xml.etree import ElementTree as E
from xml.parsers import expat

def _buffer():
    from tandas_documentales import recursos
    return recursos()['mb_buffer']*1024**2

def _parsear(f,inicio,fin,dato,control=None):
    parser=expat.ParserCreate(namespace_separator='}')
    parser.StartElementHandler=inicio;parser.EndElementHandler=fin;parser.CharacterDataHandler=dato
    parser.ExternalEntityRefHandler=lambda *args:0
    while True:
        if control:control()
        raw=f.read(65536)
        try:parser.Parse(raw,not raw)
        except expat.ExpatError as e:raise ValueError('XML del libro dañado o no seguro.') from e
        if not raw:break

def _col(n):
    r=0
    for c in n:r=r*26+ord(c)-64
    return r

class _Cadenas:
    """Cadenas compartidas a disco privado: no acumula cientos de miles en RAM."""
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-cadenas-');ruta=self.tmp.name+'/cadenas.sqlite';self.db=sqlite3.connect(ruta);os.chmod(ruta,0o600);self.db.execute('CREATE TABLE cadenas(n INTEGER PRIMARY KEY,t TEXT)');self.n=0
    def append(self,t):
        from conversaciones_jarvis import _redactar
        self.db.execute('INSERT INTO cadenas VALUES (?,?)',(self.n,_redactar(t)));self.n+=1
    def __len__(self):return self.n
    def __getitem__(self,n):
        fila=self.db.execute('SELECT t FROM cadenas WHERE n=?',(n,)).fetchone()
        if not fila:raise IndexError(n)
        return fila[0]
    def cerrar(self):self.db.close();self.tmp.cleanup()

def _libro(p,control=None):
    from tandas_documentales import zip_seguro,limites
    z=ZipFileAcotado(p)
    try:
        zip_seguro(z,dict(limites(),archivos=1000,mb_archivo=100,mb_tanda=500))
        for n in ('xl/workbook.xml','xl/_rels/workbook.xml.rels'):
            if z.getinfo(n).file_size>min(_buffer(),1024**2):raise ValueError('Metadatos del libro demasiado grandes para el buffer autorizado.')
        raiz=E.fromstring(z.read('xl/workbook.xml'));rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relaciones={x.attrib['Id']:x.attrib['Target'] for x in rels};hojas=[]
        for h in raiz.iter():
            if h.tag.rsplit('}',1)[-1]!='sheet':continue
            ident=next((v for k,v in h.attrib.items() if k.endswith('}id')),'')
            target=relaciones.get(ident,'');ruta=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            ruta=str(PurePosixPath(ruta))
            if '..' in PurePosixPath(ruta).parts or ruta not in z.namelist():raise ValueError('Relación de hoja inválida.')
            hojas.append((h.attrib.get('name','Hoja'),ruta))
        shared=_Cadenas()
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                estado={'si':False,'t':False,'partes':[],'tam':0};tope=_buffer()
                def inicio(n,a):
                    n=n.rsplit('}',1)[-1]
                    if n=='si':estado.update(si=True,partes=[],tam=0)
                    elif n=='t' and estado['si']:estado['t']=True
                def dato(t):
                    if estado['t']:
                        estado['tam']+=len(t)
                        if estado['tam']>tope:raise ValueError('Una cadena compartida supera el buffer; no cargué el libro entero.')
                        estado['partes'].append(t)
                def fin(n):
                    n=n.rsplit('}',1)[-1]
                    if n=='t':estado['t']=False
                    elif n=='si':
                        shared.append(''.join(estado['partes']));estado['si']=False
                        if len(shared)>300000:raise ValueError('Tabla de cadenas demasiado grande; divide el libro.')
                _parsear(f,inicio,fin,dato,control)
        shared.db.commit()
        return z,hojas,shared
    except BaseException:
        z.close()
        if 'shared' in locals():shared.cerrar()
        raise

def _filas(z,ruta,shared,control=None):
    with z.open(ruta) as f:
        parser=expat.ParserCreate(namespace_separator='}');parser.ExternalEntityRefHandler=lambda *args:0
        estado={'celda':None,'captura':False,'tam':0,'vals':[],'numero':0,'clave_privada':False};listas=[];tope=_buffer();privadas=set();primera=True
        sensible=re.compile(r'(?i)^(?:api[ _-]?key|(?:access[ _-]?|auth[ _-]?)?token|password|passwd|contrase[ñn]a|secret(?:[ _-]?key)?|private[ _-]?key|authorization|credential)s?$')
        def inicio(n,a):
            n=n.rsplit('}',1)[-1]
            if n=='row':estado.update(tam=0,vals=[],numero=int(a.get('r','0')))
            elif n=='c':estado['celda']={'ref':a.get('r',''),'tipo':a.get('t','n'),'partes':[],'formula':False}
            elif estado['celda'] is not None:
                if n in {'v','t'}:estado['captura']=True
                elif n=='f':estado['celda']['formula']=True
        def dato(t):
            if estado['celda'] is not None and estado['captura']:
                estado['tam']+=len(t)
                if estado['tam']>tope:raise ValueError('Una fila supera el buffer autorizado; divide las celdas extensas.')
                estado['celda']['partes'].append(t)
        def fin(n):
            n=n.rsplit('}',1)[-1]
            if n in {'v','t'}:estado['captura']=False
            elif n=='c' and estado['celda'] is not None:
                c=estado['celda'];v=''.join(c['partes']);tipo=c['tipo']
                if tipo=='s':
                    try:v=shared[int(v)]
                    except (ValueError,IndexError):v='[cadena inválida]'
                estado['vals'].append((c['ref'],v,'fórmula (resultado guardado)' if c['formula'] else 'número' if tipo=='n' else 'booleano' if tipo=='b' else 'texto'));estado['celda']=None
                if len(estado['vals'])>10000:raise ValueError('Fila con demasiadas celdas; lectura acotada.')
            elif n=='row':
                from conversaciones_jarvis import _redactar
                nonlocal primera
                vals=estado['vals']
                if primera:
                    privadas.update(re.sub(r'\d','',ref) for ref,v,_ in vals if sensible.fullmatch(v.strip()))
                protegidos=[]
                anterior_sensible=False
                for ref,v,tipo in vals:
                    if '-----BEGIN ' in v and 'PRIVATE KEY-----' in v:estado['clave_privada']=True
                    ocultar=estado['clave_privada'] or (not primera and re.sub(r'\d','',ref) in privadas) or anterior_sensible and not sensible.fullmatch(v.strip())
                    if '-----END ' in v and 'PRIVATE KEY-----' in v:estado['clave_privada']=False
                    anterior_sensible=bool(sensible.fullmatch(v.strip()))
                    limpio=v if v.lstrip('+-').replace('.','',1).isdecimal() else _redactar(v)
                    protegidos.append((ref,'[REDACTADO]' if ocultar else limpio,'texto' if ocultar else tipo))
                listas.append((estado['numero'],protegidos));primera=False
        parser.StartElementHandler=inicio;parser.EndElementHandler=fin;parser.CharacterDataHandler=dato
        while True:
            if control:control()
            raw=f.read(65536)
            try:parser.Parse(raw,not raw)
            except expat.ExpatError as e:raise ValueError('XML de hoja dañado o no seguro.') from e
            yield from listas;listas=[]
            if not raw:break

def unidades(p,max_caracteres=2_000_000,item=None,control=None):
    """Hasta 100.000 filas indexadas; bloques de 16 KiB con rangos reales."""
    item=item if item is not None else {};z,hojas,shared=_libro(p,control);total=0;metas=[]
    try:
        for nombre,ruta in hojas:
            lineas=[];tam=0;inicio=1;filas=0;tipos={};cabecera=[];muestra=[];sumas=defaultdict(Decimal);completa=True
            for n,celdas in _filas(z,ruta,shared,control):
                if control:control()
                t=f'Fila {n}: '+' | '.join(ref+'='+v for ref,v,_ in celdas)
                if total+len(t)+1>max_caracteres or filas>=100000:completa=False;item['cortado']=True;break
                filas+=1
                if not cabecera:cabecera=[v for _,v,_ in celdas]
                for ref,v,tipo in celdas:
                    col=re.sub(r'\d','',ref);tipos.setdefault(col,set()).add(tipo)
                    if tipo=='número':
                        try:
                            num=Decimal(v)
                            if num.is_finite():sumas[col]+=num
                        except InvalidOperation:pass
                if len(muestra)<5:muestra.append(t)
                if lineas and tam+len(t)>16384:
                    yield 'hoja '+nombre+f' · filas {inicio}-{anterior}','\n'.join(lineas);lineas=[];tam=0
                if not lineas:inicio=n
                lineas.append(t);tam+=len(t)+1;total+=len(t)+1;anterior=n;item['filas_leidas']=item.get('filas_leidas',0)+1
            if lineas:yield 'hoja '+nombre+f' · filas {inicio}-{anterior}','\n'.join(lineas)
            metas.append({'hoja':nombre,'filas_leidas':filas,'completa':completa,'columnas':cabecera,'tipos':{k:sorted(v) for k,v in tipos.items()},'muestra':muestra,'sumas_numericas_leidas':{k:str(v) for k,v in sumas.items()}})
            item['hojas']=metas
            if total>=max_caracteres:break
    finally:shared.cerrar();z.close()

def extraer(p,max_caracteres=2_000_000):
    item={};acumulado={}
    for ref,t in unidades(p,max_caracteres,item):
        nombre=ref.split(' · filas ',1)[0][5:];acumulado.setdefault(nombre,[]).append(t)
    return {'hojas':item.get('hojas',[]),'textos':[(n,'\n'.join(v)) for n,v in acumulado.items()],'cortado':item.get('cortado',False)}

def estadisticas(p,control=None,max_filas=1_000_000):
    """Agregados del XML en una pasada, separados del presupuesto del índice.

    Cuenta también filas posteriores a las 100.000 que admite el índice. No
    ejecuta fórmulas: suma exclusivamente celdas numéricas guardadas sin fórmula.
    El llamador impone plazo y rutas; nunca afirma completar si alcanzó el tope.
    """
    if type(max_filas) is not int or not 1<=max_filas<=1_000_000:raise ValueError('Tope de filas inválido.')
    z,hojas,shared=_libro(p,control);salida=[];total=0;completo=True
    try:
        for nombre,ruta in hojas:
            filas=0;sumas=defaultdict(Decimal);numericas=defaultdict(int);formulas=0;muestras=[]
            for n,celdas in _filas(z,ruta,shared,control):
                if control:control()
                if total>=max_filas:completo=False;break
                total+=1;filas+=1
                if len(muestras)<3:muestras.append({'fila':n,'celdas':[r+'='+v[:200] for r,v,_ in celdas[:20]]})
                for ref,v,tipo in celdas:
                    if tipo.startswith('fórmula'):formulas+=1;continue
                    if tipo!='número':continue
                    try:
                        num=Decimal(v)
                        if num.is_finite():
                            col=re.sub(r'\d','',ref);sumas[col]+=num;numericas[col]+=1
                    except InvalidOperation:pass
            salida.append({'hoja':nombre,'filas':filas,'sumas_numericas':{k:str(v) for k,v in sumas.items()},'celdas_numericas':dict(numericas),'formulas_omitidas':formulas,'muestras':muestras})
            if not completo:break
        return {'hojas':salida,'filas':total,'completo':completo,'limite_filas':max_filas,'metodo':'XML progresivo; agregados calculados por código; fórmulas sin ejecutar ni sumar.'}
    finally:shared.cerrar();z.close()

def rango(p,hoja,seleccion):
    m=re.fullmatch(r'([A-Z]{1,3})([1-9]\d*):([A-Z]{1,3})([1-9]\d*)',seleccion.upper())
    if not m:raise ValueError('Usa un rango como A1:D20.')
    a,f,b,g=_col(m[1]),int(m[2]),_col(m[3]),int(m[4])
    if b<a or g<f or (b-a+1)*(g-f+1)>2000 or g>100000:raise ValueError('Rango inválido o mayor de 2000 celdas/100000 filas; divídelo.')
    z,hojas,shared=_libro(p)
    try:
        rutas=[ruta for nombre,ruta in hojas if nombre==hoja]
        if len(rutas)!=1:raise ValueError('Hoja no encontrada; nombres: '+', '.join(n for n,_ in hojas))
        salida=[f'{p.name} · hoja {hoja} · rango {seleccion}. Valores guardados; fórmulas sin ejecutar.']
        for n,celdas in _filas(z,rutas[0],shared):
            if n>g:break
            if n<f:continue
            valores=[ref+'='+v for ref,v,_ in celdas if a<=_col(re.sub(r'\d','',ref))<=b]
            salida.append(f'Fila {n}: '+' | '.join(valores))
        return '\n'.join(salida)
    finally:shared.cerrar();z.close()
