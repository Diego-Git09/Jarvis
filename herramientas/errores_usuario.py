"""Detalles de implementación a indicaciones concretas en español."""
import re

def presentar(texto):
 t=str(texto)
 if 'FileNotFoundError' in t:
  return 'No es un archivo disponible en la ruta indicada. Comprueba su nombre y carpeta con /archivos; no ejecuté cambios.'
 if 'FileExistsError' in t:
  return 'El destino ya existe. Elige otro nombre o revisa el archivo antes de proponer un cambio; no lo sobrescribí.'
 if 'PermissionError' in t:
  return 'No pude acceder a esa ruta con los permisos actuales. Revisa las carpetas autorizadas con /carpetas; no amplié permisos.'
 if re.search(r'Argumentos no permitidos|unexpected keyword|missing .*argument|KeyError|TypeError',t,re.I):
  return 'La consulta incluyó datos no permitidos para esta operación. No ejecuté cambios. Prueba el acceso directo de /ayuda; si persiste, revisa /diagnostico.'
 if re.search(r'read (?:operation )?timed out|timed out|timeout',t,re.I):
  return 'Se agotó el tiempo de conexión. Comprueba Internet y vuelve a intentar la consulta; no confirma que el servicio esté caído.'
 return t
