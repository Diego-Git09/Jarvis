"""Orden cronológico, paginación y selección global anterior al límite."""
import ast
import os
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import jarvis_agente as J
from interfaz_jarvis import comando


class Pruebas(unittest.TestCase):
    def test_frase_de_captura_y_pagina_siguiente(self):
        registros=[{'id':n,'titulo':str(n),'contenido':'dato','proyecto':'sin_clasificar','creado':f'2026-10-12T0{n}:00:00+00:00'} for n in range(7,0,-1)]
        state={};h=[]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':registros}) as llamar:
            ejecutar=lambda n,a:J.ejecutar_herramienta(n,a,lambda _:False,state)
            handled,texto=comando('recuerdos sin clasificar ordenados del mas antiguo al mas nuevo (por fecha)',h,state,ejecutar,'s')
            self.assertTrue(handled);self.assertIn('del más antiguo al más nuevo',texto)
            llamar.assert_called_once_with('listar_memorias',{'proyecto':'sin_clasificar','orden':'antiguos'})
            self.assertEqual(list(state['_lista_memorias'].values()),[1,2,3,4,5])
            comando('/mas',h,state,ejecutar,'s')
            self.assertEqual(list(state['_lista_memorias'].values()),[6,7])
            self.assertEqual(state['_pagina_memorias']['orden'],'antiguos')
            self.assertEqual(llamar.call_count,1)

    def test_zonas_horarias_y_orden_invalido(self):
        registros=[{'id':2,'contenido':'b','creado':'2026-10-12T02:00:00+00:00'},
                   {'id':1,'contenido':'a','creado':'2026-10-11T22:00:00-03:00'}]
        with patch.object(J.CEREBRO,'llamar',return_value={'ok':True,'memorias':registros}) as llamar:
            r=J.ejecutar_herramienta('listar_memorias',{'orden':'antiguos'},lambda _:False,{})
            self.assertEqual([m['id'] for m in r['memorias']],[1,2])
            self.assertFalse(J.ejecutar_herramienta('listar_memorias',{'orden':'inventado'},lambda _:False,{})['ok'])
            self.assertEqual(llamar.call_count,1)

    def test_servidor_ordena_antes_de_limitar(self):
        carpeta = os.environ.get('SEGUNDO_CEREBRO_DIR')
        if not carpeta:
            self.skipTest('Integración externa: define SEGUNDO_CEREBRO_DIR para comprobar su servidor.')
        ruta = Path(carpeta).expanduser() / 'servidor_mcp.py'
        if not ruta.is_file():
            self.fail('SEGUNDO_CEREBRO_DIR no contiene servidor_mcp.py.')
        tree=ast.parse(ruta.read_text())
        funcion=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='listar_memorias')
        funcion.decorator_list=[]
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        self.addCleanup(db.close)
        db.execute('CREATE TABLE memorias(id INTEGER,proyecto TEXT,creado TEXT)')
        for n in range(60):db.execute('INSERT INTO memorias VALUES(?,?,?)',(n+1,'sin_clasificar',f'2026-10-12T01:{n:02}:00+00:00'))
        # La prueba aísla el SQL de listado; representa la función de formato
        # del servidor sin ejecutar el resto de su inicialización MCP.
        ns={'conectar':lambda:db,'_vista_memoria':lambda fila,limite=1600:dict(fila)}
        exec(compile(ast.Module(body=[funcion],type_ignores=[]),'<listar_memorias>','exec'),ns)
        viejos=ns['listar_memorias']('sin_clasificar','antiguos')
        nuevos=ns['listar_memorias']('sin_clasificar','recientes')
        self.assertEqual([r['id'] for r in viejos],list(range(1,51)))
        self.assertEqual([r['id'] for r in nuevos],list(range(60,10,-1)))
        pagina=ns['listar_memorias']('sin_clasificar','recientes',50,10)
        self.assertEqual([r['id'] for r in pagina],list(range(10,0,-1)))
        with self.assertRaises(ValueError):ns['listar_memorias']('sin_clasificar','recientes',-1,10)
        with self.assertRaises(ValueError):ns['listar_memorias']('sin_clasificar','recientes',0,101)


if __name__=='__main__':unittest.main()
