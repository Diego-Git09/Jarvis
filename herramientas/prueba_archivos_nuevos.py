import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import herramientas_lectura as L
import herramientas_escritura as E
import jarvis_agente as J
from interfaz_archivos import comando_archivos


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'trabajo';self.root.mkdir()
        self.patches=[patch.object(L,'RAIZ',self.root),patch.object(L,'REGISTRO',self.base/'registro.jsonl'),
                      patch.object(E,'RAIZ',self.root),patch.object(E,'CAMBIOS',self.base/'cambios'),
                      patch.object(E,'PENDIENTES',self.base/'pendientes'),patch.object(E,'COPIAS',self.base/'copias')]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in reversed(self.patches)])
        self.addCleanup(self.temp.cleanup)

    def test_lectura_lineas_y_busqueda_en_un_archivo(self):
        (self.root/'a.txt').write_text('uno\ndos\ntres\n',encoding='utf-8')
        r=L.leer_lineas('a.txt',2,1)
        self.assertEqual(r['lineas'],['dos']);self.assertEqual(r['siguiente'],3)
        self.assertEqual(L.buscar_texto('dos','a.txt')['resultados'][0]['linea'],2)
        self.assertFalse(L.leer_lineas('a.txt',0,1)['ok'])
        self.assertFalse(L.buscar_texto('x','inexistente')['ok'])

    def test_copia_y_deshacer_sin_pisar_destino(self):
        (self.root/'a.txt').write_bytes(b'original')
        r=E.copiar_archivo('a.txt','b.txt')
        self.assertTrue(r['verificado']);self.assertEqual((self.root/'b.txt').read_bytes(),b'original')
        self.assertFalse(E.copiar_archivo('a.txt','b.txt')['ok'])
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado'])
        self.assertTrue((self.root/'a.txt').exists());self.assertFalse((self.root/'b.txt').exists())

    def test_mover_y_revertir_respetan_cambios_externos(self):
        (self.root/'a.txt').write_bytes(b'original')
        r=E.mover_archivo('a.txt','b.txt')
        self.assertTrue(r['verificado']);self.assertFalse((self.root/'a.txt').exists())
        (self.root/'a.txt').write_bytes(b'ajeno')
        self.assertFalse(E.revertir_cambio(r['id_cambio'])['ok'])
        self.assertEqual((self.root/'a.txt').read_bytes(),b'ajeno')
        (self.root/'a.txt').unlink()
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado'])

    def test_carpeta_solo_se_deshace_vacia(self):
        r=E.crear_carpeta('nueva');self.assertTrue(r['verificado'])
        (self.root/'nueva'/'dato.txt').write_text('x')
        self.assertFalse(E.revertir_cambio(r['id_cambio'])['ok'])
        (self.root/'nueva'/'dato.txt').unlink()
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado'])

    def test_escritura_atomica_preserva_modo_y_usa_temporales_unicos(self):
        archivo=self.root/'a.txt';archivo.write_text('viejo');archivo.chmod(0o640)
        fijo=self.root/'a.txt.jarvis-tmp';fijo.write_text('ajeno')
        p=E.proponer_edicion('a.txt','nuevo')
        self.assertTrue(E.aplicar_edicion(p['id_propuesta'])['verificado'])
        self.assertEqual(archivo.stat().st_mode&0o777,0o640)
        self.assertEqual(fijo.read_text(),'ajeno')
        self.assertFalse(list(self.root.glob('.jarvis-*')))

    def test_fuera_de_carpeta_y_limite(self):
        fuera=self.base/'afuera.txt';fuera.write_text('no tocar')
        (self.root/'enlace').symlink_to(fuera)
        self.assertFalse(E.copiar_archivo('enlace','b.txt')['ok'])
        self.assertFalse(E.crear_carpeta('../otra')['ok'])
        (self.root/'grande').write_bytes(b'x'*100001)
        with patch.object(E,'MAX_BYTES_COPIAR',100000):self.assertFalse(E.mover_archivo('grande','otro')['ok'])
        self.assertTrue((self.root/'grande').exists())

    def test_registro_falla_antes_de_escribir_no_modifica_archivo(self):
        with patch.object(E,'_guardar_json',side_effect=OSError('disco')):
            r=E.crear_archivo('a.txt','nuevo')
        self.assertFalse(r['ok']);self.assertFalse((self.root/'a.txt').exists())

    def test_registro_falla_despues_de_escribir_lo_informa_y_permite_recuperar(self):
        original=E._guardar_json;veces=[0]
        def guardar(carpeta,ident,datos):
            veces[0]+=1
            if veces[0]==2:raise OSError('disco')
            return original(carpeta,ident,datos)
        with patch.object(E,'_guardar_json',side_effect=guardar):
            r=E.crear_archivo('a.txt','nuevo')
        self.assertFalse(r['ok']);self.assertTrue(r['escrito']);self.assertEqual((self.root/'a.txt').read_text(),'nuevo')
        cambios=E.listar_cambios()['cambios']
        self.assertEqual(cambios[0]['estado'],'registro_pendiente')
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado'])

    def test_registro_preparado_no_aplicado_no_se_ofrece_como_activo(self):
        original=E._escribir_atomico
        def escribir(destino,datos,exclusivo=False):
            if destino.parent==self.root:raise OSError('fallo antes de escribir')
            return original(destino,datos,exclusivo)
        with patch.object(E,'_escribir_atomico',side_effect=escribir):
            r=E.crear_archivo('a.txt','nuevo')
        self.assertFalse(r['ok'])
        cambios=E.listar_cambios()['cambios']
        self.assertFalse(cambios[0]['aplicado']);self.assertEqual(cambios[0]['estado'],'no_aplicado')

    def test_reemplazo_literal_preserva_resto_y_requiere_permiso(self):
        archivo=self.root/'a.txt';archivo.write_text('uno\ndos\ntres\n')
        permisos=[]
        r=J.ejecutar_herramienta('reemplazar_texto',{'ruta':'a.txt','texto_actual':'dos','texto_nuevo':'segundo'},lambda t:permisos.append(t) or True,{})
        self.assertTrue(r['verificado']);self.assertEqual(archivo.read_text(),'uno\nsegundo\ntres\n')
        self.assertEqual(len(permisos),1);self.assertIn('-dos',permisos[0])
        self.assertTrue(E.revertir_cambio(r['id_cambio'])['verificado'])

    def test_reemplazo_ambiguo_no_pide_permiso_y_todas_es_explicito(self):
        archivo=self.root/'a.txt';archivo.write_text('hola hola')
        r=J.ejecutar_herramienta('reemplazar_texto',{'ruta':'a.txt','texto_actual':'hola','texto_nuevo':'adios'},lambda _:self.fail('No debe preguntar'),{})
        self.assertFalse(r['ok']);self.assertEqual(archivo.read_text(),'hola hola')
        r=J.ejecutar_herramienta('reemplazar_texto',{'ruta':'a.txt','texto_actual':'hola','texto_nuevo':'adios','todas':True},lambda _:False,{})
        self.assertFalse(r['ok']);self.assertEqual(archivo.read_text(),'hola hola')

    def test_edicion_pedida_pasa_propuesta_a_permiso_sin_otro_si(self):
        archivo=self.root/'a.txt';archivo.write_text('hola')
        tool={'role':'assistant','content':'','tool_calls':[{'function':{'name':'proponer_edicion','arguments':{'ruta':'a.txt','contenido_nuevo':'adios'}}}]}
        permisos=[]
        r=J.ejecutar_turno([{'role':'user','content':'Cambia el archivo a.txt a adios'}],lambda _:tool,lambda t:permisos.append(t) or True,{},mostrar=lambda _:None)
        self.assertEqual(archivo.read_text(),'adios');self.assertEqual(len(permisos),1);self.assertIn('comprobado',r)

    def test_propuesta_sin_escribir_no_se_aplica_automaticamente(self):
        archivo=self.root/'a.txt';archivo.write_text('hola')
        cola=iter([{'role':'assistant','content':'','tool_calls':[{'function':{'name':'proponer_edicion','arguments':{'ruta':'a.txt','contenido_nuevo':'adios'}}}]},
                   {'role':'assistant','content':'Preparado.'}])
        J.ejecutar_turno([{'role':'user','content':'Cambia el texto como propuesta, sin escribir'}],lambda _:next(cola),lambda _:self.fail('No debe pedir permiso'),{},mostrar=lambda _:None)
        self.assertEqual(archivo.read_text(),'hola')

    def test_controlador_pide_permiso_y_historial_humano(self):
        (self.root/'a con espacio.txt').write_text('x')
        permisos=[];state={}
        def ejecutar(n,a):return J.ejecutar_herramienta(n,a,lambda t:permisos.append(t) or True,state)
        handled,texto=comando_archivos('/copiar "a con espacio.txt" "copia.txt"',[],state,ejecutar)
        self.assertTrue(handled);self.assertEqual(len(permisos),1);self.assertIn('comprobado',texto)
        handled,texto=comando_archivos('/cambios',[],state,ejecutar)
        self.assertTrue(handled);self.assertIn('copia.txt',texto)
        handled,texto=comando_archivos('/deshacer 1',[],state,ejecutar)
        self.assertTrue(handled);self.assertFalse((self.root/'copia.txt').exists())
        self.assertEqual(len(permisos),2)


if __name__=='__main__':unittest.main()
