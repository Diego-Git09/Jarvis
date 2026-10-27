"""Contratos por familia ampliada, con originales y literales sin modificar."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
import jarvis_agente as J
import variantes_r5 as V
import interfaz_jarvis as I
import peticiones_controladas as P
import alcance_fuentes as A
import memoria_explicita as M

class Pruebas(unittest.TestCase):
    def test_corpus_ampliado_distinto_de_observado(self):
        self.assertEqual(len(V.FAMILIAS),12)
        for k,frases in V.FAMILIAS.items():
            with self.subTest(familia=k):self.assertEqual(len(frases),10);self.assertEqual(len(set(frases)),10)

    def familia(self,k):
        for p in V.FAMILIAS[k]:
            with self.subTest(p=p):
                if k.startswith('scope_'):
                    from prueba_ronda5_fuentes import Pruebas as Fuentes
                    Fuentes().probar(p)
                elif k=='externo_apagado':
                    import externo_zen as Z
                    with patch.object(Z,'estado',return_value={'encendido':False}),patch.object(Z,'transporte',side_effect=AssertionError('Sin red')):
                        t=P.atender(p,{},Mock(side_effect=AssertionError('Sin acciones')))
                    self.assertIsNotNone(t);self.assertIn('apagado',t)
                elif k=='lecturas_encadenadas':
                    a=Mock(return_value={'ok':True,'contenido':'LECTURA_R5','items':[]})
                    t=P.atender(p,{},a);self.assertIsNotNone(t)
                    self.assertTrue(all(c.args[0] in {'leer_archivo','listar_archivos'} for c in a.call_args_list));self.assertIn('LECTURA_R5',t)
                elif k=='guardado_corto':
                    d=M.interpretar(p);self.assertIsNotNone(d);self.assertEqual(d['proyecto'],'sin_clasificar')
                    self.assertIn(d['contenido'],p);self.assertNotIn(' q ',d['contenido'])
                elif k=='modelo_memoria':
                    from consultas_equipo import modelos_memoria
                    t=modelos_memoria(p,Mock(solicitar=Mock(return_value={'models':[]})))
                    self.assertIsNotNone(t);self.assertIn('bytes por peso',t);self.assertIn('No hay un modelo',t)
                else:
                    from guias_contexto_r3 import contexto
                    c=contexto(p);self.assertIn('verific',c.lower());self.assertNotIn('swddo.sql',c)

for k in V.FAMILIAS:setattr(Pruebas,'test_familia_'+k,lambda self,k=k:self.familia(k))
if __name__=='__main__':unittest.main()
