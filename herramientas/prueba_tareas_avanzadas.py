import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import tareas_jarvis as T
import sesiones_jarvis as S
from interfaz_local import comando_local
import configuracion_jarvis as C


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.ruta=self.root/'tareas.json';self.addCleanup(self.temp.cleanup)

    def test_editar_y_priorizar_conservan_identidad_y_estado(self):
        t=T.anotar('primera',self.ruta);T.marcar(t['id'],True,self.ruta)
        r=T.editar(t['id'],'actualizada',self.ruta);self.assertEqual(r['id'],t['id']);self.assertTrue(r['hecha'])
        self.assertEqual(T.priorizar(t['id'],'alta',self.ruta)['prioridad'],'alta')
        antes=self.ruta.read_text()
        for p in ['urgente',[],None]:
            with self.assertRaises(ValueError):T.priorizar(t['id'],p,self.ruta)
        self.assertEqual(self.ruta.read_text(),antes)

    def test_marcar_varias_es_atomico_si_falta_una(self):
        a=T.anotar('a',self.ruta);b=T.anotar('b',self.ruta)
        antes=self.ruta.read_text()
        with self.assertRaises(ValueError):T.marcar_varias([a['id'],'inexistente'],True,self.ruta)
        self.assertEqual(self.ruta.read_text(),antes)
        T.marcar_varias([a['id'],b['id']],True,self.ruta)
        self.assertTrue(all(t['hecha'] for t in T.listar(self.ruta)))

    def test_busqueda_sin_tildes_y_markdown(self):
        t=T.anotar('Comprar café',self.ruta)
        self.assertEqual(T.filtrar('CAFE',T.listar(self.ruta))[0]['id'],t['id'])
        self.assertIn('- [ ] Comprar café',T.markdown(T.listar(self.ruta)))

    def test_listado_prioriza_y_frases_seleccionan_sus_numeros(self):
        filas=[{'id':'a','texto':'normal','hecha':False},{'id':'b','texto':'urgente','hecha':False,'prioridad':'alta'}]
        state={}
        with patch('interfaz_local.T.listar',return_value=filas),patch('interfaz_local.T.marcar_varias',return_value=filas) as marcar:
            _,texto=comando_local('/tareas',[],state,lambda _:True,dict(C.DEFAULT),lambda:None,None)
            self.assertTrue(texto.startswith('1. ○ urgente'))
            comando_local('Completa las tareas uno y dos',[],state,lambda _:True,dict(C.DEFAULT),lambda:None,None)
            marcar.assert_called_once_with(['b','a'],True)

    def test_exportar_tareas_usa_controlador_y_respeta_denegacion(self):
        llamadas=[]
        with patch('interfaz_local.T.listar',return_value=[]):
            handled,texto=comando_local('/exportar_tareas pendientes.md',[],{},lambda _:False,dict(C.DEFAULT),lambda:None,None,
                ejecutar=lambda n,a:llamadas.append((n,a)) or {'ok':False,'error':'No autorizado'})
        self.assertTrue(handled);self.assertEqual(texto,'No autorizado');self.assertEqual(llamadas[0][0],'crear_archivo')
        self.assertEqual(llamadas[0][1]['ruta'],'pendientes.md');self.assertIn('# Tareas',llamadas[0][1]['contenido'])

    def test_exportar_sesion_conserva_texto_y_no_reglas(self):
        S.guardar('sesion',[{'role':'system','content':'regla privada'},{'role':'user','content':'hola\nsegunda línea'},{'role':'assistant','content':'respuesta'}],{},self.root)
        texto=S.markdown('sesion',self.root)
        self.assertIn('> segunda línea',texto);self.assertNotIn('regla privada',texto)

    def test_tamano_pagina_se_guarda_sin_perder_proyecto(self):
        estado={'_proyecto_activo':'Jarvis','_lista_memorias':{1:2}};ajustes=dict(C.DEFAULT)
        with patch('interfaz_local.C.guardar') as guardar:
            _,texto=comando_local('/tamano 8',[],estado,lambda _:True,ajustes,lambda:None,None)
        guardar.assert_called_once();self.assertEqual(ajustes['tamano_pagina'],8)
        self.assertEqual(estado['_proyecto_activo'],'Jarvis');self.assertNotIn('_lista_memorias',estado);self.assertIn('próximas aperturas',texto)


if __name__=='__main__':unittest.main()
