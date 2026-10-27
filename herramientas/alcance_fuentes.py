"""Decide si la pregunta actual pide las fuentes disponibles. No concede permisos."""
import re
from normalizacion_entrada import vista

def _nueva_consulta(n):
 return bool(re.search(r'\b(?:que (?:es|significa)|para que sirve|cuanto es|analiza (?:las )?ventajas|como (?:esta|funciona)|cuanto cuesta)\b',n))

def _explicita(n,estado=None):
 from referencias_fuentes import explicita
 return explicita(n,estado)

def solo_lectura(pedido,activa):
 if not activa:return False
 from normalizacion_entrada import PROTEGIDO
 n=vista(PROTEGIDO.sub(' ',pedido.split('[Adjunto:',1)[0]))
 return bool(re.search(r'\b(?:resume|resumeme|analiza|explica|explicame|que dice|de que trata|ideas principales)\b',n) and not re.search(r'\b(?:crea|guarda|escribe|mueve|copia|edita|modifica|elimina|borra|ejecuta|instala)\b',n))

def preparar(historial,pedido,estado):
 disponible=bool(estado.get('_tanda_documentos') or estado.get('_documento_tramo'))
 n=vista(pedido)
 excluye=bool(re.search(r'\b(?:sin adjuntos|sin archivos|otro tema|olvida eso|no uses|sin usar)\b',n))
 actual='[adjunto:' in n
 especifica=_explicita(n,estado) and not excluye
 anteriores=[m.get('content','') for m in historial if m.get('role')=='user']
 if anteriores and anteriores[-1]==pedido:anteriores.pop()
 tema=estado.get('_fuentes_tema_activo',False)
 if '_fuentes_tema_activo' not in estado:
  for p in anteriores:
   pn=vista(p)
   if p.strip().startswith('/') and '[adjunto:' not in pn:continue
   if _explicita(pn):tema=True
   elif _nueva_consulta(pn) or re.fullmatch(r'hola(?: jarvis)?',pn.strip(' ¿?!.')):tema=False
 from seguimiento_conversacion import continuacion
 sigue=tema and continuacion(pedido) and not _nueva_consulta(n)
 if re.search(r'\b(?:paso|opcion|alternativa|tema|concepto|recuerdos?|api|docker)\b',n) and not especifica:sigue=False
 if estado.get('_hilo_conversacion',{}).get('propuesta') and not especifica:sigue=False
 activa=disponible and not excluye and (actual or especifica or sigue)
 estado['_fuentes_turno']=bool(activa)
 estado['_fuentes_tema_activo']=bool(activa)
 # Cambia solo la vista que recibe el modelo; conserva el historial íntegro.
 estado['_fuentes_aislar_historial']=disponible and not activa and not (continuacion(pedido) and not _nueva_consulta(n))
 return bool(activa)
