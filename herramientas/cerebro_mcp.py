"""Cliente MCP HTTP local. No repite escrituras ante fallos de conexión."""
import json
import urllib.error
import urllib.request
from entorno_jarvis import en_pruebas

URL_MCP = 'http://127.0.0.1:8765/mcp'
VERSION = '2025-06-18'
MAX_BYTES = 32_000_000
LECTURAS = {'buscar_memoria', 'buscar_memoria_semantica', 'listar_memorias',
            'consultar_estado_cerebro', 'consultar_memoria', 'listar_proyectos',
            'consultar_ultimo_recuerdo', 'consultar_ultima_conversacion'}
PERMITIDAS = LECTURAS | {'corregir_memoria', 'olvidar_memoria', 'clasificar_memoria', 'crear_proyecto'}


class ErrorCerebro(ConnectionError):
    pass


class ClienteCerebro:
    def __init__(self, url=URL_MCP, timeout=30):
        self.url, self.timeout = url, timeout
        self.sesion = None
        self.version = VERSION
        self.iniciado = False
        self.numero = 0
        self.abrir = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

    def _enviar(self, metodo, params=None, notificacion=False):
        if en_pruebas() and self.url == URL_MCP:
            raise ErrorCerebro('Las pruebas tienen bloqueado el MCP real; usa un cliente falso o un servidor temporal.')
        self.numero += 1
        ident = self.numero
        cuerpo = {'jsonrpc': '2.0', 'method': metodo}
        if not notificacion:
            cuerpo['id'] = ident
        if params is not None:
            cuerpo['params'] = params
        cab = {'Content-Type': 'application/json',
               'Accept': 'application/json, text/event-stream'}
        if self.iniciado:
            cab['MCP-Protocol-Version'] = self.version
        if self.sesion:
            cab['Mcp-Session-Id'] = self.sesion
        req = urllib.request.Request(self.url, data=json.dumps(cuerpo).encode(), headers=cab)
        with self.abrir(req, timeout=self.timeout) as r:
            if metodo == 'initialize':
                self.sesion = r.headers.get('Mcp-Session-Id')
            if notificacion:
                return None
            if 'text/event-stream' in r.headers.get('Content-Type', ''):
                data, total = [], 0
                respuesta = None
                while True:
                    linea = r.readline(MAX_BYTES + 1)
                    total += len(linea)
                    if total > MAX_BYTES:
                        raise ErrorCerebro('Respuesta de memoria demasiado grande.')
                    if not linea or not linea.strip():
                        if data:
                            respuesta = json.loads('\n'.join(data))
                            if isinstance(respuesta, dict) and respuesta.get('id') == ident:
                                break
                            data = []
                        if not linea:
                            raise ErrorCerebro('El servidor cerró la respuesta sin resultado.')
                    elif linea.startswith(b'data:'):
                        data.append(linea[5:].decode('utf-8').lstrip(' ').rstrip('\r\n'))
            else:
                raw = r.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ErrorCerebro('Respuesta de memoria demasiado grande.')
                respuesta = json.loads(raw)
        if not isinstance(respuesta, dict) or respuesta.get('id') != ident:
            raise ErrorCerebro('Respuesta MCP no válida.')
        if 'error' in respuesta:
            error = respuesta.get('error')
            codigo = error.get('code') if isinstance(error, dict) else None
            detalle = f' (código {codigo})' if isinstance(codigo, int) else ''
            raise ErrorCerebro('El servidor MCP rechazó la llamada' + detalle + '.')
        if 'result' not in respuesta:
            raise ErrorCerebro('Respuesta MCP sin resultado.')
        return respuesta['result']

    def _iniciar(self):
        self.sesion = None
        self.iniciado = False
        r = self._enviar('initialize', {'protocolVersion': VERSION, 'capabilities': {},
             'clientInfo': {'name': 'jarvis', 'version': '0.3'}})
        self.version = r['protocolVersion']
        if self.version not in {VERSION, '2025-03-26'}:
            raise ErrorCerebro('Versión MCP no compatible.')
        self.iniciado = True
        self._enviar('notifications/initialized', notificacion=True)

    def llamar(self, nombre, argumentos):
        if nombre not in PERMITIDAS:
            raise ErrorCerebro('Herramienta de memoria no permitida.')
        try:
            if not self.iniciado:
                self._iniciar()
            try:
                resultado = self._enviar('tools/call', {'name': nombre, 'arguments': argumentos})
            except urllib.error.HTTPError as e:
                e.close()
                if e.code != 404:
                    raise ErrorCerebro(f'El servidor MCP respondió HTTP {e.code}.') from e
                self.iniciado = False
                self._iniciar()
                resultado = self._enviar('tools/call', {'name': nombre, 'arguments': argumentos})
            return normalizar(resultado)
        except ErrorCerebro:
            raise
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
            self.iniciado = False
            raise ErrorCerebro('No pude completar la llamada al Segundo Cerebro. '
                               'Revisa http://127.0.0.1:8767. '
                               'Si era un cambio, consulta el recuerdo antes de repetirlo.') from e

    def guardar_conversacion(self, proyecto, titulo, contenido, clave, sesion='', creado=''):
        """Escritura interna idempotente; no forma parte de las herramientas del modelo."""
        if not all(isinstance(x, str) and x.strip() for x in (proyecto, titulo, contenido, clave)):
            raise ErrorCerebro('No pude guardar la conversación: faltan datos.')
        try:
            if not self.iniciado:
                self._iniciar()
            parametros = {'name': 'guardar_conversacion', 'arguments': {
                'proyecto': proyecto, 'titulo': titulo, 'contenido': contenido, 'clave': clave}}
            if sesion:parametros['arguments']['sesion']=sesion
            if creado:parametros['arguments']['creado']=creado
            try:
                bruto = self._enviar('tools/call', parametros)
            except urllib.error.HTTPError as e:
                e.close()
                if e.code != 404:
                    raise ErrorCerebro(f'El servidor MCP respondió HTTP {e.code}.') from e
                # La clave idempotente permite repetir con seguridad solo este error de sesión.
                self.iniciado = False
                self._iniciar()
                bruto = self._enviar('tools/call', parametros)
            resultado = normalizar(bruto)
            if not resultado.get('ok') or resultado.get('tipo') != 'conversacion':
                raise ErrorCerebro('Segundo Cerebro no confirmó el guardado completo.')
            return resultado
        except ErrorCerebro:
            raise
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError) as e:
            self.iniciado = False
            raise ErrorCerebro('No pude confirmar el guardado. La conversación seguirá en la cola local; revisa http://127.0.0.1:8767.') from e

    def publicar_documento(self,titulo,contenido,actualizar=False):
        """Solo documentación Jarvis autorizada por /estado_ia; no se anuncia al modelo."""
        import hashlib,re
        contenido=contenido.strip()  # Contrato publicado de guardar_memoria normaliza extremos.
        if not titulo.startswith('JARVIS — ') or not contenido.strip() or len(contenido)>8000:raise ValueError('Documento de estado inválido.')
        fijo='JARVIS — Estado actual (resumen para IA)'
        if actualizar and titulo!=fijo:raise ValueError('Solo se actualiza el resumen fijo autorizado.')
        def consultar_documento(ident):
            filas=self.llamar('consultar_memoria',{'id_memoria':ident}).get('memorias')
            if not isinstance(filas,list) or len(filas)!=1 or not isinstance(filas[0],dict):
                raise ErrorCerebro('La consulta del documento no devolvió un único recuerdo verificable.')
            m=filas[0]
            if m.get('id')!=ident or m.get('proyecto')!='Jarvis' or m.get('titulo')!=titulo or m.get('tipo','recuerdo')!='recuerdo' or not isinstance(m.get('contenido'),str):
                raise ErrorCerebro('El documento cambió de identidad, proyecto, título o tipo; no actualicé otro recuerdo.')
            return m
        if actualizar:
            candidatos=[]
            for offset in range(0,10000,100):
                pagina=self.llamar('listar_memorias',{'proyecto':'Jarvis','desplazamiento':offset,'limite':100}).get('memorias',[])
                candidatos.extend(m for m in pagina if m.get('titulo')==titulo and m.get('proyecto')=='Jarvis' and m.get('tipo','recuerdo')=='recuerdo')
                if len(pagina)<100:break
            else:raise ErrorCerebro('El proyecto excede el límite de búsqueda del resumen; no creé otra copia.')
        else:candidatos=[m for m in self.llamar('buscar_memoria',{'proyecto':'Jarvis','consulta':titulo}).get('memorias',[]) if m.get('titulo')==titulo and m.get('proyecto')=='Jarvis']
        if len(candidatos)>1:raise ErrorCerebro('Hay varios resúmenes con el mismo título; selecciona uno antes de actualizar.')
        if candidatos:
            ident=candidatos[0]['id'];m=consultar_documento(ident)
            if m['contenido']!=contenido:
                if not actualizar:raise ErrorCerebro('Existe otro documento con igual título; no lo sobrescribí.')
                r=self.llamar('corregir_memoria',{'id_memoria':ident,'contenido_esperado':m['contenido'],'contenido_nuevo':contenido})
                if not r.get('ok'):raise ErrorCerebro('No se confirmó la actualización del resumen.')
        else:
            if not self.iniciado:self._iniciar()
            bruto=self._enviar('tools/call',{'name':'guardar_memoria','arguments':{'proyecto':'Jarvis','titulo':titulo,'contenido':contenido}})
            if bruto.get('isError'):raise ErrorCerebro('No se confirmó la publicación.')
            d=bruto.get('structuredContent')
            texto=d.get('result','') if isinstance(d,dict) else '\n'.join(x.get('text','') for x in bruto.get('content',[]))
            match=re.search(r'Memoria guardada\. ID: (\d+)',texto)
            if not match:raise ErrorCerebro('Resultado de publicación incierto; consultar antes de repetir.')
            ident=int(match[1])
        guardado=consultar_documento(ident)
        if guardado.get('id')!=ident or guardado.get('proyecto')!='Jarvis' or guardado.get('titulo')!=titulo or guardado.get('tipo','recuerdo')!='recuerdo' or guardado.get('contenido')!=contenido:
            raise ErrorCerebro('La lectura posterior no coincide con el documento.')
        return {'id':ident,'titulo':titulo,'sha256':hashlib.sha256(contenido.encode()).hexdigest(),'verificado':True}


def normalizar(resultado):
    if not isinstance(resultado, dict):
        raise ErrorCerebro('Resultado MCP no válido.')
    if resultado.get('isError'):
        return {'ok': False, 'error': 'Segundo Cerebro rechazó la operación.'}
    dato = resultado.get('structuredContent')
    if dato is None:
        textos = [p.get('text', '') for p in resultado.get('content', []) if p.get('type') == 'text']
        try:
            dato = json.loads('\n'.join(textos))
        except ValueError:
            raise ErrorCerebro('Resultado de memoria no reconocido.')
    if isinstance(dato, dict) and set(dato) == {'memorias'}:
        dato = dato['memorias']
    if isinstance(dato, dict) and set(dato) == {'result'}:
        dato = dato['result']
    if isinstance(dato, list):
        return {'ok': True, 'memorias': dato}
    if isinstance(dato, dict):
        if dato.get('estado') == 'no_encontrada':
            return {'ok': False, 'error': 'Todavía no hay registros de ese tipo.'}
        if dato.get('estado') == 'conflicto':
            return {'ok': False, 'error': 'El contenido cambió desde la consulta. Vuelve a abrir el recuerdo.'}
        return {'ok': True, **dato}
    raise ErrorCerebro('Resultado de memoria no reconocido.')
