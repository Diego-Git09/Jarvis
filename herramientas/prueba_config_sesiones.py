import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import configuracion_jarvis as C
import sesiones_jarvis as S
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_config_validacion_y_guardado_atomico(self):
        archivo=self.base/'config.json'
        datos=dict(C.DEFAULT,modo='breve',timeout_modelo=60)
        C.guardar(datos,archivo)
        self.assertEqual(C.leer(archivo)[0],datos)
        self.assertEqual(archivo.stat().st_mode&0o777,0o600)
        for cambio in [{'modelo':'\nmal'}, {'num_ctx':True}, {'modo':'inventado'}, {'timeout_modelo':0}, {'extra':1}]:
            with self.assertRaises(ValueError):C.guardar(dict(datos,**cambio),archivo)
        self.assertEqual(C.leer(archivo)[0],datos)

    def test_config_corrupta_no_crashea_ni_se_sobrescribe(self):
        archivo=self.base/'config.json';archivo.write_text('{roto')
        datos,aviso=C.leer(archivo)
        self.assertEqual(datos,C.DEFAULT);self.assertTrue(aviso)
        self.assertEqual(archivo.read_text(),'{roto')

    def test_sesion_guarda_contenido_sin_permisos_ni_cache(self):
        h=[{'role':'system','content':'reglas viejas'}, {'role':'user','content':'hola'}, {'role':'assistant','content':'hola'}]
        state={'_proyecto_activo':'Jarvis','_tamano_pagina':10,'_memorias':{1:{'contenido':'privado'}},'id_propuesta':'xyz'}
        S.guardar('almuerzo',h,state,self.base)
        mensajes,prefs=S.cargar('almuerzo',self.base)
        self.assertEqual(mensajes,h[1:]);self.assertEqual(prefs,{'_proyecto_activo':'Jarvis','_tamano_pagina':10})
        self.assertNotIn('privado',(self.base/'almuerzo.json').read_text())
        self.assertEqual((self.base/'almuerzo.json').stat().st_mode&0o777,0o600)

    def test_sesion_rechaza_rutas_y_enlaces(self):
        for nombre in ['../salir','a/b','', 'x.json;comando']:
            with self.assertRaises(ValueError):S.ruta_sesion(nombre,self.base)
        fuera=self.base/'fuera.json';fuera.write_text('secreto')
        (self.base/'alias.json').symlink_to(fuera)
        with self.assertRaises(ValueError):S.cargar('alias',self.base)
        with self.assertRaises(ValueError):S.guardar('alias',[],{},self.base)
        self.assertEqual(fuera.read_text(),'secreto')

    def test_listado_tolera_archivo_corrupto(self):
        S.guardar('buena',[{'role':'user','content':'texto'}],{},self.base)
        (self.base/'rota.json').write_text('{roto')
        self.assertEqual([r['nombre'] for r in S.listar(self.base)],['buena'])

    def test_modelo_no_instalado_no_cambia_config(self):
        ajustes=dict(C.DEFAULT)
        with patch('interfaz_local.O.modelos',return_value=['qwen3:8b']),patch('interfaz_local.C.guardar') as guardar:
            handled,texto=comando_local('/modelo desconocido',[],{},lambda _:True,ajustes,lambda:None,None)
        self.assertTrue(handled);self.assertIn('no está instalado',texto)
        self.assertEqual(ajustes,C.DEFAULT);guardar.assert_not_called()

    def test_sesion_denegada_no_escribe(self):
        with patch('interfaz_local.S.guardar') as guardar:
            handled,texto=comando_local('/guardar prueba',[{'role':'system','content':'s'}],{},lambda _:False,dict(C.DEFAULT),lambda:None,None)
        self.assertTrue(handled);self.assertIn('No guardé',texto);guardar.assert_not_called()

    def test_diagnostico_actual_y_caida_de_cerebro(self):
        class CerebroCaido:
            def llamar(self,nombre,argumentos):
                raise ConnectionError('sin conexión')
        with patch('interfaz_local.O.diagnostico',return_value={'ok':False}):
            handled,texto=comando_local('/diagnostico',[],{},lambda _:True,dict(C.DEFAULT),lambda:None,CerebroCaido())
        self.assertTrue(handled)
        self.assertIn('Lecturas realizadas ahora',texto)
        self.assertIn('(Chile)',texto)
        self.assertIn('http://127.0.0.1:8767',texto)
        self.assertIn('Los accesos directos siguen disponibles',texto)


if __name__=='__main__':unittest.main()
