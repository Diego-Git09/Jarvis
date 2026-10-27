"""Rúbricas y 1200 casos nuevos; se materializan antes de consultar ningún modelo."""
import json
import hashlib
from pathlib import Path
from collections import Counter

def python(i):
    v=i%20+2;f=i//20
    if f==0:desc=f'resolver(datos) limita cada entero al intervalo [-{v},{v}], conservando orden';datos=[[],[-100,0,100],[v,v+1,-v-1]];func=lambda d:[max(-v,min(v,x)) for x in d]
    elif f==1:desc=f'resolver(datos) devuelve sumas acumuladas más {v} en cada posición';datos=[[],[1,2,-1],[0,0]];func=lambda d:[sum(d[:n+1])+v for n in range(len(d))]
    elif f==2:desc='resolver(datos) intercambia claves y valores de un diccionario; si valores repetidos conserva la última clave';datos=[{}, {'a':1,'b':2},{'a':1,'b':1}];func=lambda d:{b:a for a,b in d.items()}
    elif f==3:desc=f'resolver(datos) devuelve pares [posición,valor] para valores divisibles por {v}, conservando orden';datos=[[],[0,v,v+1,-v],[3,5,8]];func=lambda d:[[n,x] for n,x in enumerate(d) if x%v==0]
    elif f==4:desc='resolver(datos) devuelve True si todos los paréntesis están balanceados; ignora otros caracteres';datos=['','()','(()','a(b)c',')('];func=lambda d:balance(d)
    elif f==5:desc=f'resolver(datos) quita duplicados conservando primera aparición y rota a la izquierda {v} posiciones módulo longitud; vacío devuelve []';datos=[[],[1,2,1,3],[9]];func=lambda d:rotar(d,v)
    elif f==6:desc=f'resolver(datos) devuelve lista de palabras PALÍNDROMAS (igual al invertir), minúsculas, sin duplicados y ordenadas, longitud >= {v}; no quita tildes';datos=[[],['ANA','reconocer','ana','Python','oso'],['x'*v]];func=lambda d:sorted({w.lower() for w in d if len(w)>=v and w.lower()==w.lower()[::-1]})
    elif f==7:desc=f'resolver(datos) suma {v} minutos a una hora HH:MM y devuelve HH:MM, con vuelta de 24h';datos=['00:00','23:59','12:30'];func=lambda d:f'{((int(d[:2])*60+int(d[3:])+v)//60)%24:02d}:{(int(d[:2])*60+int(d[3:])+v)%60:02d}'
    elif f==8:desc=f'resolver(datos) agrupa pares [clave,valor], suma valores por clave y añade {v} una sola vez a cada total';datos=[[],[['a',1],['b',2],['a',3]],[['x',-1]]];func=lambda d:{k:sum(x[1] for x in d if x[0]==k)+v for k in {x[0] for x in d}}
    else:desc=f'resolver(datos) devuelve las palabras cuya frecuencia es exactamente {v}, en minúsculas y orden alfabético';datos=['',' '.join(['hola']*v+['x']),'a a b b b'];func=lambda d:sorted(k for k,n in Counter(d.lower().split()).items() if n==v)
    return desc,[[[d],func(d)] for d in datos]

def balance(t):
    n=0
    for x in t:
        if x=='(':n+=1
        if x==')':n-=1
        if n<0:return False
    return n==0
def rotar(d,v):
    u=list(dict.fromkeys(d))
    if not u:return []
    n=v%len(u);return u[n:]+u[:n]

def sql(i):
    v=i%20+2;f=i//20
    base="SQLite: crea ventas(id INTEGER PRIMARY KEY,zona TEXT,monto INTEGER) con (1,'norte',5),(2,'sur',NULL),(3,'norte',17),(4,'sur',3). Crea identidad(nombre TEXT) con una sola fila 'NUEVO_SQL_"+str(i)+"'. "
    if f==0:desc=f'Vista resultado(id,valor): COALESCE(monto,0)+{v} para todas las ventas.';query='SELECT id,valor FROM resultado ORDER BY id';rows=[[1,5+v],[2,v],[3,17+v],[4,3+v]]
    elif f==1:desc=f'Vista resultado(id,total): suma acumulada de COALESCE(monto,0) por id más {v}.';query='SELECT id,total FROM resultado ORDER BY id';rows=[[1,5+v],[2,5+v],[3,22+v],[4,25+v]]
    elif f==2:desc=f'Vista resultado(zona,total): zonas cuya suma de montos >= {v}, usando HAVING.';query='SELECT zona,total FROM resultado ORDER BY zona';rows=[[z,m] for z,m in [('norte',22),('sur',3)] if m>=v]
    elif f==3:desc='Vista resultado(id): ventas donde monto es NULL.';query='SELECT id FROM resultado ORDER BY id';rows=[[2]]
    elif f==4:desc=f'Vista resultado(zona,cantidad): cuenta montos NO NULOS menores que {v}, incluye zonas con cero.';query='SELECT zona,cantidad FROM resultado ORDER BY zona';rows=[['norte',int(5<v)+int(17<v)],['sur',int(3<v)]]
    elif f==5:desc=f'Vista resultado(id): ventas con monto mayor que la media NO NULA de su zona y monto >= {v}.';query='SELECT id FROM resultado ORDER BY id';rows=[[3]] if 17>=v else []
    elif f==6:desc="Crea zonas(nombre TEXT PRIMARY KEY) con ('norte'),('sur'),('este'). Vista resultado(zona,cantidad): LEFT JOIN con todas las zonas, cuenta ventas incluyendo montos NULL.";query='SELECT zona,cantidad FROM resultado ORDER BY zona';rows=[['este',0],['norte',2],['sur',2]]
    elif f==7:desc=f'Vista resultado(id,orden): número de fila por zona según id más {v}.';query='SELECT id,orden FROM resultado ORDER BY id';rows=[[1,1+v],[2,1+v],[3,2+v],[4,2+v]]
    elif f==8:desc=f'Vista resultado(id,clase): CASE: NULL es ausente, monto >= {v} es alto, resto bajo.';query='SELECT id,clase FROM resultado ORDER BY id';rows=[[n,'ausente' if m is None else 'alto' if m>=v else 'bajo'] for n,m in [(1,5),(2,None),(3,17),(4,3)]]
    else:desc=f'Vista resultado(id): últimas {v%3+1} ventas por id descendente con monto NO NULO.';query='SELECT id FROM resultado ORDER BY id DESC';rows=[[n] for n in [4,3,1][:v%3+1]]
    return base+desc,[{'consulta':query,'esperado':rows},{'consulta':'SELECT nombre FROM identidad','esperado':[['NUEVO_SQL_'+str(i)]]},{'consulta':'SELECT count(*) FROM ventas','esperado':[[4]]}]

def jvm(i):
    v=i%20+2;f=i//20;datos=[[],[1,-2,3,3,10],[v,v+1,-v],[0,0,0],[5,-5]]
    if f==0:desc=f'suma de cuadrados de valores >= {v}; vacío 0';fn=lambda d:sum(x*x for x in d if x>=v)
    elif f==1:desc=f'cuenta cambios entre valores consecutivos cuya diferencia absoluta >= {v}; vacío 0';fn=lambda d:sum(abs(a-b)>=v for a,b in zip(d,d[1:]))
    elif f==2:desc=f'suma de valores multiplicados por su posición (base 1), más {v}; vacío {v}';fn=lambda d:sum((n+1)*x for n,x in enumerate(d))+v
    elif f==3:desc=f'cantidad de valores divisibles por {v}; incluye negativos y cero; vacío 0';fn=lambda d:sum(x%v==0 for x in d)
    elif f==4:desc=f'valor más cercano a {v}, empate el menor; vacío -777';fn=lambda d:min(d,key=lambda x:(abs(x-v),x)) if d else -777
    elif f==5:desc=f'cantidad de pares adyacentes cuya suma es > {v}; vacío 0';fn=lambda d:sum(a+b>v for a,b in zip(d,d[1:]))
    elif f==6:desc=f'suma de valores limitados a [-{v},{v}], conservando entrada';fn=lambda d:sum(max(-v,min(v,x)) for x in d)
    elif f==7:desc=f'primer índice (base cero) de valor > {v}; si ninguno -1';fn=lambda d:next((n for n,x in enumerate(d) if x>v),-1)
    elif f==8:desc=f'cantidad de valores negativos multiplicada por {v}; vacío 0';fn=lambda d:sum(x<0 for x in d)*v
    else:desc=f'diferencia máximo-mínimo más {v}; vacío {v}';fn=lambda d:max(d)-min(d)+v if d else v
    return desc,[[d,fn(d)] for d in datos]

UBUNTU=[('mostrar tamaño de cada carpeta sin borrar nada','du',r'\bdu\b'),('mostrar enlaces simbólicos de una carpeta','find',r'find.*-type\s+l'),('comprobar huella SHA256 de archivo sin ejecutarlo','sha256sum',r'sha256sum'),('mostrar tipo de archivo','file',r'\bfile\b'),('ver metadatos de archivo','stat',r'\bstat\b'),('consultar servicio fallido sin reiniciarlo','systemctl --failed',r'systemctl.*--failed'),('ver últimos 30 registros de un servicio','journalctl -n 30',r'journalctl.*(?:-n\s*30|--lines[= ]30)'),('listar unidades de almacenamiento sin formatear','lsblk',r'\blsblk\b'),('comprobar espacio de inodos sin borrar','df -i',r'\bdf\b.*-[a-z]*i'),('consultar versión kernel, no la distribución','uname -r',r'uname.*-r'),('mostrar primeras diez líneas sin editar','head -n 10',r'\bhead\b'),('mostrar últimas cinco líneas sin editar','tail -n 5',r'tail.*-n\s*5'),('buscar una palabra literal, no regex','rg -F',r'(?:rg|grep).*-(?:F|-[\w-]*fixed)'),('comparar texto de dos archivos sin cambiarlos','diff',r'\bdiff\b'),('buscar paquetes por nombre, sin instalar','apt search',r'apt(?:-cache)?\s+search'),('revisar la hora sin cambiarla','date',r'\bdate\b'),('ver permisos y dueño, sin chmod','ls -l',r'\bls\b.*-l'),('contar líneas de texto','wc -l',r'wc.*-l'),('buscar archivo por nombre sin borrarlo','find -name',r'find.*-name'),('ver variables PATH sin ejecutar programas','printf',r'\b(?:printf|echo)\b.*PATH')]

def construir():
    out=[]
    for c in ['python','sql','java','android','ubuntu','entrenamiento']:
        for i in range(200):
            d={'contexto':c,'id':i}
            if c=='python':p,pr=python(i);d.update(pedido='Genera logica.py: '+p+f'. Además etiqueta() devuelve exactamente NUEVO_PY_{i}. Conserva firma y no modifiques argumentos.',contratos=pr,contratos_repr=[repr(e) for _,e in pr],etiqueta='NUEVO_PY_'+str(i))
            elif c=='sql':p,pr=sql(i);d.update(pedido='Genera datos.sql. '+p,contratos=pr)
            elif c in {'java','android'}:
                p,pr=jvm(i);pref=f'public class Nuevo{i}, public static int resolver(int[] datos)' if c=='java' else f'Kotlin, objeto Nuevo{i} con fun resolver(datos: IntArray): Int'
                d.update(pedido=f'Genera SOLO código {pref}. Resultado: {p}. No imports, paquetes, E/S, procesos ni reflexión. Ejemplos: '+json.dumps(pr[:2]),contratos=pr)
            elif c=='ubuntu':p,esperado,patron=UBUNTU[i%20];d.update(pedido=f'Caso U_{i}: explícame cómo {p} en un archivo/carpeta ficticia "muestra_{i}". NO ejecutes, no uses sudo ni modifiques nada. Máximo dos líneas.',patron=patron,prohibido=r'(?i)(?:ejecut[eé]|modifiqu[eé]|borr[eé]|instal[eé])')
            else:
                escenarios=['retomar el caso de una tienda con cuatro accesos','una tanda de 100 PDF no cabe en contexto','un PDF escaneado no aporta texto','la preferencia SQL no debe cambiar Java','una prueba tiene cero tests ejecutados','el motor MySQL no está instalado','cayó MCP tras generar la respuesta','no quiero guardar esta práctica','el usuario dice sigamos después de una guía','no hay permiso para compilar'][i%10]
                d.update(pedido=f'Entrenamiento: {escenarios}. Conserva exactamente NUEVO_ENT_{i}. Di qué falta verificar o preguntar, sin afirmar acciones ya hechas. Máximo dos líneas.',patron=f'NUEVO_ENT_{i}',patron_adicional=r'(?i)(verific|comprob|pregunt|permiso|pendiente|no |falta)',prohibido=r'(?i)(?:ya (?:compil|ejecut|guard|instal)|he (?:compil|ejecut|instal))')
            out.append(d)
    return {'version':2,'rubrica':'Contratos funcionales exactos en Python/SQLite/JVM; regex explícitas y negativos para explicaciones. V2 corrige la serialización de claves enteras de diccionarios Python: JSON las transformaba en cadenas. Los valores esperados normativos y las peticiones no cambian; se conserva V1 y su auditoría. 200 casos por contexto; diez familias diferentes de las anteriores. Los casos varían parámetros y no son 1200 proyectos distintos.','casos':out}

def publicar(ruta):
    d=construir();p=Path(ruta);p.parent.mkdir(parents=True,exist_ok=True);raw=json.dumps(d,ensure_ascii=False,indent=2)+'\n';p.write_text(raw)
    return hashlib.sha256(raw.encode()).hexdigest()
if __name__=='__main__':print(publicar('registros/reportes/ampliacion_20261014/corpus_1200_previo.json'))
