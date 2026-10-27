"""Condiciones de documentos: datos, citas, caché y rechazos con transporte falso."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import reservas_documentales as C
import resumen_documental as R
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        for m,k,v in [(T,'RAIZ',self.base/'indice'),(T,'CONFIG',self.base/'limites.json'),(T,'RECURSOS',self.base/'recursos.json'),(R,'CARPETA',self.base/'cache')]:patch.object(m,k,v).start()
        self.reglas=C.cargar();self.llamadas=[]

    def tanda(self,textos):
        paths=[]
        for i,t in enumerate(textos):p=self.base/f'fuente{i}.txt';p.write_text(t);paths.append(p)
        return T.indexar(T.crear(paths)['id'],False)

    def transporte(self,ruta,cuerpo=None,**kw):
        if ruta=='/api/tags':return {'models':[{'name':'qwen3:8b','digest':'a'*64}]}
        self.llamadas.append(cuerpo);d=json.loads(cuerpo['messages'][-1]['content'])
        if 'id_permitido' in d:resumen=d['contenido_documental_no_confiable'];refs=[d['id_permitido']]
        else:resumen=' '.join(m['resumen'] for m in d['resumenes_con_procedencia']);refs=[x for m in d['resumenes_con_procedencia'] for x in m['ref_ids']]
        return {'message':{'content':json.dumps({'resumen':resumen,'ref_ids':refs},ensure_ascii=False)}}

    def resumir(self,d,transporte=None):return R.resumir(d['id'],solicitar=transporte or self.transporte)

    def test_detecta_negativa_condicion_e_incertidumbre_sin_reescribir(self):
        t='No publiques todavía. Solo con permiso. Fecha tentativa. Entrega confirmada.'
        f=C.extraer(t,self.reglas)
        self.assertEqual(C.textos(f),['No publiques todavía.','Solo con permiso.','Fecha tentativa.'])

    def test_no_confunde_no_embebido_y_aprobado_con_una_negativa(self):
        self.assertEqual(C.extraer('Proyecto Noria confirmado. Inventario aprobado.',self.reglas),[])

    def test_linea_envuelta_y_cita_con_puntuacion_conservan_el_fragmento(self):
        t='El informe dice «No usar. Solo ejemplo». La fecha no se ha\naprobado.'
        self.assertEqual(C.textos(C.extraer(t,self.reglas)),['El informe dice «No usar. Solo ejemplo».','La fecha no se ha\naprobado.'])

    def test_mapa_que_omite_reserva_no_se_disfraza_de_generacion_completa(self):
        d=self.tanda(['Presupuesto 713 para SUM_CAUT_73. Aún no se ha decidido cuál es válido.'])
        def omitir(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat':r['message']['content']=json.dumps({'resumen':'SUM_CAUT_73 tiene presupuesto 713.','ref_ids':['R0001']})
            return r
        r=self.resumir(d,omitir)
        self.assertFalse(r['generacion_completa']);self.assertIn('Aún no se ha decidido',r['texto']);self.assertTrue(r['fallos'])

    def test_mapa_omitido_se_corrige_una_vez_y_luego_usa_cache(self):
        d=self.tanda(['Presupuesto 713 para SUM_CAUT_73. No publiques todavía.'])
        def primera(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat' and len(self.llamadas)==1:r['message']['content']=json.dumps({'resumen':'SUM_CAUT_73 tiene presupuesto 713.','ref_ids':['R0001']})
            return r
        r=self.resumir(d,primera);self.assertTrue(r['generacion_completa']);self.assertIn('No publiques todavía.',r['texto'])
        self.assertEqual(r['llamadas_generacion'],2);cache=self.resumir(d,primera)
        self.assertEqual(cache['llamadas_generacion'],0);self.assertEqual(cache['texto'],r['texto'])

    def test_reduccion_que_omite_reserva_conserva_mapas_y_sus_fuentes(self):
        d=self.tanda(['Proyecto SUM_A73. No instalar todavía.','Proyecto SUM_B84. La entrega sigue pendiente.'])
        def omitir(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat' and 'resumenes_con_procedencia' in json.loads(cuerpo['messages'][-1]['content']):
                r['message']['content']=json.dumps({'resumen':'Proyectos SUM_A73 y SUM_B84.','ref_ids':['R0001','R0002']})
            return r
        r=self.resumir(d,omitir);self.assertFalse(r['generacion_completa']);self.assertIn('No instalar todavía.',r['texto'])
        self.assertIn('La entrega sigue pendiente.',r['texto']);self.assertEqual(len(r['refs']),2)

    def test_inversion_de_no_aprobado_no_pasa_por_conservar_numero(self):
        d=self.tanda(['Plan SUM_C73. Presupuesto 713. No está aprobado.'])
        def invertir(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat':r['message']['content']=json.dumps({'resumen':'Plan SUM_C73 aprobado con presupuesto 713.','ref_ids':['R0001']})
            return r
        r=self.resumir(d,invertir);self.assertFalse(r['generacion_completa']);self.assertIn('No está aprobado.',r['texto'])
        self.assertNotIn('Plan SUM_C73 aprobado',r['texto'])

    def test_mapa_cacheado_sin_reserva_se_rechaza(self):
        d=self.tanda(['Plan SUM_C73. No publiques todavía.']);self.resumir(d);real=R._leer_cache
        def cambiar(clave):
            r=real(clave)
            return dict(r,resumen='Plan SUM_C73.') if r else r
        with patch.object(R,'_leer_cache',side_effect=cambiar):r=self.resumir(d)
        self.assertFalse(r['generacion_completa']);self.assertIn('No publiques todavía.',r['texto'])

    def test_fallback_recupera_reserva_posterior_a_los_primeros_trescientos_caracteres(self):
        t='Plan SUM_C73. '+('Detalles del ejemplo. '*30)+'No instales paquetes sin permiso.'
        d=self.tanda([t])
        def fallo(ruta,cuerpo=None,**kw):
            if ruta=='/api/chat':raise ConnectionError('Transporte falso falló')
            return self.transporte(ruta,cuerpo,**kw)
        r=self.resumir(d,fallo);self.assertIn('No instales paquetes sin permiso.',r['texto']);self.assertFalse(r['generacion_completa'])

    def test_diccionario_invalido_no_desactiva_controles_ni_genera(self):
        p=self.base/'reglas.json';p.write_text('{mal')
        d=self.tanda(['Plan SUM_C73. No publiques.'])
        with patch.object(C,'RUTA',p):r=self.resumir(d)
        self.assertFalse(r['ok']);self.assertEqual(self.llamadas,[])

    def test_diccionario_es_literal_y_no_expande_regex(self):
        p=self.base/'reglas.json';p.write_text(json.dumps({'version':1,'categorias':{'especial':{'palabras':[],'frases':['x.*y'],'prefijos':[]}}}))
        with patch.object(C,'RUTA',p):reglas=C.cargar()
        self.assertEqual(C.extraer('xAAAAy',reglas),[]);self.assertTrue(C.extraer('x.*y',reglas))

    def test_perfil_de_condiciones_no_trunca_silenciosamente(self):
        t=' '.join(f'No instales paquete P{i}.' for i in range(8));fragmentos=C.extraer(t,self.reglas)
        self.assertEqual(len(fragmentos),8)
        with self.assertRaises(ValueError):C.validar_capacidad(fragmentos)

    def test_cache_de_reduccion_sin_reserva_tampoco_se_acepta(self):
        d=self.tanda(['Plan SUM_A73. No publiques todavía.','Plan SUM_B84. Falta confirmar.'])
        self.resumir(d);real=R._leer_cache
        def quitar(clave):
            r=real(clave)
            return dict(r,resumen='Plan SUM_A73 y SUM_B84.') if r and r['ref_ids']!=['FUENTE'] else r
        with patch.object(R,'_leer_cache',side_effect=quitar):r=self.resumir(d)
        self.assertFalse(r['generacion_completa']);self.assertIn('No publiques todavía.',r['texto']);self.assertIn('Falta confirmar.',r['texto'])

    def test_muchas_condiciones_conserva_extractos_sin_llamar_generacion(self):
        frases=[f'No instales paquete P{i}.' for i in range(8)]
        d=self.tanda([' '.join(frases)]);r=self.resumir(d)
        self.assertFalse(r['generacion_completa']);self.assertEqual(self.llamadas,[])
        self.assertTrue(all(f in r['texto'] for f in frases));self.assertIn('perfil',str(r['fallos']))

    def test_cambio_de_diccionario_invalida_cache_sin_cambiar_fuente(self):
        p=self.base/'reglas.json';reglas=json.loads(C.RUTA.read_text());p.write_text(json.dumps(reglas))
        d=self.tanda(['Plan ROMBO_X91. Estado naranja.'])
        def omitir(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat':r['message']['content']=json.dumps({'resumen':'Plan ROMBO_X91.','ref_ids':['R0001']})
            return r
        with patch.object(C,'RUTA',p):
            a=self.resumir(d,omitir);self.assertTrue(a['generacion_completa'])
            reglas['categorias']['incertidumbre']['frases'].append('estado naranja');p.write_text(json.dumps(reglas))
            b=self.resumir(d)
        self.assertTrue(b['generacion_completa']);self.assertEqual(b['cache']['mapas'],0)
        self.assertNotEqual(a['reglas_reservas_sha256'],b['reglas_reservas_sha256']);self.assertIn('Estado naranja.',b['texto'])

    def test_fuente_revocada_no_devuelve_reservas_en_metadatos(self):
        d=self.tanda(['No publiques EJEMPLO_PRIVADO_73.']);real=R._verificar;revocada=False
        def verificar(f,control):
            if revocada:raise T.L.FueraDeAlcance('Lectura revocada sintéticamente')
            return real(f,control)
        def revocar(ruta,cuerpo=None,**kw):
            nonlocal revocada
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat':revocada=True
            return r
        with patch.object(R,'_verificar',side_effect=verificar):r=self.resumir(d,revocar)
        self.assertFalse(r['ok']);self.assertNotIn('EJEMPLO_PRIVADO_73',json.dumps(r,ensure_ascii=False))


if __name__=='__main__':unittest.main()
