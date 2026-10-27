"""Pruebas del flujo agrupado sobre una base temporal, sin datos reales."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import jarvis_agente as J
from interfaz_jarvis import comando
from control_clasificacion import consultar, clasificar, crear_proyecto


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        with closing(sqlite3.connect(self.base/'cerebro.db')) as db,db:
            db.execute('CREATE TABLE memorias(id INTEGER PRIMARY KEY,proyecto TEXT,titulo TEXT,contenido TEXT,creado TEXT)')
            for n in range(1,6):db.execute('INSERT INTO memorias VALUES(?,?,?,?,?)',(100+n,'sin_clasificar',f't{n}',f'dato{n}','fecha'))
        self.state={'_lista_memorias':{n:100+n for n in range(1,6)},'_memorias':{100+n:consultar(self.base,100+n)['memorias'][0] for n in range(1,6)}}
        self.calls=[]
        parent=self
        class Cliente:
            def llamar(self,n,a):
                parent.calls.append((n,dict(a)))
                if n=='consultar_memoria':return {'ok':True,**consultar(parent.base,a['id_memoria'])}
                if n=='clasificar_memoria':return {'ok':True,**clasificar(parent.base,a['id_memoria'],a['proyecto'],a['contenido_esperado'],a['proyecto_esperado'])}
                raise AssertionError(n)
        self.cliente=Cliente()

    def tearDown(self):self.temp.cleanup()

    def ejecutar(self,args,confirmar):
        with patch.object(J,'CEREBRO',self.cliente),patch.object(J.L,'_registrar') as registro:
            r=J.ejecutar_herramienta('clasificar_recuerdos',args,confirmar,self.state)
            self.assertNotIn('dato1',str(registro.call_args_list))
            return r

    def test_cinco_movimientos_una_confirmacion_ids_reales(self):
        permisos=[]
        r=self.ejecutar({'numeros':[1,2,3,4,5],'proyecto':'JARVIS'},lambda t:permisos.append(t) or True)
        self.assertTrue(r['ok']);self.assertEqual(len(permisos),1)
        self.assertIn('dato5',permisos[0])
        writes=[a['id_memoria'] for n,a in self.calls if n=='clasificar_memoria']
        self.assertEqual(writes,[101,102,103,104,105])
        for ident in writes:
            fila=consultar(self.base,ident)['memorias'][0]
            self.assertEqual(fila['proyecto'],'Jarvis')
            self.assertEqual(fila['contenido'],f'dato{ident-100}')

    def test_rechazo_no_mueve(self):
        r=self.ejecutar({'numeros':[1,2],'proyecto':'Jarvis'},lambda _:False)
        self.assertFalse(r['ok']);self.assertTrue(all(n=='consultar_memoria' for n,a in self.calls))
        self.assertEqual(consultar(self.base,101)['memorias'][0]['proyecto'],'sin_clasificar')

    def test_seleccion_invalida_no_consulta(self):
        for nums in [[1,1],[True],[0],[],[1,6]]:
            self.assertFalse(self.ejecutar({'numeros':nums,'proyecto':'Jarvis'},lambda _:self.fail('No debe preguntar'))['ok'])
        self.assertFalse(self.calls)

    def test_contenido_cambiado_no_mueve_nada(self):
        with closing(sqlite3.connect(self.base/'cerebro.db')) as db,db:db.execute("UPDATE memorias SET contenido='otro' WHERE id=102")
        r=self.ejecutar({'numeros':[1,2],'proyecto':'Jarvis'},lambda _:self.fail('No debe preguntar'))
        self.assertFalse(r['ok']);self.assertTrue(all(n=='consultar_memoria' for n,a in self.calls))
        self.assertEqual(consultar(self.base,101)['memorias'][0]['proyecto'],'sin_clasificar')

    def test_fallo_intermedio_informa_lo_completado(self):
        original=self.cliente.llamar
        def fallar(n,a):
            if n=='clasificar_memoria' and a['id_memoria']==102:raise ConnectionError('fallo')
            return original(n,a)
        with patch.object(self.cliente,'llamar',side_effect=fallar):
            r=self.ejecutar({'numeros':[1,2,3],'proyecto':'Jarvis'},lambda _:True)
        self.assertFalse(r['ok']);self.assertEqual([m['numero'] for m in r['resultados']],[1])
        self.assertIn('recuerdo 2',r['error'])
        self.assertEqual(consultar(self.base,103)['memorias'][0]['proyecto'],'sin_clasificar')

    def test_frases_del_texto_no_usan_qwen(self):
        for frase,numeros in [('puedes mover los recuerdos 1,2,3,4,5 al proyecto JARVIS',[1,2,3,4,5]),('mueve el recuero 1 y 2 al Proyecto Jarvis',[1,2])]:
            calls=[]
            handled,_=comando(frase,[],{},lambda n,a:calls.append((n,a)) or {'ok':False,'error':'simulado'},'s')
            self.assertTrue(handled);self.assertEqual(calls[0][1]['numeros'],numeros)
            self.assertEqual(calls[0][0],'clasificar_recuerdos')
        for frase in ['No muevas los recuerdos 1 y 2 al proyecto Jarvis','¿Cómo puedo mover recuerdos a Jarvis?']:
            self.assertFalse(comando(frase,[],{},None,'s')[0])

    def test_flujo_comando_aceptado_mueve_todos(self):
        permisos=[]
        def ejecutar(nombre,args):
            self.assertEqual(nombre,'clasificar_recuerdos')
            return self.ejecutar(args,lambda t:permisos.append(t) or True)
        handled,texto=comando('puedes mover los recuerdos 1,2,3,4,5 al proyecto JARVIS',[],self.state,ejecutar,'s')
        self.assertTrue(handled);self.assertEqual(len(permisos),1)
        for n in range(1,6):
            self.assertIn(f'{n}. t{n}: movido',texto)
            self.assertEqual(consultar(self.base,100+n)['memorias'][0]['proyecto'],'Jarvis')

    def test_frase_exacta_agrega_memorias_una_confirmacion(self):
        permisos=[]
        handled,texto=comando('agrega las memorias 1,2,3,4,5 al proyecto Segundo Cerebro',[],self.state,
            lambda n,a:self.ejecutar(a,lambda t:permisos.append(t) or True),'s')
        self.assertTrue(handled);self.assertEqual(len(permisos),1)
        for n in range(1,6):
            self.assertEqual(consultar(self.base,100+n)['memorias'][0]['proyecto'],'Segundo Cerebro')
            self.assertIn(f'{n}. t{n}: movido',texto)

    def test_variantes_memorias_y_verbos(self):
        for frase in ['añade las memorias 1 y 2 al proyecto Segundo Cerebro',
                      'puedes agregar los recuerdos 1,2 al proyecto Jarvis',
                      'por favor asigna las memorias 1,2 al proyecto estudios',
                      'pasa los recuerdos 1,2 al proyecto Jarvis']:
            calls=[]
            handled,_=comando(frase,[],{},lambda n,a:calls.append((n,a)) or {'ok':False,'error':'simulado'},'s')
            self.assertTrue(handled);self.assertEqual(calls[0][1]['numeros'],[1,2])
        self.assertFalse(comando('No agregues las memorias 1,2 al proyecto Jarvis',[],{},None,'s')[0])

    def test_error_del_modelo_indica_herramienta_correcta(self):
        with patch.object(J,'CEREBRO',self.cliente):
            r=J.ejecutar_herramienta('clasificar_memoria',{'id_memoria':[1,2,3],'proyecto':'Jarvis'},lambda _:self.fail('No debe preguntar'),self.state)
        self.assertFalse(r['ok']);self.assertIn('clasificar_recuerdos',r['error'])
        self.assertFalse(self.calls)

    def comprobar_frase_unica(self, frase):
        crear_proyecto(self.base,'Segundo Cerebro')
        self.state['_lista_memorias']={1:101};permisos=[]
        handled,texto=comando(frase,[],self.state,lambda n,a:self.ejecutar(a,lambda t:permisos.append(t) or True),'s')
        self.assertTrue(handled);self.assertEqual(len(permisos),1)
        self.assertEqual(consultar(self.base,101)['memorias'][0]['proyecto'],'Segundo Cerebro')
        self.assertIn('movido',texto)
        with closing(sqlite3.connect(self.base/'cerebro.db')) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memorias WHERE proyecto='sin_clasificar'").fetchone()[0],4)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memorias WHERE proyecto='Segundo Cerebro'").fetchone()[0],1)

    def test_muevelo_de_captura_pide_permiso_y_cambia_conteos(self):
        self.comprobar_frase_unica('muevelo a Proyecto Segundo Cerebro')

    def test_agrega_uno_sin_palabra_recuerdo(self):
        self.comprobar_frase_unica('agrega 1 al proyecto segundo cerebro')

    def test_pronombre_ambiguo_no_ejecuta(self):
        handled,texto=comando('muévelo al proyecto Segundo Cerebro',[],self.state,lambda *_:self.fail('No debe ejecutar'),'s')
        self.assertTrue(handled);self.assertIn('número',texto)
        self.assertFalse(self.calls)

    def test_qwen_no_puede_afirmar_movimiento_sin_herramienta(self):
        h=[{'role':'user','content':'muevelo a Proyecto Segundo Cerebro'}]
        r=J.ejecutar_turno(h,lambda _: {'role':'assistant','content':'1. Implementación: movido al proyecto Segundo Cerebro.'},lambda _:self.fail('No debe preguntar'),self.state)
        self.assertIn('No ejecuté',r);self.assertEqual(h[-1]['content'],r)
        self.assertEqual(consultar(self.base,101)['memorias'][0]['proyecto'],'sin_clasificar')

    def test_qwen_no_puede_ocultar_permiso_denegado(self):
        cola=iter([{'role':'assistant','content':'','tool_calls':[{'function':{'name':'clasificar_recuerdos','arguments':{'numeros':[1],'proyecto':'Segundo Cerebro'}}}]},
                   {'role':'assistant','content':'El recuerdo se movió correctamente.'}])
        with patch.object(J,'CEREBRO',self.cliente),patch.object(J.L,'_registrar'):
            r=J.ejecutar_turno([{'role':'user','content':'mueve 1 a Segundo Cerebro'}],lambda _:next(cola),lambda _:False,self.state,mostrar=lambda _:None)
        self.assertIn('No autorizaste',r)
        self.assertNotIn('correctamente',r)
        self.assertEqual(consultar(self.base,101)['memorias'][0]['proyecto'],'sin_clasificar')

    def test_ya_clasificados_no_repite_escritura(self):
        self.ejecutar({'numeros':[1,2],'proyecto':'Jarvis'},lambda _:True)
        self.calls=[]
        r=self.ejecutar({'numeros':[1,2],'proyecto':'Jarvis'},lambda _:self.fail('No debe preguntar'))
        self.assertTrue(r['ok']);self.assertTrue(all(m['estado']=='ya_clasificado' for m in r['resultados']))
        self.assertTrue(all(n=='consultar_memoria' for n,a in self.calls))


if __name__=='__main__':unittest.main()
