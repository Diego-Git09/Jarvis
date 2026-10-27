"""600 peticiones reales al generador local de Jarvis; todo el trabajo en carpetas temporales.

Ejecutar expresamente: python3 herramientas/evaluar_desarrollo_600.py --sesiones 60
No llama a servicios externos ni guarda conversaciones de pruebas en Segundo Cerebro.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


FRASES = ['Genera {f}', 'Jarvis, modifica {f} porfa', 'Cambia {f}', 'Corrige {f}',
          'Actualiza {f}', 'Arregla {f} po', 'Mejora {f}', 'Implementa {f}',
          'Repara {f}', 'Añade el cambio a {f}']


def python_caso(familia, valor):
    if familia == 0:
        objetivo = f'resolver(importe) devuelve round(importe * (1 + {valor}/100), 2); no modifica argumentos.'
        casos = [([x], round(x*(1+valor/100), 2)) for x in [0, 1, 100, -10, 123.45]]
    elif familia == 1:
        objetivo = f'resolver(valores) conserva y ordena los números mayores o iguales a {valor}, incluyendo repetidos.'
        casos = [([x], sorted(v for v in x if v >= valor)) for x in [[], [1,2,20,-5], [valor, valor, valor-1]]]
    elif familia == 2:
        objetivo = f'resolver(palabras) devuelve las palabras únicas, quitando espacios y pasando a minúsculas, de longitud >= {valor}; orden alfabético.'
        casos = [([x], sorted({v.strip().lower() for v in x if len(v.strip())>=valor})) for x in [[], [' Hola ', 'hola',' SQL ','python','a'], ['x'*valor, 'x'*valor]]]
    elif familia == 3:
        objetivo = f'resolver(texto) devuelve diccionario de frecuencias de palabras separadas por espacios, en minúsculas y de longitud >= {valor}.'
        from collections import Counter
        casos = [([x], dict(Counter(w for w in x.lower().split() if len(w)>=valor))) for x in ['', 'SQL sql Python python py', 'hola hola buenos dias', 'x'*valor]]
    elif familia == 4:
        objetivo = f'resolver(fecha) recibe fecha ISO YYYY-MM-DD y devuelve ISO de la fecha {valor} días después. Incluye cruces de año y bisiestos.'
        casos = [([x], (datetime.fromisoformat(x)+timedelta(days=valor)).date().isoformat()) for x in ['2024-02-28','2026-12-31','2000-02-29']]
    else:
        objetivo = f'resolver(csv_texto) suma enteros de columna monto que sean >= {valor}. CSV con encabezado nombre,monto; devuelve int y 0 si no hay filas.'
        casos = [(['nombre,monto\n'],0), (['nombre,monto\na,5\nb,20\nc,-3\n'],sum(x for x in [5,20,-3] if x>=valor))]
    return objetivo, casos


def sql_caso(familia, valor, etiqueta):
    filas=[(1,'norte',4),(2,'sur',10),(3,'norte',20)]
    base = ('SQLite. Crea tabla ventas(id INTEGER PRIMARY KEY, zona TEXT, monto INTEGER), '
            'con EXACTAMENTE filas (1,norte,4),(2,sur,10),(3,norte,20). '
            f'Crea tabla identidad(nombre TEXT) con una sola fila {etiqueta!r}; consérvala siempre. ')
    elegidas=[r for r in filas if r[2]>=valor]
    if familia==0:
        pedido=f'Vista resultado(id,monto) con ventas monto >= {valor}.'
        query='SELECT id,monto FROM resultado ORDER BY id'; esperado=[[r[0],r[2]] for r in elegidas]
    elif familia==1:
        pedido=f'Vista resultado(zona,total) con suma por zona de ventas monto >= {valor}.'
        query='SELECT zona,total FROM resultado ORDER BY zona'; esperado=[[z,sum(r[2] for r in elegidas if r[1]==z)] for z in sorted({r[1] for r in elegidas})]
    elif familia==2:
        pedido=f'Vista resultado(zona,cantidad) con cantidad por zona de ventas monto >= {valor}.'
        query='SELECT zona,cantidad FROM resultado ORDER BY zona'; esperado=[[z,sum(r[1]==z for r in elegidas)] for z in sorted({r[1] for r in elegidas})]
    elif familia==3:
        pedido=f'Vista resultado(zona,minimo) con mínimo por zona de ventas monto >= {valor}.'
        query='SELECT zona,minimo FROM resultado ORDER BY zona'; esperado=[[z,min(r[2] for r in elegidas if r[1]==z)] for z in sorted({r[1] for r in elegidas})]
    elif familia==4:
        pedido=f'Vista resultado(zona,maximo) con máximo por zona de ventas monto >= {valor}.'
        query='SELECT zona,maximo FROM resultado ORDER BY zona'; esperado=[[z,max(r[2] for r in elegidas if r[1]==z)] for z in sorted({r[1] for r in elegidas})]
    else:
        pedido=(f'Crea tabla zonas(zona TEXT PRIMARY KEY, nombre TEXT) con (norte,Norte),(sur,Sur). '
                f'Vista resultado(id,nombre) con JOIN de ventas y zonas, para monto >= {valor}.')
        query='SELECT id,nombre FROM resultado ORDER BY id'; esperado=[[r[0],r[1].title()] for r in elegidas]
    return base+pedido,[{'consulta':query,'esperado':esperado}, {'consulta':'SELECT nombre FROM identidad','esperado':[[etiqueta]]}, {'consulta':'SELECT count(*) FROM ventas','esperado':[[3]]}]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sesiones',type=int,default=60)
    parser.add_argument('--iniciar',type=int,default=0)
    parser.add_argument('--modelo',default='qwen3:8b')
    parser.add_argument('--modelo-correccion',default='',help='Otro modelo local para el segundo intento; no aumenta el límite de dos propuestas.')
    parser.add_argument('--sesiones-lista',help='Repetir sesiones concretas, por ejemplo 5,7,17; conserva las diez peticiones de cada sesión.')
    parser.add_argument('--continuar',action='store_true',help='Conservar auditoría y retomar solo las peticiones pendientes.')
    parser.add_argument('--informe',default='registros/reportes/desarrollo_600_2026-10-13')
    args=parser.parse_args()
    if not 1<=args.sesiones<=60:parser.error('sesiones debe ser entre 1 y 60')
    try:sesiones=[int(x) for x in args.sesiones_lista.split(',')] if args.sesiones_lista else list(range(args.iniciar,args.iniciar+args.sesiones))
    except ValueError:parser.error('sesiones-lista necesita números separados por coma')
    if not sesiones or len(sesiones)>60 or any(x<0 or x>599 for x in sesiones) or len(set(sesiones))!=len(sesiones):parser.error('Sesiones inválidas, repetidas o demasiadas.')
    informe=Path(args.informe).resolve();informe.parent.mkdir(parents=True,exist_ok=True)
    inicio=time.monotonic();filas=[];llamadas=0;segundos_anteriores=0
    if args.continuar:
        filas=[json.loads(l) for l in informe.with_suffix('.jsonl').read_text().splitlines() if l.strip()]
        anterior=json.loads(informe.with_suffix('.json').read_text())
        if anterior['modelo']!=args.modelo:parser.error('El modelo de la auditoría no coincide.')
        if anterior.get('modelo_correccion','')!=args.modelo_correccion:parser.error('El modelo de corrección de la auditoría no coincide.')
        segundos_anteriores=anterior.get('segundos',0);llamadas=sum(len(f['llamadas']) for f in filas)
    previas={(f['sesion'],f['turno']):f for f in filas}
    if len(previas)!=len(filas):parser.error('La auditoría contiene peticiones repetidas; revísala antes de continuar.')
    with tempfile.TemporaryDirectory(prefix='jarvis-600-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1',PYTHONDONTWRITEBYTECODE='1')
        from entorno_jarvis import TRABAJO
        TRABAJO.mkdir();import proyectos_codigo as P;import cliente_ollama as O
        def si(_):return True  # Únicamente proyectos sintéticos de este TemporaryDirectory.
        with informe.with_suffix('.jsonl').open('a' if args.continuar else 'w',encoding='utf-8') as auditoria:
            for sesion in sesiones:
                if all((sesion,t) in previas for t in range(10)):continue
                lenguaje='python' if sesion%2==0 else 'sql';familia=(sesion//2)%6
                nombre=f'Caso_{sesion}_{lenguaje}';archivo='logica.py' if lenguaje=='python' else 'datos.sql';raiz=TRABAJO/nombre
                inicial=P.ejecutar('iniciar_proyecto_codigo',{'nombre':nombre,'ruta':str(raiz),'objetivo':f'Desarrollo {lenguaje} con cambios de requisitos; conservar etiqueta de proyecto {nombre} y la función/vista resolver/resultado.'},si,{})
                assert inicial['ok'],inicial
                assert P.ejecutar('actualizar_plan_codigo',{'etapas_json':json.dumps([{'titulo':'Lógica con pruebas de regresión','archivos':[archivo]}])},si,{})['ok']
                for turno in range(10):
                    valor=(sesion//12)+turno+1
                    if lenguaje=='python':
                        requisito,casos=python_caso(familia,valor)
                        requisito+=f' Además etiqueta() devuelve exactamente {nombre!r}; no elimines esa función.'
                        pruebas=('import unittest\nfrom logica import resolver, etiqueta\n'
                                 'class Contrato(unittest.TestCase):\n'
                                 f' def test_identidad(self): self.assertEqual(etiqueta(),{nombre!r})\n')
                        for k,(argumentos,esperado) in enumerate(casos):pruebas+=f' def test_caso_{k}(self): self.assertEqual(resolver(*{argumentos!r}),{esperado!r})\n'
                        (raiz/'test_logica.py').write_text(pruebas)
                    else:
                        requisito,casos=sql_caso(familia,valor,nombre)
                        (raiz/'pruebas_sql.json').write_text(json.dumps(casos))
                    if (sesion,turno) in previas:
                        # Recuperar únicamente el estado sintético de una sesión
                        # parcial a partir de sus respuestas ya auditadas. No se
                        # vuelve a llamar al modelo ni se alteran sus resultados.
                        previa=previas[(sesion,turno)]
                        for llamada in previa['llamadas']:
                            try:generado=json.loads(llamada['respuesta_modelo'])
                            except (ValueError,TypeError):continue
                            contenido=generado.get('contenido') if isinstance(generado,dict) else None
                            if not isinstance(contenido,str) or llamada.get('fin')=='length':continue
                            state={}
                            if (raiz/archivo).exists():state['_codigo_archivos_leidos']={str(raiz/archivo):hashlib.sha256((raiz/archivo).read_bytes()).hexdigest()}
                            P.ejecutar('escribir_archivo_codigo',{'ruta':archivo,'contenido':contenido},si,state)
                        if previa['ok']:P.ejecutar('validar_proyecto_codigo',{'modo':'tests_python' if lenguaje=='python' else 'tests_sql'},si,{})
                        else:P.ejecutar('registrar_error_codigo',{'error':previa['error'][-4000:] or 'Caso anterior pendiente'},si,{})
                        continue
                    if turno in {3,7} and (raiz/archivo).exists():
                        viejo=(raiz/archivo).read_text()
                        (raiz/archivo).write_text(viejo+('\nfallo_inyectado=variable_inexistente\n' if lenguaje=='python' else '\nSELECT variable_inexistente FROM ventas;\n'))
                        P.ejecutar('validar_proyecto_codigo',{'modo':'tests_python' if lenguaje=='python' else 'tests_sql'},si,{})
                    pedido=FRASES[turno].format(f=archivo)+'. '+requisito
                    if turno in {4,8}:pedido+=' Retomamos después de cerrar el chat: usa el proyecto y archivos reales guardados.'
                    auditoria_llamadas=[]
                    def enviar(endpoint,payload,**kw):
                        nonlocal llamadas
                        respuesta=O.solicitar(endpoint,payload,**kw);llamadas+=1
                        auditoria_llamadas.append({'numero':llamadas,'modelo':payload['model'],'tokens_entrada':respuesta.get('prompt_eval_count'),'tokens_salida':respuesta.get('eval_count'),'respuesta_modelo':respuesta.get('message',{}).get('content'),'fin':respuesta.get('done_reason')})
                        return respuesta
                    antes=time.monotonic();respuesta='';error=''
                    try:
                        respuesta=P.desarrollar(pedido,{},si,enviar,args.modelo,modelo_alternativo=args.modelo_correccion) or 'No entró al generador'
                        est=P.estado(P.activo());ok=bool(est['validacion_vigente'] and not est['error_pendiente'] and auditoria_llamadas)
                        if not ok:error=est['error_pendiente'] or respuesta
                    except Exception as exc:ok=False;error=type(exc).__name__+': '+str(exc)
                    fila={'sesion':sesion,'turno':turno,'lenguaje':lenguaje,'familia':familia,'pedido':pedido,'ok':ok,'error':error,'segundos':round(time.monotonic()-antes,3),'llamadas':auditoria_llamadas,'respuesta_jarvis':respuesta}
                    filas.append(fila);auditoria.write(json.dumps(fila,ensure_ascii=False)+'\n');auditoria.flush()
                    resumen={'fecha':datetime.now(timezone.utc).isoformat(),'modelo':args.modelo,'modelo_correccion':args.modelo_correccion,'sesiones':len(sesiones),'sesiones_elegidas':sesiones,'peticiones':len(filas),'llamadas_reales':llamadas,'correctas':sum(f['ok'] for f in filas),'fallidas':sum(not f['ok'] for f in filas),'segundos':round(segundos_anteriores+time.monotonic()-inicio,2),'reanuda_auditoria':args.continuar,'fallos':[{'sesion':f['sesion'],'turno':f['turno'],'error':f['error'][:1200]} for f in filas if not f['ok']],'aislamiento':'JARVIS_PRUEBAS=1, JARVIS_DIR temporal; sin SC ni proveedores externos','alcance':'Generador de archivos real de Jarvis, Qwen local, unittest y SQLite con contratos; no equivale a 600 pruebas de toda la interfaz/conversación libre.'}
                    informe.with_suffix('.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2))
                    if len(filas)%10==0:print(json.dumps({k:resumen[k] for k in ['peticiones','llamadas_reales','correctas','fallidas','segundos']}),flush=True)
    return 0 if all(f['ok'] for f in filas) else 1


if __name__=='__main__':raise SystemExit(main())
