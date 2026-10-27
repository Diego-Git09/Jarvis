"""Publicación fija de estado: cola, contenido esperado y lectura posterior."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import estado_ia as E
from cerebro_mcp import ErrorCerebro
from prueba_ampliacion_controles import MemoriaFalsa


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        for k,v in [('DATOS',self.base),('PENDIENTE',self.base/'pendiente.json')]:patch.object(E,k,v).start()
        patch.object(E,'generar',return_value='Estado sintético verificado').start();self.addCleanup(patch.stopall)

    def test_solo_publica_el_titulo_fijo_y_no_los_capitulos(self):
        c=MemoriaFalsa()
        with patch.object(E,'temas',side_effect=AssertionError('No publicar capítulos')):
            r=E.publicar(c)
        self.assertEqual(len(r),1);self.assertEqual(c.d[1]['titulo'],E.TITULO);self.assertFalse(E.PENDIENTE.exists())
        self.assertEqual(json.loads((self.base/'estado_ia_publicado.json').read_text())['documentos'],r)

    def test_fallo_de_guardado_deja_la_cola_sin_recibo_de_exito(self):
        c=MemoriaFalsa()
        with patch.object(c,'publicar_documento',side_effect=ErrorCerebro('MCP falso caído')),self.assertRaises(ErrorCerebro):E.publicar(c)
        d=json.loads(E.PENDIENTE.read_text());self.assertEqual(d['documentos'],[[E.TITULO,'Estado sintético verificado']])
        self.assertFalse((self.base/'estado_ia_publicado.json').exists())

    def test_reintento_actualiza_un_solo_estado_y_conserva_otro_recuerdo(self):
        c=MemoriaFalsa();E.publicar(c)
        otro=c.publicar_documento('JARVIS — Documento ajeno al estado','No modificar')['id']
        with patch.object(E,'generar',return_value='Estado sintético posterior'):E.publicar(c)
        self.assertEqual(len(c.d),2);self.assertEqual(c.d[otro]['contenido'],'No modificar')
        self.assertEqual(c.d[1]['contenido'],'Estado sintético posterior');self.assertEqual(c.cambios,['nuevo','nuevo','corregir_memoria'])

    def test_lectura_posterior_con_titulo_tipo_o_id_distinto_no_confirma(self):
        for campo,valor in [('titulo','Otro'),('tipo','conversacion'),('id',99)]:
            with self.subTest(campo=campo):
                c=MemoriaFalsa();c.publicar_documento(E.TITULO,'Estado',True);original=c.llamar
                def llamar(nombre,args):
                    r=original(nombre,args)
                    if nombre=='consultar_memoria':r['memorias'][0][campo]=valor
                    return r
                with patch.object(c,'llamar',side_effect=llamar),self.assertRaises(ErrorCerebro):c.publicar_documento(E.TITULO,'Estado',True)

    def test_bateria_completa_no_se_confunde_con_focal_posterior(self):
        import os
        raiz=self.base/'registros';reportes=raiz/'reportes';reportes.mkdir(parents=True)
        completa=reportes/'pruebas_control_5.txt';completa.write_text('Total: 1649 pruebas. Archivos con fallos: 0.\n')
        focal=reportes/'pruebas_resumen_documental.txt';focal.write_text('Total: 50 pruebas. Archivos con fallos: 0.\n')
        os.utime(completa,(1,1));os.utime(focal,(2,2))
        with patch.object(E,'REGISTROS',raiz):r=E._ultima_bateria()
        self.assertEqual(r[1],completa);self.assertEqual(r[2],1649)

    def test_cambio_de_destino_antes_de_corregir_no_escribe(self):
        for campo,valor in [('titulo','Otro'),('proyecto','personal'),('tipo','conversacion'),('id',99)]:
            with self.subTest(campo=campo):
                c=MemoriaFalsa();c.publicar_documento(E.TITULO,'Original',True);original=c.llamar
                def llamar(nombre,args):
                    r=original(nombre,args)
                    if nombre=='consultar_memoria':r['memorias'][0][campo]=valor
                    return r
                with patch.object(c,'llamar',side_effect=llamar),self.assertRaises(ErrorCerebro):c.publicar_documento(E.TITULO,'Cambiar',True)
                self.assertEqual(c.cambios,['nuevo']);self.assertEqual(c.d[1]['contenido'],'Original')

    def test_consulta_vacia_no_crea_otra_copia(self):
        c=MemoriaFalsa();c.publicar_documento(E.TITULO,'Original',True);original=c.llamar
        def llamar(nombre,args):return {'ok':True,'memorias':[]} if nombre=='consultar_memoria' else original(nombre,args)
        with patch.object(c,'llamar',side_effect=llamar),self.assertRaises(ErrorCerebro):c.publicar_documento(E.TITULO,'Cambiar',True)
        self.assertEqual(c.cambios,['nuevo']);self.assertEqual(len(c.d),1)


if __name__=='__main__':unittest.main()
