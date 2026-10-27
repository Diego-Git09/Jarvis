"""Contrato de resúmenes con fuentes sintéticas: nunca consulta Ollama real."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import resumen_documental as R
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ)
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.parches=[patch.object(T,'RAIZ',self.base/'indice'),
                      patch.object(T,'CONFIG',self.base/'limites.json'),
                      patch.object(T,'RECURSOS',self.base/'recursos.json'),
                      patch.object(R,'CARPETA',self.base/'cache')]
        for parche in self.parches:parche.start();self.addCleanup(parche.stop)
        self.llamadas=[];self.digest='a'*64

    def tanda(self,textos=None):
        textos=textos or ['El proyecto sintético se llama Rosa. Presupuesto confirmado: 42.']
        paths=[]
        for n,texto in enumerate(textos):
            p=self.base/f'fuente{n}.txt';p.write_text(texto,encoding='utf-8');paths.append(p)
        d=T.indexar(T.crear(paths)['id'],False)
        return d,paths

    def transporte(self,ruta,cuerpo=None,timeout=5):
        self.llamadas.append((ruta,cuerpo,timeout))
        if ruta=='/api/tags':return {'models':[{'name':'qwen3:8b','digest':self.digest}]}
        dato=json.loads(cuerpo['messages'][-1]['content'])
        if 'id_permitido' in dato:
            resultado={'resumen':'El proyecto Rosa dispone de presupuesto 42. '+' '.join(dato.get('literales_que_debes_conservar',[])),'ref_ids':[dato['id_permitido']]}
        else:
            resultado={'resumen':' '.join(m['resumen'] for m in dato['resumenes_con_procedencia']),
                       'ref_ids':[r for m in dato['resumenes_con_procedencia'] for r in m['ref_ids']]}
        return {'message':{'content':json.dumps(resultado,ensure_ascii=False)},'prompt_eval_count':160,'eval_count':34}

    def resumir(self,d,**kw):return R.resumir(d['id'],solicitar=kw.pop('solicitar',self.transporte),**kw)

    def test_mapa_generado_y_referencia_del_controlador(self):
        d,_=self.tanda();r=self.resumir(d)
        self.assertTrue(r['ok']);self.assertTrue(r['generacion_completa']);self.assertEqual(r['tipo'],'GENERADO')
        self.assertIn('fuente0.txt',r['refs'][0]['referencia']);self.assertIn('42',r['texto'])
        self.assertEqual(r['fallos'],[]);self.assertEqual(r['llamadas_generacion'],1)

    def test_reduccion_varias_fuentes(self):
        d,_=self.tanda(['dato uno','dato dos']);r=self.resumir(d)
        self.assertTrue(r['generacion_completa']);self.assertEqual(r['llamadas_generacion'],3)
        self.assertEqual(len(r['refs']),2);self.assertEqual(r['metricas_modelo'][-1]['fase'],'reduccion')

    def test_reduccion_que_omite_cifra_no_se_presenta_completa(self):
        d,_=self.tanda(['dato uno','dato dos'])
        def incompleta(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat' and 'resumenes_con_procedencia' in json.loads(cuerpo['messages'][-1]['content']):
                dato=json.loads(r['message']['content']);dato['resumen']='El proyecto dispone de presupuesto.';r['message']['content']=json.dumps(dato)
            return r
        r=self.resumir(d,solicitar=incompleta)
        self.assertFalse(r['generacion_completa']);self.assertIn('42',r['texto']);self.assertTrue(r['fallos'])
        self.assertEqual(r['llamadas_generacion'],4);self.assertEqual(len(r['refs']),2)

    def test_reduccion_que_omite_fuente_se_corrige_una_vez(self):
        d,_=self.tanda(['dato uno','dato dos']);veces=0
        def primera_incompleta(ruta,cuerpo=None,**kw):
            nonlocal veces
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat' and 'resumenes_con_procedencia' in json.loads(cuerpo['messages'][-1]['content']):
                veces+=1
                if veces==1:
                    dato=json.loads(r['message']['content']);dato['ref_ids']=dato['ref_ids'][:1];r['message']['content']=json.dumps(dato)
            return r
        r=self.resumir(d,solicitar=primera_incompleta)
        self.assertTrue(r['generacion_completa']);self.assertEqual(r['llamadas_generacion'],4);self.assertEqual(len(r['refs']),2)
        cache=self.resumir(d,solicitar=primera_incompleta)
        self.assertEqual(cache['llamadas_generacion'],0);self.assertEqual(cache['texto'],r['texto'])
        self.assertTrue(r['avisos_ejecucion']);self.assertEqual(cache['avisos_ejecucion'],[])

    def test_un_numero_distinto_que_contiene_el_literal_no_lo_suplanta(self):
        mapas=[{'resultado':{'resumen':'Presupuesto 12 para NOMBRE_A17.','ref_ids':['R0001']}}]
        for numero in ['312','-12','12.4','12:00']:
            with self.subTest(numero=numero),self.assertRaises(ValueError):
                R._comprobar_reduccion({'resumen':f'NOMBRE_A17 tiene presupuesto {numero}.','ref_ids':['R0001']},mapas,{'R0001'})
        R._comprobar_reduccion({'resumen':'NOMBRE_A17 tiene presupuesto 12.','ref_ids':['R0001']},mapas,{'R0001'})

    def test_cache_de_reduccion_incompleta_no_se_muestra_completa(self):
        d,_=self.tanda(['dato uno','dato dos']);real=R._leer_cache
        self.resumir(d)
        def devolver_incompleta(clave):
            r=real(clave)
            if r and r.get('ref_ids')!=['FUENTE']:return {'resumen':'Solo dato incompleto.','ref_ids':r['ref_ids']}
            return r
        with patch.object(R,'_leer_cache',side_effect=devolver_incompleta):r=self.resumir(d)
        self.assertFalse(r['generacion_completa']);self.assertIn('42',r['texto']);self.assertNotIn('Solo dato incompleto',r['texto'])

    def test_mapa_que_omite_literal_usa_texto_fuente_no_generacion_rechazada(self):
        d,_=self.tanda(['Presupuesto confirmado 42 para NOMBRE_A17.'])
        def mapa_malo(ruta,cuerpo=None,**kw):
            r=self.transporte(ruta,cuerpo,**kw)
            if ruta=='/api/chat':
                r['message']['content']=json.dumps({'resumen':'VALOR_INVENTADO','ref_ids':['R0001']})
            return r
        r=self.resumir(d,solicitar=mapa_malo)
        self.assertFalse(r['generacion_completa']);self.assertEqual(r['tipo'],'EXTRACTIVO')
        self.assertIn('42',r['texto']);self.assertIn('NOMBRE_A17',r['texto']);self.assertNotIn('VALOR_INVENTADO',r['texto'])

    def test_mapa_cacheado_incompleto_tampoco_se_disfraza_de_extracto(self):
        d,_=self.tanda(['Presupuesto confirmado 42 para NOMBRE_A17.']);self.resumir(d);real=R._leer_cache
        def alterado(clave):
            r=real(clave)
            return dict(r,resumen='VALOR_INVENTADO') if r else r
        with patch.object(R,'_leer_cache',side_effect=alterado):r=self.resumir(d)
        self.assertEqual(r['tipo'],'EXTRACTIVO');self.assertNotIn('VALOR_INVENTADO',r['texto']);self.assertIn('42',r['texto'])

    def test_cobertura_no_equivale_a_original(self):
        d,_=self.tanda(['línea de datos\n'*700]);r=self.resumir(d,max_trozos=2)
        c=r['cobertura'];self.assertEqual(c['trozos_seleccionados'],2)
        self.assertGreater(c['trozos_disponibles'],2);self.assertLess(c['porcentaje_trozos_seleccionados'],100)
        self.assertIsNone(c['fuentes'][0]['porcentaje_original_recibido_por_modelo'])
        self.assertIn('No acredita lectura completa',r['texto'])

    def test_seleccion_reparte_fuentes_y_extremos(self):
        d,_=self.tanda(['DATOS\n'*1000,'DATOS OTRA FUENTE\n'*500]);r=self.resumir(d,max_trozos=4)
        self.assertEqual([f['trozos_seleccionados'] for f in r['cobertura']['fuentes']],[2,2])
        self.assertEqual(len(r['seleccion']),4)

    def test_fuentes_mayores_que_cupo_declara_omitidas(self):
        d,_=self.tanda(['uno','dos','tres','cuatro']);r=self.resumir(d,max_trozos=2)
        self.assertEqual(r['cobertura']['fuentes_manifestadas'],4)
        self.assertEqual(sum(f['trozos_seleccionados']>0 for f in r['cobertura']['fuentes']),2)

    def test_cache_reutiliza_sin_nuevas_generaciones(self):
        d,_=self.tanda(['uno','dos']);a=self.resumir(d);self.llamadas.clear();b=self.resumir(d)
        self.assertTrue(a['generacion_completa']);self.assertTrue(b['generacion_completa'])
        self.assertEqual(b['cache']['mapas'],2);self.assertEqual(b['cache']['reduccion'],1)
        self.assertEqual(b['llamadas_generacion'],0);self.assertEqual(b['cobertura']['trozos_enviados_esta_ejecucion'],0)
        self.assertEqual([x[0] for x in self.llamadas],['/api/tags'])

    def test_cache_permisos_privados(self):
        d,_=self.tanda();self.resumir(d)
        self.assertEqual(os.stat(R.CARPETA).st_mode&0o777,0o700)
        self.assertTrue(list(R.CARPETA.glob('*.json')))
        for p in R.CARPETA.glob('*.json'):self.assertEqual(p.stat().st_mode&0o777,0o600)

    def test_digest_distinto_invalida_cache(self):
        d,_=self.tanda();self.resumir(d);self.digest='b'*64;r=self.resumir(d)
        self.assertEqual(r['cache']['mapas'],0);self.assertEqual(r['llamadas_generacion'],1)

    def test_sin_digest_no_cache(self):
        d,_=self.tanda();self.digest='';a=self.resumir(d);b=self.resumir(d)
        self.assertEqual(a['cache']['guardados'],0);self.assertEqual(b['cache']['mapas'],0)
        self.assertIn('digest',' '.join(b['avisos']))

    def test_parametros_distintos_invalida_cache(self):
        d,_=self.tanda();self.resumir(d)
        with patch.object(R,'OPCIONES',dict(R.OPCIONES,seed=17)):r=self.resumir(d)
        self.assertEqual(r['cache']['mapas'],0)

    def test_huella_cache_corrupta_se_regenera(self):
        d,_=self.tanda();self.resumir(d);p=next(R.CARPETA.glob('*.json'));j=json.loads(p.read_text());j['resultado']['resumen']='alterado';p.write_text(json.dumps(j))
        r=self.resumir(d);self.assertEqual(r['cache']['mapas'],0);self.assertNotIn('alterado',r['texto'])

    def test_fuente_cambiada_no_usa_cache(self):
        d,p=self.tanda();self.resumir(d);p[0].write_text('Otro contenido')
        r=self.resumir(d);self.assertFalse(r['ok']);self.assertFalse(r['refs']);self.assertEqual(r['llamadas_generacion'],0)

    def test_fuente_cambia_durante_mapa_no_entrega_texto(self):
        d,p=self.tanda()
        def transporte(ruta,cuerpo=None,timeout=5):
            r=self.transporte(ruta,cuerpo,timeout)
            if ruta=='/api/chat':p[0].write_text('Cambio posterior')
            return r
        r=self.resumir(d,solicitar=transporte);self.assertFalse(r['ok']);self.assertNotIn('presupuesto 42',r['texto'])

    def test_cambio_durante_reduccion_no_entrega_mapas_viejos(self):
        d,p=self.tanda(['uno','dos'])
        def transporte(ruta,cuerpo=None,timeout=5):
            r=self.transporte(ruta,cuerpo,timeout)
            if cuerpo and 'resumenes_con_procedencia' in cuerpo['messages'][-1]['content']:p[0].write_text('cambio al reducir')
            return r
        r=self.resumir(d,solicitar=transporte);self.assertFalse(r['ok']);self.assertFalse(r['refs'])

    def test_fuente_desautorizada_incluso_con_cache(self):
        d,_=self.tanda();self.resumir(d)
        with patch.object(R.L,'_resolver',side_effect=R.L.FueraDeAlcance('Permiso retirado')):r=self.resumir(d)
        self.assertFalse(r['ok']);self.assertEqual(r['llamadas_generacion'],0)

    def test_lector_anterior_no_recupera_texto(self):
        d,_=self.tanda();d['lector_version']=T.LECTOR_VERSION-1;T._atomic(T._ruta(d['id']),d)
        r=self.resumir(d);self.assertFalse(r['ok']);self.assertIn('/indexar',r['texto']);self.assertFalse(self.llamadas)

    def test_version_fuente_anterior_no_recupera_texto(self):
        d,_=self.tanda();d['archivos'][0]['lector_version']=T.LECTOR_VERSION-1;T._atomic(T._ruta(d['id']),d)
        r=self.resumir(d);self.assertFalse(r['ok']);self.assertFalse(self.llamadas)

    def test_indice_enlace_rechazado(self):
        d,_=self.tanda();p=T.RAIZ/'trozos.sqlite';real=T.RAIZ/'original.sqlite';p.rename(real);p.symlink_to(real)
        r=self.resumir(d);self.assertFalse(r['ok']);self.assertFalse(self.llamadas)

    def test_cache_enlace_no_escribe_destino(self):
        d,_=self.tanda();destino=self.base/'otro';destino.mkdir();R.CARPETA.symlink_to(destino,target_is_directory=True)
        r=self.resumir(d);self.assertTrue(r['ok']);self.assertEqual(r['cache']['guardados'],0);self.assertEqual(list(destino.iterdir()),[])

    def test_fuente_pendiente_no_se_simula_completa(self):
        d,p=self.tanda();nuevo=self.base/'pendiente.txt';nuevo.write_text('no indexado');d['archivos'].append({'ruta':str(nuevo),'nombre':nuevo.name});T._atomic(T._ruta(d['id']),d)
        r=self.resumir(d);self.assertTrue(r['ok']);self.assertFalse(r['generacion_completa']);self.assertEqual(r['cobertura']['fuentes_manifestadas'],2)

    def test_respuesta_vacia_fallback_explicito(self):
        d,_=self.tanda()
        def transporte(ruta,cuerpo=None,timeout=5):return self.transporte(ruta,cuerpo,timeout) if ruta=='/api/tags' else {'message':{'content':''}}
        r=self.resumir(d,solicitar=transporte);self.assertTrue(r['ok']);self.assertEqual(r['tipo'],'EXTRACTIVO')
        self.assertFalse(r['generacion_completa']);self.assertTrue(r['fallos']);self.assertIn('El proyecto sintético',r['texto'])

    def test_error_transporte_no_finge_generacion(self):
        d,_=self.tanda()
        def transporte(ruta,cuerpo=None,timeout=5):
            if ruta=='/api/tags':return self.transporte(ruta,cuerpo,timeout)
            raise ConnectionError('API key=secreto-ficticio')
        r=self.resumir(d,solicitar=transporte);self.assertEqual(r['tipo'],'EXTRACTIVO');self.assertFalse(r['generacion_completa'])
        self.assertNotIn('secreto-ficticio',json.dumps(r))

    def test_ref_ajena_no_se_presenta(self):
        d,_=self.tanda()
        def transporte(ruta,cuerpo=None,timeout=5):
            if ruta=='/api/tags':return self.transporte(ruta,cuerpo,timeout)
            return {'message':{'content':json.dumps({'resumen':'Hecho inventado','ref_ids':['R9999']})}}
        r=self.resumir(d,solicitar=transporte);self.assertEqual(r['tipo'],'EXTRACTIVO');self.assertNotIn('inventado',r['texto'])

    def test_cita_pagina_modelo_rechazada(self):
        with self.assertRaises(ValueError):R._validar_resumen({'resumen':'Según página 99 ocurre X.','ref_ids':['R0001']},{'R0001'})

    def test_id_interno_en_parrafo_rechazado(self):
        with self.assertRaises(ValueError):R._validar_resumen({'resumen':'Dato [R0001].','ref_ids':['R0001']},{'R0001'})

    def test_tools_del_modelo_no_se_ejecutan(self):
        d,_=self.tanda()
        def transporte(ruta,cuerpo=None,timeout=5):
            if ruta=='/api/tags':return self.transporte(ruta,cuerpo,timeout)
            return {'message':{'content':'{}','tool_calls':[{'function':{'name':'escribir'}}]}}
        r=self.resumir(d,solicitar=transporte);self.assertEqual(r['tipo'],'EXTRACTIVO');self.assertFalse(r['generacion_completa'])

    def test_documentos_y_generado_redactados(self):
        d,_=self.tanda(['api_key=secreto-sintetico\nDato publico: Rosa'])
        def transporte(ruta,cuerpo=None,timeout=5):
            r=self.transporte(ruta,cuerpo,timeout)
            if cuerpo:
                self.assertNotIn('secreto-sintetico',json.dumps(cuerpo))
                r['message']['content']=json.dumps({'resumen':'api_key=otra-clave-ficticia','ref_ids':['R0001']})
            return r
        r=self.resumir(d,solicitar=transporte);self.assertTrue(r['ok']);self.assertNotIn('otra-clave-ficticia',json.dumps(r))
        for p in R.CARPETA.glob('*.json'):self.assertNotIn('otra-clave-ficticia',p.read_text())

    def test_cuerpo_sin_herramientas_y_presupuesto(self):
        d,_=self.tanda();self.resumir(d)
        cuerpo=next(c for ruta,c,_ in self.llamadas if ruta=='/api/chat')
        self.assertNotIn('tools',cuerpo);self.assertFalse(cuerpo['think']);self.assertFalse(cuerpo['stream'])
        self.assertLessEqual(cuerpo['options']['num_ctx'],8192);self.assertEqual(cuerpo['options']['num_predict'],256)
        self.assertTrue(all(0<t<=35 for ruta,_,t in self.llamadas if ruta=='/api/chat'))

    def test_presupuesto_bytes_evitar_contexto_excesivo(self):
        with self.assertRaisesRegex(ValueError,'presupuesto'):
            R._generar(self.transporte,'qwen3:8b',[{'role':'user','content':'漢'*3000}],{'R0001'},time.monotonic()+10,0,lambda:None)
        self.assertEqual(self.llamadas,[])

    def test_reduccion_recorta_mapas_sin_omitir_fuentes(self):
        mapas=[{'resultado':{'resumen':'漢'*1000,'ref_ids':[f'R{n:04d}']}} for n in range(1,13)]
        mensajes,info=R._mensajes_reduccion(mapas)
        self.assertEqual(info['mapas_recibidos'],12);self.assertEqual(info['mapas_recortados'],12)
        datos=json.loads(mensajes[-1]['content'])
        self.assertEqual(len(datos['resumenes_con_procedencia']),12)
        self.assertLessEqual(sum(len(m['content'].encode()) for m in mensajes)+256+1024,8192)
        self.assertEqual(len(mapas[0]['resultado']['resumen']),1000)

    def test_fallo_reduccion_visible_en_texto(self):
        d,_=self.tanda(['uno','dos'])
        def transporte(ruta,cuerpo=None,timeout=5):
            if cuerpo and 'resumenes_con_procedencia' in cuerpo['messages'][-1]['content']:raise ConnectionError('interrupción sintética')
            return self.transporte(ruta,cuerpo,timeout)
        r=self.resumir(d,solicitar=transporte)
        self.assertTrue(r['ok']);self.assertFalse(r['generacion_completa']);self.assertIn('No se completó toda la generación',r['texto'])

    def test_cancelar_antes_generacion(self):
        d,_=self.tanda()
        def progreso(x):
            if x['fase']=='validando':self.assertTrue(R.cancelar(d['id']))
        r=self.resumir(d,progreso=progreso);self.assertTrue(r['cancelado']);self.assertFalse(r['ok']);self.assertFalse(self.llamadas)
        self.assertFalse(R.cancelar(d['id']))

    def test_cancelar_tras_mapa_guarda_y_reanuda(self):
        d,_=self.tanda(['uno','dos'])
        def progreso(x):
            if x['fase']=='mapa' and x['procesados']==1:R.cancelar(d['id'])
        a=self.resumir(d,progreso=progreso);self.assertTrue(a['cancelado']);self.assertFalse(a['ok'])
        b=self.resumir(d);self.assertTrue(b['generacion_completa']);self.assertEqual(b['cache']['mapas'],1)

    def test_plazo_global_no_equivale_a_exito(self):
        d,_=self.tanda()
        def transporte(ruta,cuerpo=None,timeout=5):
            r=self.transporte(ruta,cuerpo,timeout)
            if ruta=='/api/chat':time.sleep(.025)
            return r
        r=self.resumir(d,solicitar=transporte,timeout_total=.015)
        self.assertTrue(r['plazo_agotado']);self.assertFalse(r['ok']);self.assertFalse(r['generacion_completa'])

    def test_solo_un_trabajo_por_tanda(self):
        d,_=self.tanda();otro=[]
        def progreso(x):
            if x['fase']=='validando':otro.append(self.resumir(d))
        r=self.resumir(d,progreso=progreso);self.assertTrue(r['ok']);self.assertFalse(otro[0]['ok']);self.assertIn('activo',otro[0]['texto'])

    def test_progreso_defectuoso_no_pierde_resultado(self):
        d,_=self.tanda()
        def progreso(_):raise ValueError('interfaz cerrada')
        r=self.resumir(d,progreso=progreso);self.assertTrue(r['ok']);self.assertTrue(r['avisos'])

    def test_modelo_no_instalado_sin_descarga(self):
        d,_=self.tanda();r=self.resumir(d,solicitar=lambda *a,**k:{'models':[]})
        self.assertEqual(r['tipo'],'EXTRACTIVO');self.assertFalse(r['generacion_completa']);self.assertEqual(r['llamadas_generacion'],0)

    def test_modelo_con_derivacion_remota_no_se_usa(self):
        d,_=self.tanda()
        r=self.resumir(d,solicitar=lambda *a,**k:{'models':[{'name':'qwen3:8b','digest':self.digest,'remote_host':'ejemplo.invalid'}]})
        self.assertEqual(r['llamadas_generacion'],0);self.assertFalse(r['generacion_completa'])

    def test_servidor_no_local_rechazado(self):
        d,_=self.tanda()
        with patch.object(R,'en_pruebas',return_value=False),patch.object(R.O,'BASE','https://ejemplo.invalid'),patch.object(R.O,'solicitar') as mock:
            r=R.resumir(d['id'])
        self.assertFalse(r['ok']);mock.assert_not_called()

    def test_pruebas_sin_transporte_no_consultan_real(self):
        d,_=self.tanda()
        with patch.object(R.O,'solicitar') as mock:r=R.resumir(d['id'])
        self.assertFalse(r['ok']);mock.assert_not_called()

    def test_argumentos_invalidos_sin_generacion(self):
        d,_=self.tanda()
        for kw in [{'max_trozos':0},{'max_trozos':13},{'max_trozos':True},{'timeout_total':0},{'timeout_total':float('nan')},{'modelo':'x\n/invalido'}]:
            with self.subTest(kw=kw):self.assertFalse(self.resumir(d,**kw)['ok'])
        self.assertFalse(self.llamadas)

    def test_nombre_cache_por_huella_sin_rutas_de_fuente(self):
        d,p=self.tanda();self.resumir(d)
        for cache in R.CARPETA.glob('*.json'):
            self.assertRegex(cache.name,r'^[a-f0-9]{64}\.json$');self.assertNotIn(str(p[0]),cache.read_text())

    def test_fuentes_indice_y_manifiesto_no_se_modifican(self):
        d,paths=self.tanda();paths+=[T.RAIZ/'trozos.sqlite',T._ruta(d['id'])]
        antes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        r=self.resumir(d);self.assertTrue(r['ok'])
        self.assertEqual(antes,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

    def test_lectura_cache_repara_permisos_de_entradas_anteriores(self):
        d,_=self.tanda();self.resumir(d);p=next(R.CARPETA.glob('*.json'));os.chmod(p,0o644);os.chmod(R.CARPETA,0o755)
        r=self.resumir(d);self.assertEqual(r['cache']['mapas'],1)
        self.assertEqual(p.stat().st_mode&0o777,0o600);self.assertEqual(R.CARPETA.stat().st_mode&0o777,0o700)


if __name__=='__main__':unittest.main()
