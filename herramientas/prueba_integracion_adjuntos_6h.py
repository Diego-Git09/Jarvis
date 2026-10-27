"""Fronteras públicas: límites por tanda, worker y resumen local explícito."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tandas_documentales as T
import resumen_documental as R
from interfaz_local import comando_local


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        for campo,nombre in [('RAIZ','indice'),('CONFIG','limites.json'),('RECURSOS','recursos.json')]:
            patch.object(T,campo,self.base/nombre).start()

    def archivo(self,nombre,texto):
        p=self.base/nombre;p.write_text(texto);return p

    def local(self,p,e,avisar=None):
        return comando_local(p,[],e,lambda _:False,{'modelo':'qwen3:8b'},lambda:None,None,avisar=avisar)

    def test_cache_no_rebasa_cupo_global_ni_recuperacion(self):
        T.configurar(dict(T.DEFAULT,trozo=400,trozos_tanda=10))
        archivos=[self.archivo(f'{letra}.txt',(f'CLAVE_{letra} '+'dato '*90+'\n')*20) for letra in ['A','B']]
        for p in archivos:T.indexar(T.crear([p])['id'],False)
        d=T.indexar(T.crear(archivos)['id'],False)
        self.assertEqual(sum(a['trozos_visibles'] for a in d['archivos']),10)
        self.assertEqual(d['archivos'][1]['trozos_visibles'],0)
        for fts in (False,True):
            r=T.buscar(d['id'],'CLAVE_B',limite=20,presupuesto=30000,usar_fts=fts)
            self.assertEqual(r['total_trozos'],10)
            self.assertFalse(any('CLAVE_B' in x['texto'] for x in r['trozos']))

    def test_cache_misma_fuente_no_amplia_resumen_generado(self):
        T.configurar(dict(T.DEFAULT,trozo=400,trozos_tanda=10))
        p=self.archivo('a.txt',('DATO_INICIAL '+'dato '*90+'\n')*20)
        d=T.indexar(T.crear([p])['id'],False)
        # Simula otra tanda que solo puede recibir dos trozos de esa caché.
        d['archivos'][0]['trozos_visibles']=2;T._atomic(T._ruta(d['id']),d)
        def transporte(ruta,*_a,**_k):
            if ruta=='/api/tags':return {'models':[]}
            raise ConnectionError('Modelo sintético no disponible; respaldo extractivo')
        r=R.resumir(d['id'],solicitar=transporte)
        self.assertEqual(r['cobertura'].get('trozos_disponibles'),2)

    def test_indexador_proceso_real_informa_techo_memoria(self):
        d=T.indexar(T.crear([self.archivo('real.txt','DATO_LOCAL\n')])['id'],False)
        a=d['archivos'][0];self.assertEqual(a['estado'],'indexado')
        self.assertIn('aislamiento',a);self.assertIn('sha256_aislado',a)
        self.assertEqual(a['sha256_aislado'],a['hash'])
        self.assertEqual(a['bytes_leidos'],(self.base/'real.txt').stat().st_size)

    def test_memoria_agotada_no_bloquea_siguiente_archivo(self):
        a=self.archivo('malo.txt','dato');b=self.archivo('bien.txt','DATO_BUENO')
        real=T._extraer_unidades
        def leer(item,l,c,r):
            if item['nombre']=='malo.txt':raise MemoryError('Techo de memoria sintético')
            yield from real(item,l,c,r)
        with patch.object(T,'_extraer_unidades',side_effect=leer):
            d=T.indexar(T.crear([a,b])['id'],False)
        self.assertEqual(d['archivos'][0]['estado'],'ilegible');self.assertEqual(d['archivos'][1]['estado'],'indexado')

    def test_recursos_memoria_pide_permiso_y_valida_tipo(self):
        antes=T.recursos();T.comando('/adjuntos recursos mb_proceso=128',{},lambda _:False)
        self.assertEqual(T.recursos(),antes)
        T.comando('/adjuntos recursos mb_proceso=128',{},lambda _:True)
        self.assertEqual(T.recursos()['mb_proceso'],128)
        for invalido in [63,1025,True]:
            with self.assertRaises(ValueError):T.validar_recursos({'mb_proceso':invalido})

    def test_resumen_explicito_sin_tanda_no_llama_modelo(self):
        with patch.object(R,'resumir') as modelo:
            ok,texto=self.local('/resumir tanda generado',{})
        self.assertTrue(ok);self.assertIn('/adjuntar',texto);modelo.assert_not_called()

    def test_resumen_explicito_conecta_callback_y_resultado(self):
        r={'ok':True,'texto':'GENERADO con [F1].','tipo':'GENERADO','cobertura':{},'generacion_completa':True,'cache':{},'fallos':[],'segundos':1}
        e={'_tanda_documentos':'a'*32};avisar=lambda _:None
        with patch.object(R,'resumir',return_value=r) as modelo:
            ok,texto=self.local('/resumir tanda generado 3',e,avisar)
        self.assertTrue(ok);self.assertIn('GENERADO',texto);self.assertEqual(modelo.call_args.kwargs['max_trozos'],3)
        self.assertIs(modelo.call_args.kwargs['progreso'],avisar);self.assertIn('_ultimo_resumen_documental',e)

    def test_resumen_invalido_no_envia(self):
        for numero in ['0','13','abc','1 extra']:
            with patch.object(R,'resumir') as modelo:
                ok,texto=self.local('/resumir tanda generado '+numero,{'_tanda_documentos':'a'*32})
                self.assertTrue(ok);modelo.assert_not_called()

    def test_indexar_desde_comando_local_notifica_inicio_unidades_y_final(self):
        d=T.crear([self.archivo('progreso.txt','DATO_LOCAL\n')]);e={'_tanda_documentos':d['id']};eventos=[];real=T.indexar
        with patch.object(T,'indexar',side_effect=lambda ident,**kw:real(ident,False,**kw)):
            ok,texto=self.local('/indexar',e,eventos.append)
        self.assertTrue(ok);self.assertEqual(eventos[0]['fase'],'iniciando');self.assertEqual(eventos[-1]['fase'],'finalizado')
        self.assertTrue(all(x['tipo']=='indexacion' and x['tanda']==d['id'] for x in eventos))
        self.assertTrue(any(x.get('unidades',0)>0 for x in eventos));self.assertIn('indexado',texto)

    def test_indexar_cancelado_desde_aviso_conserva_final_y_tanda(self):
        d=T.crear([self.archivo('progreso.txt','DATO_LOCAL\n'*300)]);e={'_tanda_documentos':d['id']};eventos=[];real=T.indexar
        def avisar(x):
            eventos.append(x)
            if x.get('unidades',0)>0:T.cancelar_indexacion(d['id'])
        with patch.object(T,'indexar',side_effect=lambda ident,**kw:real(ident,False,**kw)):
            ok,_=self.local('/indexar',e,avisar)
        self.assertTrue(ok);self.assertEqual(eventos[-1]['fase'],'finalizado');self.assertTrue(T.cargar(d['id'])['cancelada'])
        self.assertEqual(e['_tanda_documentos'],d['id'])

    def test_indexar_fallido_siempre_notifica_fin_para_recuperar_controles(self):
        d=T.crear([self.archivo('progreso.txt','DATO_LOCAL\n')]);eventos=[]
        with patch.object(T,'indexar',side_effect=ValueError('Fallo ficticio')):
            ok,texto=self.local('/indexar',{'_tanda_documentos':d['id']},eventos.append)
        self.assertTrue(ok);self.assertIn('Fallo ficticio',texto)
        self.assertEqual([x['fase'] for x in eventos],['iniciando','finalizado'])


if __name__=='__main__':unittest.main()
