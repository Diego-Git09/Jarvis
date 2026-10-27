import ast
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import unidades_captura as U

class Pruebas(unittest.TestCase):
    def test_no_extrae_los_dos_fragmentos_del_incidente(self):
        self.assertEqual(U.candidatos('Solo diseño, sin implementar'),[])
        self.assertEqual(U.candidatos('El filtro de privacidad de 8.2 vale igual para todos.'),[])
    def test_preferencia_breve_persistente_sigue_admitida(self):
        t='Prefiero pasos cortos y palabras simples.';self.assertEqual(U.candidatos(t),[t])
    def test_no_separa_una_lista_en_lineas_sueltas(self):
        t='Prefiero estas opciones:\n- pasos cortos\n- un ejemplo concreto'
        self.assertEqual(U.candidatos(t),[t])
    def test_encabezado_se_conserva_con_su_parrafo_contiguo(self):
        t='## Preferencia de modelos\n\nPrefiero usar los modelos locales para mis preguntas.'
        r=U.candidatos(t);self.assertEqual([t],r);self.assertTrue(all(x in t for x in r))
    def test_codigo_y_encabezados_sueltos_no_son_recuerdos(self):
        self.assertEqual(U.candidatos('```python\nprint("Preferencias permanentes")\n```'),[])
        self.assertEqual(U.candidatos('## Política de privacidad'),[])
    def test_referencias_vagas_no_se_vuelven_preferencias(self):
        self.assertEqual(U.candidatos('Quiero la segunda, igual que lo anterior.'),[])
    def test_no_parafrasea_los_fragmentos(self):
        t='Prefiero usar SQL.\n\nMe gusta recibir un ejemplo concreto.'
        self.assertTrue(all(x in t for x in U.candidatos(t)))
    def test_limites_de_tamano_y_cantidad(self):
        self.assertLessEqual(len(U.candidatos('\n\n'.join('Prefiero la opción '+str(i) for i in range(200)))),64)
        self.assertTrue(all(len(x)<=1800 for x in U.candidatos('Texto largo. '*400)))
    def test_funcion_real_del_capturador_rechaza_cita_que_no_es_unidad(self):
        p=Path.home()/'SegundoCerebro/memoria_automatica.py'
        fuente=p.read_text();arbol=ast.parse(fuente);func=next(x for x in arbol.body if isinstance(x,ast.FunctionDef) and x.name=='extract')
        class Respuesta:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return json.dumps({'message':{'content':json.dumps({'recuerdos':[{'titulo':'Política de privacidad','cita':'El filtro de privacidad de 8.2 vale igual para todos.'}]})}}).encode()
        import urllib.request,re
        env={'re':re,'json':json,'urllib':types.SimpleNamespace(request=types.SimpleNamespace(Request=urllib.request.Request,urlopen=lambda *a,**k:Respuesta())),'MODEL':'modelo-ficticio','private':lambda _:False,'opto_privacidad':lambda _:False}
        exec(compile(ast.Module(body=[func],type_ignores=[]),str(p),'exec'),env)
        t='Prefiero conservar el contexto completo.\n\nEl filtro de privacidad de 8.2 vale igual para todos.'
        self.assertTrue(U.candidatos(t))
        self.assertEqual(env['extract'](t),[])

if __name__=='__main__':unittest.main()
