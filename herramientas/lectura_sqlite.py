"""Esquemas y muestras SQLite sin materializar celdas extensas completas.

Solo consultas construidas aquí. No lee vistas ni calcula columnas virtuales.
TEXT grande: blobopen de solo lectura y prefijo de64KiB; BLOB: solo tamaño.
Sin rowid accesible, una celda extensa se declara omitida, sin carga alternativa.
"""
from contextlib import contextmanager
import codecs
import re
import sqlite3

MAX_CELDA=65536
MAX_MUESTRA=1000
MAX_ESQUEMA=65536
SENSIBLE=re.compile(r'(?i)(?:api.?key|token|secret|password|passwd|contrase[ñn]a|authorization|credential|private.?key)')


def _identificador(nombre):return '"'+nombre.replace('"','""')+'"'


def _autorizar(accion,a,b,base,origen):
    if accion in {sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ}:return sqlite3.SQLITE_OK
    if accion==sqlite3.SQLITE_FUNCTION and (b or '').casefold() in {'typeof','octet_length','like','substr'}:return sqlite3.SQLITE_OK
    if accion==sqlite3.SQLITE_PRAGMA and (a or '').casefold() in {'encoding','table_xinfo','table_list'}:return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


@contextmanager
def abrir(p,control=None):
    db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=1)
    interrumpido=[]
    try:
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF')
        db.enable_load_extension(False)
        db.execute('BEGIN')
        db.set_authorizer(_autorizar)
        if control:
            def progreso():
                try:control();return 0
                except (InterruptedError,TimeoutError) as e:interrumpido.append(e);return 1
            db.set_progress_handler(progreso,1000)
        try:yield db
        except sqlite3.OperationalError:
            if interrumpido:raise interrumpido[0]
            raise
    finally:db.close()


def _redactar_celda(texto):
    from conversaciones_jarvis import _redactar
    texto=_redactar(texto)
    # Un prefijo no debe exponer el cuerpo de una clave cuyo cierre está
    # fuera de la muestra. La omisión termina en la celda, no en otra fila.
    m=re.search(r'-----BEGIN [^-]*PRIVATE KEY-----',texto)
    if m:texto=texto[:m.start()]+'[CLAVE PRIVADA REDACTADA]'
    return texto[:MAX_MUESTRA]


def _fin_cita(sql,inicio):
    cierre=']' if sql[inicio]=='[' else sql[inicio];i=inicio+1
    while i<len(sql):
        if sql[i]==cierre:
            if i+1<len(sql) and sql[i+1]==cierre:i+=2;continue
            return i+1
        i+=1
    return i


def _saltar_comentario(sql,i):
    if sql.startswith('--',i):
        fin=sql.find('\n',i+2);return len(sql) if fin<0 else fin+1
    fin=sql.find('*/',i+2);return len(sql) if fin<0 else fin+2


def _esquema_seguro(sql):
    from conversaciones_jarvis import _redactar
    sql=sql or '';partes=[];inicio=0;i=0
    while i<len(sql):
        if sql[i] in '\'"`[':i=_fin_cita(sql,i);continue
        if sql.startswith(('--','/*'),i):i=_saltar_comentario(sql,i);continue
        if (sql[i:i+7].casefold()=='default' and (i==0 or not (sql[i-1].isalnum() or sql[i-1]=='_'))
            and (i+7==len(sql) or not (sql[i+7].isalnum() or sql[i+7]=='_'))):
            valor=i+7
            while valor<len(sql):
                if sql[valor].isspace():valor+=1
                elif sql.startswith(('--','/*'),valor):valor=_saltar_comentario(sql,valor)
                else:break
            fin=valor
            if fin<len(sql) and sql[fin] in '\'"`[':fin=_fin_cita(sql,fin)
            elif fin<len(sql) and sql[fin]=='(':
                profundidad=0
                while fin<len(sql):
                    if sql[fin] in '\'"`[':fin=_fin_cita(sql,fin);continue
                    if sql.startswith(('--','/*'),fin):fin=_saltar_comentario(sql,fin);continue
                    if sql[fin]=='(':profundidad+=1
                    elif sql[fin]==')':
                        profundidad-=1
                        if profundidad==0:fin+=1;break
                    fin+=1
            else:
                if fin<len(sql) and sql[fin] in '+-':
                    fin+=1
                    while fin<len(sql) and sql[fin].isspace():fin+=1
                while fin<len(sql) and not sql[fin].isspace() and sql[fin] not in ',)':fin+=1
            partes.extend([sql[inicio:i],'DEFAULT [VALOR OMITIDO]']);i=fin;inicio=fin
        else:i+=1
    partes.append(sql[inicio:]);return _redactar(''.join(partes))


def unidades(p,item,tope,control=None):
    def comprobar():
        if control:control()
    def avisar(texto):
        if texto not in item.get('aviso',''):item['aviso']=(item.get('aviso','')+' '+texto).strip()
    with abrir(p,control) as db:
        try:db.execute("SELECT octet_length('')").fetchone()
        except sqlite3.OperationalError:
            avisar('Esta versión de SQLite no permite muestras acotadas por bytes; solo esquema. Actualiza el runtime de Python para habilitarlas.')
            total=0
            for nombre,sql in db.execute("SELECT substr(name,1,1000),substr(sql,1,4000) FROM sqlite_schema WHERE type='table' ORDER BY name LIMIT 100"):
                comprobar();texto=_esquema_seguro(sql);restante=tope-total
                if restante<=0:item['cortado']=True;return
                yield item['nombre']+' · tabla '+nombre,texto[:restante];total+=len(texto)
                if len(texto)>restante:item['cortado']=True;return
            return
        tablas=db.execute("SELECT CASE WHEN octet_length(name)<=4096 THEN name ELSE NULL END,CASE WHEN octet_length(sql)<=65536 THEN sql ELSE NULL END FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT 101").fetchall()
        if len(tablas)>100:item['cortado']=True
        nombres={n for n,_ in tablas[:100] if n is not None};sin_rowid={};virtuales=set()
        for _,nombre,tipo,_,wr,_ in db.execute('PRAGMA table_list'):
            comprobar()
            if nombre in nombres:
                sin_rowid[nombre]=bool(wr)
                if tipo=='virtual':virtuales.add(nombre)
        enc=db.execute('PRAGMA encoding').fetchone()[0].replace('UTF-','utf-').lower()
        total=0
        for nombre,sql in tablas[:100]:
            comprobar();restante=tope-total
            if restante<=0:item['cortado']=True;return
            if nombre is None:
                aviso='Nombre de tabla mayor de4096 bytes omitido; no consulté sus filas.'
                avisar(aviso);t=aviso[:restante];yield item['nombre']+' · tabla omitida',t;total+=len(t);continue
            ref=item['nombre']+' · tabla '+nombre;ident=_identificador(nombre)
            if sql is None:
                aviso='Esquema mayor de65536 bytes omitido; no evalué la tabla.'
                avisar(aviso);t=aviso[:restante];yield ref,t;total+=len(t);continue
            esquema='Esquema: '+_esquema_seguro(sql)+'\n'
            if nombre in virtuales:
                aviso='Tabla virtual: solo esquema, no consulté sus filas.'
                avisar(aviso);t=(esquema+aviso)[:restante];yield ref,t;total+=len(t);continue
            if len(esquema)+len('Muestra (hasta 20 filas):\n')>=restante:
                item['cortado']=True;yield ref,esquema[:restante];return
            info=db.execute('PRAGMA table_xinfo('+ident+')').fetchall()
            columnas=[x for x in info if x[6] in {0,3}]
            if any(x[6] not in {0,3} for x in info):avisar('Columnas virtuales u ocultas omitidas; no calculé expresiones del adjunto.')
            ocupados={x[1].casefold() for x in info}
            alias=next((n for n in ('rowid','_rowid_','oid') if n not in ocupados),None) if not sin_rowid.get(nombre,True) else None
            rid=_identificador(alias) if alias else 'NULL'
            origen=' FROM '+ident+' NOT INDEXED'
            # NOT INDEXED conserva el recorrido físico entre columnas incluso
            # cuando todos los alias de rowid están ocupados; BEGIN fija snapshot.
            ids=[r[0] for r in db.execute('SELECT '+rid+origen+' LIMIT 20')]
            muestras=[[] for _ in ids];usado=len(esquema)+len('Muestra (hasta 20 filas):\n');agotado=False
            for c in columnas:
                comprobar();col=c[1]
                if SENSIBLE.search(col):valores=['[REDACTADO]']*len(ids)
                else:
                    q=_identificador(col)
                    consulta=('SELECT '+rid+',typeof('+q+'),octet_length('+q+'),CASE WHEN typeof('+q+")='blob' THEN NULL WHEN octet_length("+q+')<=65536 THEN '+q+' ELSE NULL END'+origen+' LIMIT 20')
                    valores=[]
                    for i,(fila,tipo,tamano,valor) in enumerate(db.execute(consulta)):
                        comprobar()
                        if i>=len(ids) or fila!=ids[i]:raise ValueError('La muestra SQLite cambió de filas durante la lectura.')
                        if tipo=='blob':v=f'[BLOB {tamano} bytes]'
                        elif tipo=='text' and tamano>MAX_CELDA:
                            if alias is None:
                                v=f'[TEXTO OMITIDO: {tamano} bytes, lectura por partes no disponible]'
                                avisar('El formato de esta tabla no permite leer por partes su texto extenso; se omite esa celda.')
                            else:
                                try:
                                    with db.blobopen(nombre,col,fila,readonly=True) as celda:raw=celda.read(MAX_CELDA)
                                    v=_redactar_celda(codecs.getincrementaldecoder(enc)(errors='replace').decode(raw,final=False))
                                except sqlite3.Error:
                                    v='[TEXTO OMITIDO: lectura incremental no disponible]'
                                    avisar('Una celda extensa no admite lectura incremental; no usé carga completa como alternativa.')
                        else:v=_redactar_celda(str(valor))
                        valores.append(v)
                    if len(valores)!=len(ids):raise ValueError('La muestra SQLite no confirmó todas sus filas.')
                for fila,v in zip(muestras,valores):
                    if usado+len(v)+3>restante:agotado=True;break
                    fila.append(v);usado+=len(v)+3
                if agotado:break
            t=esquema+'Muestra (hasta 20 filas):\n'+''.join(' | '.join(fila)+'\n' for fila in muestras)
            if agotado or len(t)>restante:item['cortado']=True
            yield ref,t[:restante];total+=len(t)
            if agotado or len(t)>restante:return
        avisar('Solo esquema y muestra; no representa todas las filas de la base.')
        avisar('Texto: hasta 1000 caracteres por celda, lectura por partes de hasta 64 KiB. Los binarios se describen por su tamaño y los campos sensibles se ocultan sin leer su contenido.')
