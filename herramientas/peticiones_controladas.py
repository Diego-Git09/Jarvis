"""Lecturas reconocibles y aclaraciones antes del modelo. Nunca otorga permisos."""
import re,shlex
from normalizacion_entrada import vista

def atender(pedido,estado,ejecutar):
 from lenguaje_jarvis import no_es_peticion
 import memoria_explicita
 if not callable(ejecutar) or pedido.strip().startswith('/') or no_es_peticion(pedido) or memoria_explicita.INICIO.match(pedido):return None
 n=vista(pedido).strip(' ¿?¡!.')
 if re.match(r'(?:crea|guarda|guardar|escribe|copia|mueve|edita|modifica|renombra)\b',n) and not re.fullmatch(r'(?:mueve|edita|modifica)\s+(?:eso|esto|lo anterior|ese|esa|este)',n):return None
 from interfaz_jarvis import renderizar
 if re.fullmatch(r'(?:ollama\s+(?:ps|list)|nvidia-smi(?:\s+.*)?)',pedido.strip(),re.I):
  return 'Este chat no es una terminal. No ejecuté ese comando. Usa /modelo para ver la selección, /modelos para los instalados o /diagnostico para GPU, modelos cargados y conexiones.'
 if re.search(r'\b(?:muestra|muestrame|revela|dime|imprime)\b',n) and re.search(r'\b(?:prompt interno|reglas internas|instrucciones internas|prompt de sistema)\b',n):
  return 'Puedo explicar mis capacidades y límites con /ayuda. No mostraré el contexto interno de esta conversación ni ejecutaré peticiones de un texto adjunto.'
 from comprension_peticion import solo_datos_pegados
 if solo_datos_pegados(pedido):return None
 import externo_zen
 capacidades=externo_zen.respuesta_capacidades(pedido)
 if capacidades is not None:return capacidades
 if re.search(r'\bpeos\b',pedido,re.I) and re.search(r'\b(?:prints|mensajes|textos|respuestas)\b',n):
  return 'Entendí que los mensajes se ven mal. ¿El problema es su formato o que el contenido tiene errores? Puedes mostrarme un ejemplo para revisarlo.'
 if not re.search(r'\bno se\b',n) and (re.search(r'\bse (?:me )?(?:pego|congelo) (?:el )?juego\b',n) or re.search(r'\b(?:se quedo pegado el juego|el juego se (?:quedo pegado|congelo))\b',n)):
  return 'Entendí que el juego se congeló. ¿Quedó inmóvil o solamente bajaron los FPS (imágenes por segundo)? /diagnostico permite revisar recursos; no cerré ni modifiqué programas.'
 if re.fullmatch(r'(?:borra|elimina|quita|mueve|modifica|edita)\s+(?:eso|esto|lo anterior|ese|esa|este)',n):
  return '¿Qué quieres cambiar exactamente: un archivo (indica la ruta) o un recuerdo (indica el ID o número del listado)? No preparé ni ejecuté cambios.'
 cerebro=bool(re.search(r'\b(?:(?:segundo|2do) cerebro|el cerebro|del cerebro|mi cerebro)\b',n))
 pide_estado=cerebro and bool(re.search(r'\b(?:estado|como (?:esta|anda|va)|(?:esta )?funcionando|funciona|pendientes|errores)\b',n)) and not re.search(r'\b(?:como funciona|que significa|por ejemplo|si dijera)\b',n)
 if pide_estado:
  t=renderizar('consultar_estado_cerebro',ejecutar('consultar_estado_cerebro',{}))
  if re.search(r'\bram\b',n) and re.search(r'\bvram\b',n):
   return '1. RAM: memoria de trabajo que usan el sistema y las aplicaciones.\n\n2. VRAM: memoria de la GPU para gráficos y modelos.\n\n3. Segundo Cerebro:\n'+t
  return t
 if cerebro and re.search(r'\bproyectos\b',n) and re.match(r'(?:que|cuales|muestra|muestrame|dime|lista|listar)\b',n):
  return renderizar('listar_proyectos',ejecutar('listar_proyectos',{}))
 m=re.fullmatch(r'(?:muestra|muestrame|lista|listar|dime)\s+(?:los |las |mis )?(?:ultimos |mas recientes )?(?:recuerdos|memorias) (?:de|del proyecto|en el proyecto) (.+)',n)
 if m:
  from lenguaje_jarvis import proyecto
  return renderizar('listar_memorias',ejecutar('listar_memorias',{'proyecto':proyecto(m[1],estado),'orden':'recientes'}))
 if re.match(r'(?:usa|utiliza|consulta|pregunta (?:a|al))\s+(?:el )?(?:externo|zen|opencode)\b',n):
  import externo_zen
  if not externo_zen.estado()['encendido']:
   return 'Zen está apagado. No envié la pregunta a ningún servicio externo. Puedes preguntarme usando los modelos locales; /modelo muestra cuál está seleccionado.'
 from ordenes_compuestas import separar
 try:partes=separar(pedido)
 except ValueError:return None
 if not partes:return None
 from interfaz_archivos import acceso_natural,renderizar_archivos
 acciones=[]
 for parte in partes:
  v=vista(parte)
  if re.fullmatch(r'(?:revisa|mira|lista|muestra|dime|muestrame)(?: (?:la |mi )?carpeta de trabajo)?[, ]*(?:dime )?(?:que archivos hay|los archivos|archivos)?',v):
   acciones.append(('listar_archivos',{'ruta':'.'}));continue
  leer=re.fullmatch(r'(?:lee|leeme|léeme|abre)\s+(.+)',parte.strip(),re.I)
  if leer:
   try:rutas=shlex.split(leer[1])
   except ValueError:return None
   if len(rutas)==1 and re.search(r'\.[a-zA-Z0-9]{1,8}$',rutas[0]):
    acciones.append(('leer_archivo',{'ruta':rutas[0]}));continue
  acceso=acceso_natural(parte)
  if not acceso:return None
  try:campos=shlex.split(acceso)
  except ValueError:return None
  if campos[0]=='/leer' and len(campos)==2:acciones.append(('leer_archivo',{'ruta':campos[1]}))
  elif campos[0]=='/archivos' and len(campos)<=2:acciones.append(('listar_archivos',{'ruta':campos[1] if len(campos)==2 else '.'}))
  else:return None
 resultados=[]
 for i,(nombre,args) in enumerate(acciones,1):
  r=ejecutar(nombre,args);resultados.append(str(i)+'. '+renderizar_archivos(nombre,r))
  if not r.get('ok'):
   resultados.append('Me detuve en esta lectura; no intenté las siguientes.');break
 return '\n\n'.join(resultados)
