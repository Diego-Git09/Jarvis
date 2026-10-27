"""Preparación de tandas: fuentes excluidas, límites y cancelación real local."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=T.L.RAIZ);self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.addCleanup(patch.stopall)
        for k,n in [('RAIZ','indice'),('CONFIG','limites.json'),('RECURSOS','recursos.json')]:patch.object(T,k,self.base/n).start()
    def texto(self,n,t='DATO_BUENO'):
        p=self.base/n;p.write_text(t);return p
    def test_zip_corrupto_se_excluye_sin_bloquear_otro_archivo(self):
        p=self.texto('roto.zip','no es zip');q=self.texto('bien.md')
        d=T.crear([p,q]);self.assertEqual([x['nombre'] for x in d['archivos']],['bien.md']);self.assertEqual(len(d['avisos']),1)
        self.assertIn('roto.zip',T.manifiesto(d));d=T.indexar(d['id'],False);self.assertEqual(d['archivos'][0]['estado'],'indexado')
    def test_zip_traversal_no_deja_miembros_parciales(self):
        p=self.base/'mal.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('bueno.txt','NO_INCORPORAR');z.writestr('../fuera.txt','NO_LEER')
        d=T.crear([p,self.texto('si.txt')]);self.assertEqual([x['nombre'] for x in d['archivos']],['si.txt']);self.assertTrue(d['avisos'])
    def test_todas_fuentes_invalidas_conserva_el_error_original(self):
        with self.assertRaisesRegex(ValueError,'ZIP sin directorio final válido'):T.crear([self.texto('roto.zip','no zip')])
    def test_limite_global_no_se_convierte_en_seleccion_parcial(self):
        T.configurar(dict(T.DEFAULT,archivos=1))
        with self.assertRaises(T.LimiteTanda):T.crear([self.texto('uno.md'),self.texto('dos.md')])
    def test_archivo_grande_en_carpeta_no_excluye_los_demas(self):
        carpeta=self.base/'carpeta';carpeta.mkdir();(carpeta/'bien.md').write_text('DATO_BUENO')
        with (carpeta/'enorme.txt').open('wb') as f:f.truncate(21*1024**2)
        d=T.crear([carpeta]);self.assertEqual([x['nombre'] for x in d['archivos']],['bien.md']);self.assertIn('20 MB',d['avisos'][0])
    def test_preparacion_cancelada_no_cambia_tanda_activa(self):
        anterior=T.crear([self.texto('anterior.md')]);p=T.RAIZ/'activa.json';contenido=p.read_bytes()
        def cancelar():raise InterruptedError('Cancelado')
        with self.assertRaises(InterruptedError):T.crear([self.texto('nuevo.md')],control=cancelar)
        self.assertEqual(p.read_bytes(),contenido)
    def test_preparar_sin_publicar_conserva_seleccion_previa(self):
        T.crear([self.texto('anterior.md')]);p=T.RAIZ/'activa.json';contenido=p.read_bytes()
        d=T.crear([self.texto('nuevo.md')],activar=False)
        self.assertEqual(p.read_bytes(),contenido);self.assertTrue(T._ruta(d['id']).is_file())
    def test_progreso_entrega_cantidad_y_tiempo(self):
        eventos=[];T.crear([self.texto('uno.md'),self.texto('dos.md')],progreso=eventos.append)
        self.assertEqual([x['archivos'] for x in eventos],[1,2]);self.assertTrue(all(x['segundos']>=0 for x in eventos))
    def test_gitignore_grande_no_se_omite_silenciosamente(self):
        p=self.base/'repo';p.mkdir();(p/'.gitignore').write_text('privado.txt\n'+'#'*100001);(p/'privado.txt').write_text('NO_INCORPORAR')
        with self.assertRaisesRegex(ValueError,'gitignore supera'):T.crear([p])
    def test_hash_cambiado_con_firma_conservada_no_devuelve_cache(self):
        import os
        p=self.texto('modificado.md','DATO_ORIGINAL');d=T.indexar(T.crear([p])['id'],False);s=p.stat()
        p.write_text('DATO_CAMBIADO');os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns))
        self.assertEqual(p.stat().st_size,s.st_size);self.assertFalse(T.buscar(d['id'],'DATO_ORIGINAL')['trozos'])

    def test_directorio_demasiado_grande_no_se_ordena_ni_publica(self):
        from unittest.mock import Mock,MagicMock
        anterior=T.crear([self.texto('previo.md')]);contenido=(T.RAIZ/'activa.json').read_bytes()
        carpeta=self.base/'repo';carpeta.mkdir()
        entrada=Mock(name='archivo');entrada.name='omitido.txt';entrada.is_dir.return_value=False
        listado=MagicMock();listado.__enter__.return_value=iter([entrada]*10001)
        with patch.object(T.os,'scandir',return_value=listado),self.assertRaisesRegex(ValueError,'metadatos'):
            T.crear([carpeta])
        self.assertEqual((T.RAIZ/'activa.json').read_bytes(),contenido)

    def test_cambio_de_memoria_no_reutiliza_lector_de_metadatos(self):
        p=self.texto('fuente.txt');llamadas=[]
        def extraer(item,limites,control,recursos):
            llamadas.append(recursos['mb_proceso'])
            yield item['nombre'],'DATO_MEMORIA_'+str(recursos['mb_proceso'])
        with patch.object(T,'_extraer_unidades',side_effect=extraer):
            inicial=T.indexar(T.crear([p])['id'],False)
            T.configurar_recursos(dict(T.RECURSOS_DEFAULT,mb_proceso=512))
            posterior=T.indexar(T.crear([p])['id'],False)
        self.assertEqual(llamadas,[256,512]);self.assertNotEqual(inicial['archivos'][0]['clave'],posterior['archivos'][0]['clave'])
        self.assertTrue(any('DATO_MEMORIA_512' in x['texto'] for x in T.buscar(posterior['id'],'DATO_MEMORIA_512')['trozos']))

    def test_exclusiones_masivas_conservan_total_sin_manifesto_ilimitado(self):
        carpeta=self.base/'repo';carpeta.mkdir();(carpeta/'bien.md').write_text('DATO_VALIDO')
        for i in range(300):
            with (carpeta/f'excluido{i}.txt').open('wb') as f:f.truncate(21*1024**2)
        d=T.crear([carpeta])
        self.assertEqual(d['fuentes_excluidas_total'],300);self.assertEqual(len(d['excluidas']),200)
        self.assertEqual(len(d['archivos']),1);self.assertIn('Omití 100 detalles',d['avisos'][0])
        self.assertLess(len(__import__('json').dumps(d)),250000)


if __name__=='__main__':unittest.main()
