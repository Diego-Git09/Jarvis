"""Contratos R6 de privacidad y preferencia; nunca usa clave o red reales."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import externo_zen as Z
import seguridad_texto as S
import interfaz_jarvis as I
import jarvis_agente as J

PUBLICAS=['Explica Android Studio con Kotlin','Explica Windows y Linux','Compara Kubernetes y Docker','Explica PostgreSQL y MySQL','Compara Gradle y Maven','Explica Git para programar','Explica Android con Compose','Explica Studio y Gradle','Compara Windows y Ubuntu','Explica Kubernetes y PostgreSQL']
CITADAS=['Explica la frase "usa el externo"','Explica la frase «solo local»','Explica el ejemplo `usa el externo`','Explica este código:\n```\nusa el externo\n```','Explica esta cita: usa el externo','Explica este texto pegado: solo local','Explica la siguiente salida:\nusuario@equipo:~$ usa el externo','Explica el ejemplo “sin nube”','Explica estas palabras: "no uses internet"','Explica esto:\n> usa el externo']
ADVERSAS=['Explica el proyecto de Alicia','Explica el trabajo de Pedro','Explica la empresa Desconocida','Explica el proyecto de ALBERTO','Explica qué pasa en Valparaíso','Explica lo que hizo Santiago','Explica mi universidad','Explica mi trabajo con Docker','Explica el log usuario@equipo:~$ comando','Explica token=SECRETO_FICTICIO_R6']

class Pruebas(unittest.TestCase):
 def setUp(self):
  self.addCleanup(patch.stopall)
  patch.object(Z,'estado',return_value={'encendido':False}).start()
  patch.object(Z,'clave',side_effect=AssertionError('No se leen claves')).start()
  patch.object(Z,'transporte',side_effect=AssertionError('No hay red externa')).start()
 def citado(self,p):
  e={};Z.elegir(p,'compleja',e,fallo=True)
  self.assertNotIn('_preferencia_externa',e,p)
 def publico(self,p):self.assertTrue(S.privacidad_externa(p)[0],p)
 def adverso(self,p):self.assertFalse(S.privacidad_externa(p)[0],p)
 def test_tanda_antigua_no_equivale_a_fuentes_de_este_turno(self):
  for p in PUBLICAS:
   with self.subTest(p=p),patch.object(Z,'privacidad_externa',return_value=(False,'evaluación')) as privacidad:
    Z.elegir(p,'compleja',{'_tanda_documentos':'a'*32,'_fuentes_turno':False},fallo=True)
    self.assertFalse(privacidad.call_args.kwargs['adjuntos'])
 def test_fuentes_actuales_y_adjuntos_siguen_bloqueados(self):
  for p in PUBLICAS:
   for marca in ('_fuentes_turno','_adjuntos_turno'):
    with self.subTest(p=p,marca=marca),patch.object(Z,'privacidad_externa',return_value=(False,'fuentes')) as privacidad:
     Z.elegir(p,'compleja',{marca:True},fallo=True)
     self.assertTrue(privacidad.call_args.kwargs['adjuntos'])
 def test_preferencia_fuera_de_comillas_si_cuenta(self):
  for p,valor in [('solo local','local'),('sin internet','local'),('sin nube','local'),('no uses internet','local'),('no uses el externo','local'),('usa el externo','externo'),('usa la nube','externo'),('usa zen','externo'),('usa opencode','externo'),('usar el externo','externo')]:
   with self.subTest(p=p):
    e={};Z.elegir(p,'simple',e);self.assertEqual(e.get('_preferencia_externa'),valor)
 def test_archivo_publico_editable_y_fallo_cerrado(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'publicos.json';p.write_text(json.dumps(['Rust','LLVM']))
   with patch.object(S,'TERMINOS_PUBLICOS',p,create=True):
    self.assertTrue(S.privacidad_externa('Explica Rust y LLVM')[0])
    p.write_text('{no es JSON}')
    self.assertFalse(S.privacidad_externa('Explica Rust y LLVM')[0])
 def test_mensaje_largo_tiene_misma_decision_en_ambas_entradas(self):
  for inicio in PUBLICAS:
   pregunta=inicio+' y comenta las posibilidades. '+('detalle ' * 1700)
   llamadas=[]
   def elegir(*args,**kw):
    if kw.get('contexto'):llamadas.append(kw)
    return None,'externo apagado'
   with self.subTest(p=inicio),patch.object(Z,'elegir',side_effect=elegir),patch.object(Z,'respuesta_capacidades',return_value=None),patch('mensajes_largos.preparar',return_value='LOCAL'),patch('analisis_registros.explicar',return_value=None):
    I.comando(pregunta,[],{},Mock(side_effect=AssertionError('Sin acciones')),J.SISTEMA)
    J._responder_con_respaldo([{'role':'user','content':pregunta}],Mock(),lambda _:False,{},mostrar=lambda _:None)
   self.assertGreaterEqual(len(llamadas),2)
   self.assertEqual(llamadas[0],llamadas[-1])

for familia,frases,metodo in [('publico',PUBLICAS,'publico'),('citado',CITADAS,'citado'),('adverso',ADVERSAS,'adverso')]:
 for i,p in enumerate(frases,1):setattr(Pruebas,f'test_{familia}_{i:02}',lambda self,p=p,metodo=metodo:getattr(self,metodo)(p))
if __name__=='__main__':unittest.main()
