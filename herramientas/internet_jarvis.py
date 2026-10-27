"""Consultas web públicas acotadas, sin cookies, JavaScript ni acceso a la red local."""
import http.client
import ipaddress
import re
import socket
import ssl
import time
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urljoin, urlencode
import xml.etree.ElementTree as ET
from lenguaje_jarvis import limpiar, normalizar

MAX_BYTES = 1_000_000


class ErrorHTTP(ConnectionError):
    """Conserva solo diagnóstico permitido; nunca el cuerpo HTTP ni las claves."""
    def __init__(self,codigo,datos=b'',retry_after=''):
        super().__init__(f'El servidor respondió HTTP {codigo}.')
        self.codigo=codigo;self.diagnostico={}
        try:
            import json
            d=json.loads(datos);e=d.get('error',{})
            if not isinstance(e,dict):return
            estado=e.get('status','')
            if estado in {'PERMISSION_DENIED','RESOURCE_EXHAUSTED','INVALID_ARGUMENT','UNAUTHENTICATED','NOT_FOUND','UNAVAILABLE'}:self.diagnostico['estado']=estado
            mensaje=str(e.get('message','')).casefold()
            if 'reported as leaked' in mensaje or 'key was leaked' in mensaje:self.diagnostico['causa']='clave_bloqueada'
            elif 'api key expired' in mensaje:self.diagnostico['causa']='clave_caducada'
            elif 'api key not valid' in mensaje or 'invalid api key' in mensaje:self.diagnostico['causa']='clave_invalida'
            elif 'api key service' in mensaje or 'requests from referer' in mensaje or 'requests from this' in mensaje:self.diagnostico['causa']='restricciones_clave'
            elif 'has not been used' in mensaje or 'service disabled' in mensaje:self.diagnostico['causa']='servicio_deshabilitado'
            if re.search(r'\blimit\s*:\s*0\b',mensaje):self.diagnostico['cuota_cero']=True
            detalles=e.get('details',[])
            for item in detalles if isinstance(detalles,list) else []:
                if not isinstance(item,dict):continue
                motivo=item.get('reason')
                if motivo in {'API_KEY_INVALID','API_KEY_SERVICE_BLOCKED','API_KEY_HTTP_REFERRER_BLOCKED','API_KEY_IP_ADDRESS_BLOCKED','SERVICE_DISABLED','CONSUMER_INVALID','BILLING_DISABLED'}:self.diagnostico['motivo']=motivo
                for v in item.get('violations',[]) if isinstance(item.get('violations'),list) else []:
                    if not isinstance(v,dict):continue
                    if str(v.get('quotaValue',''))=='0':self.diagnostico['cuota_cero']=True
                    metrica=str(v.get('quotaMetric',''))+str(v.get('quotaId',''))
                    if 'FreeTier' in metrica or 'free_tier' in metrica:self.diagnostico['nivel']='gratuito'
                    if 'PerDay' in metrica:self.diagnostico['periodo']='diario'
                    elif 'PerMinute' in metrica and self.diagnostico.get('periodo')!='diario':self.diagnostico['periodo']='por_minuto'
                demora=item.get('retryDelay','')
                if re.fullmatch(r'\d+(?:\.\d+)?s',str(demora)):self.diagnostico['espera_segundos']=min(86400,int(float(demora[:-1])+1))
        except (ValueError,TypeError,AttributeError):pass
        if str(retry_after).isdigit():self.diagnostico.setdefault('espera_segundos',min(86400,int(retry_after)))


def interpretar_busqueda(pregunta, compuestas=False):
    """Reconoce búsquedas públicas; conserva consultas y nombres tal como se escriben."""
    natural=limpiar(pregunta);n=normalizar(natural)
    if natural.startswith('/') or re.search(r'\b(?:no (?:busques|buscar|consultes|investigues)|sin (?:(?:usar|consultar) )?(?:internet|buscar|consultar)|solo local)\b',n):
        return None
    # Buscar una memoria o un archivo nunca implica enviarlo al buscador público.
    if re.search(r'\b(?:recuerdos?|memorias?|segundo cerebro|mis archivos|mis tareas|mis conversaciones|mis sesiones|mis proyectos)\b',n):
        return None
    if not compuestas and re.search(r'\b(?:y|luego|despues)\s+(?:luego\s+)?(?:crea|guarda|escribe|edita|mueve|copia|borra|clasifica|pregunta|preguntale|resume|compara|analiza|explica)\b',n):
        return None
    m=re.fullmatch(r'(?:busca|buscar|b[uú]scame|investiga|investigar|averigua|averiguar|aver[ií]guame|averiguarme|consulta|consultar)\s+(?:(?:en\s+)?(?:internet|la web|web|online)\s*:?\s*)?(.+)',natural,re.I|re.S)
    if m:
        consulta=m[1].strip()
        objetivo=normalizar(consulta)
        if objetivo in {'algo','algo en internet','en internet','internet','la web','web'}:
            return None
        if re.match(r'(?:a\s+)?(?:claude|gemini|chatgpt|deepseek)\b',objetivo) and n.startswith(('consulta ','consultar ')):
            return None
        if re.search(r'\b(?:archivos?|carpetas?|directorios?|ficheros?|tareas|sesiones|conversaciones|proyectos?)\b|\.(?:txt|md|py|sql|csv|xlsx|docx|pdf)\b',objetivo) and not re.search(r'\b(?:internet|web|online)\b',n):
            return None
        return consulta
    if re.match(r'^(?:dime\s+)?(?:cuanto (?:cuesta|vale|sale)|cual es el precio|que precio (?:tiene|vale))\s+\S',n):
        return natural
    return None


def validar_url(url):
    if not isinstance(url,str) or len(url)>2048 or re.search(r'[\x00-\x20\x7f]',url):
        raise ValueError('La dirección está vacía, es demasiado larga o contiene espacios.')
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError('Usa una dirección pública https:// sin credenciales ni puertos especiales.')
    host=p.hostname.encode('idna').decode('ascii')
    if host.lower().rstrip('.') in {'localhost','localhost.localdomain'}:
        raise ValueError('Las consultas web no acceden a la red local.')
    try:
        if not ipaddress.ip_address(host).is_global:raise ValueError('La dirección no es pública.')
    except ValueError as e:
        if 'no es pública' in str(e):raise
    return urlunsplit(('https','['+host+']' if ':' in host else host,'/'+p.path.lstrip('/'),p.query,''))


def direcciones_publicas(host):
    direcciones=list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not direcciones or any(not ipaddress.ip_address(ip).is_global for ip in direcciones):
        raise ValueError('El destino resuelve a una dirección no pública.')
    return sorted(direcciones,key=lambda ip:ipaddress.ip_address(ip).version)


class ConexionPublica(http.client.HTTPSConnection):
    def __init__(self,host,ip,timeout):
        super().__init__(host,timeout=timeout,context=ssl.create_default_context());self.ip=ip

    def connect(self):
        # Una sola resolución y conexión a la IP validada; TLS verifica el nombre original.
        raw=socket.create_connection((self.ip,443),self.timeout)
        try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except Exception:
            raw.close();raise


def solicitar_publico(url, cuerpo=None, headers=None, timeout=15):
    """GET con redirecciones validadas; POST sin redirecciones para no filtrar claves."""
    fin=time.monotonic()+timeout
    for salto in range(4):
        url=validar_url(url);p=urlsplit(url)
        ips=direcciones_publicas(p.hostname)
        restante=fin-time.monotonic()
        if restante<=0:raise TimeoutError('La consulta agotó su tiempo.')
        conexion=ConexionPublica(p.hostname,ips[0],restante)
        try:
            cabeceras={'User-Agent':'Jarvis/1.0 (consulta textual)','Accept-Encoding':'identity'}
            cabeceras.update(headers or {})
            conexion.request('POST' if cuerpo is not None else 'GET',p.path+('?' +p.query if p.query else ''),body=cuerpo,headers=cabeceras)
            respuesta=conexion.getresponse()
            if respuesta.status in (301,302,303,307,308):
                if cuerpo is not None:raise ValueError('La API redirigió la petición; configura su dirección definitiva.')
                destino=respuesta.getheader('Location')
                if not destino or salto==3:raise ValueError('Demasiadas redirecciones o destino ausente.')
                url=urljoin(url,destino);continue
            if not 200<=respuesta.status<300:
                # Solo se clasifica una muestra pequeña del error. Su texto no sale
                # de este proceso, porque puede repetir claves, URLs o la pregunta.
                datos_error=respuesta.read(8192)
                raise ErrorHTTP(respuesta.status,datos_error,respuesta.getheader('Retry-After',''))
            if respuesta.getheader('Content-Encoding','identity').lower() not in ('identity',''):
                raise ValueError('El servidor envió un formato comprimido no admitido.')
            datos=bytearray()
            while len(datos)<=MAX_BYTES:
                restante=fin-time.monotonic()
                if restante<=0:raise TimeoutError('La consulta agotó su tiempo.')
                conexion.sock.settimeout(restante) if conexion.sock else None
                trozo=respuesta.read1(min(32768,MAX_BYTES+1-len(datos)))
                if not trozo:break
                datos.extend(trozo)
            if len(datos)>MAX_BYTES:raise ValueError('La página supera 1 MB. Usa una página más pequeña.')
            return bytes(datos),respuesta.getheader('Content-Type',''),url
        finally:conexion.close()
    raise ValueError('No se pudo seguir la dirección.')


class TextoHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.partes=[];self.ocultos=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript','svg','template'}:self.ocultos.append(tag)
        if not self.ocultos and tag in {'p','div','br','li','h1','h2','h3','tr','section'}:self.partes.append('\n')
    def handle_endtag(self,tag):
        if self.ocultos and self.ocultos[-1]==tag:self.ocultos.pop()
        if not self.ocultos and tag in {'p','div','li','h1','h2','h3','tr'}:self.partes.append('\n')
    def handle_data(self,data):
        if not self.ocultos:self.partes.append(data)
    def texto(self):
        return '\n'.join(' '.join(l.split()) for l in ''.join(self.partes).splitlines() if l.strip())


class ResultadosBrave(HTMLParser):
    """Lee únicamente tarjetas de resultados, excluyendo navegación y scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.nivel=0;self.activos=[];self.registros=[];self.oculto=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ('script','style'):self.oculto+=1
        if tag=='div':
            self.nivel+=1
            if 'snippet' in attrs.get('class','').split():
                item={'url':'','partes':[],'titulo':''};self.registros.append(item);self.activos.append((self.nivel,item))
        if self.activos and 'title' in attrs.get('class','').split() and attrs.get('title'):
            self.activos[-1][1]['titulo']=attrs['title']
        if tag=='a' and self.activos and not self.activos[-1][1]['url']:
            link=attrs.get('href','')
            if link.startswith('https://'):self.activos[-1][1]['url']=link
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.oculto=max(0,self.oculto-1)
        if tag=='div':
            if self.activos and self.activos[-1][0]==self.nivel:self.activos.pop()
            self.nivel=max(0,self.nivel-1)
    def handle_data(self,data):
        if self.activos and not self.oculto and data.strip():self.activos[-1][1]['partes'].append(data.strip())
    def resultados(self):
        return [{'titulo':x['titulo'] or ' '.join(x['partes'])[:200],'url':x['url'],'resumen':' '.join(x['partes'])[:700]} for x in self.registros if x['url'] and x['partes']]


def fecha():return datetime.now().astimezone().isoformat(timespec='seconds')


def leer_web(url):
    try:
        datos,tipo,final=solicitar_publico(url)
        if not (tipo.lower().startswith('text/') or 'xhtml' in tipo.lower()):
            raise ValueError('Solo puedo leer páginas de texto o HTML; no archivos binarios ni PDF por URL.')
        encoding=re.search(r'charset=([\w-]+)',tipo,re.I)
        try:contenido=datos.decode(encoding[1] if encoding else 'utf-8',errors='replace')
        except LookupError:contenido=datos.decode('utf-8',errors='replace')
        if 'html' in tipo.lower():
            parser=TextoHTML();parser.feed(contenido);contenido=parser.texto()
        if not contenido.strip():raise ValueError('La página no contiene texto accesible sin JavaScript.')
        return {'ok':True,'url':final,'consultado':fecha(),'contenido':contenido[:10000],
                'recortado':len(contenido)>10000,'fuente_externa':True}
    except (OSError,ValueError,http.client.HTTPException) as e:
        return {'ok':False,'error':str(e)[:250]}


def buscar_web(consulta,limite=5):
    try:
        if not isinstance(consulta,str) or not 1<=len(consulta.strip())<=500:raise ValueError('Escribe una búsqueda de 1 a 500 caracteres.')
        if type(limite) is not int or not 1<=limite<=5:raise ValueError('El límite debe estar entre 1 y 5.')
        candidatos=[];motor='Brave'
        try:
            datos,_,_=solicitar_publico('https://search.brave.com/search?'+urlencode({'q':consulta.strip()}))
            parser=ResultadosBrave();parser.feed(datos.decode('utf-8',errors='replace'));candidatos=parser.resultados()
        except (OSError,ValueError,http.client.HTTPException):pass
        if not candidatos:
            motor='Bing RSS (alternativo)'
            url='https://www.bing.com/search?'+urlencode({'q':consulta.strip(),'format':'rss','setlang':'es'})
            datos,_,_=solicitar_publico(url);raiz=ET.fromstring(datos)
            candidatos=[{'titulo':item.findtext('title') or '', 'url':item.findtext('link') or '',
                         'resumen':item.findtext('description') or ''} for item in raiz.findall('./channel/item')]
        resultados=[];vistos=set()
        for item in candidatos:
            link=item['url'].strip()
            if link.startswith('http://'):link='https://'+link[7:]
            try:link=validar_url(link)
            except ValueError:continue
            if link in vistos:continue
            vistos.add(link)
            resultados.append({'titulo':unescape(item['titulo'] or link)[:250],
                               'url':link,'resumen':unescape(item['resumen'])[:700]})
            if len(resultados)==limite:break
        if not resultados:raise ValueError('El buscador no devolvió resultados accesibles; intenta otra búsqueda o /web con una URL.')
        return {'ok':True,'consulta':consulta,'motor':motor,'resultados':resultados,'consultado':fecha(),
                'fuente_externa':True,'aviso':'Son resultados del buscador; abre la página para verificar el contenido y su fecha.'}
    except (OSError,ValueError,ET.ParseError,http.client.HTTPException) as e:
        return {'ok':False,'error':str(e)[:250]}


def presentar(r):
    if not r.get('ok'):return 'No pude consultar Internet: '+r.get('error','sin respuesta')
    if 'resultados' in r:
        return 'Resultados web · '+r['consultado']+'\n\n'+'\n\n'.join(f"{n}. {x['titulo']}\n{x['url']}\n{x['resumen']}" for n,x in enumerate(r['resultados'],1))+'\n\n'+r['aviso']
    return f"Fuente: {r['url']}\nConsulta: {r['consultado']}\n\n{r['contenido']}"+ ('\n[Texto recortado a 10 000 caracteres.]' if r['recortado'] else '')
