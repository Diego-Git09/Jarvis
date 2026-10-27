"""Redacción antes de IPC/índice con valores ficticios que cruzan bloques."""
import io
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest
from unittest.mock import patch

import evaluar_redaccion_bordes_6h as B
import evaluar_redaccion_larga_6h as G
import lectores_adjuntos as L
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def leer(self,c,largo=False):
        raw,privados=(G if largo else B).preparar(c);item={'nombre':'fuente.env' if c['familia']=='env' else 'fuente.txt'}
        texto=''.join(t for _,t in L.bloques_texto(io.BytesIO(raw),item,200000)).replace('[CREDENCIALES REDACTADAS]','')
        ventanas={v[i:i+8] for v in privados for i in range(len(v)-7)}
        self.assertFalse(any(v in texto for v in ventanas),'El texto filtró una parte del valor ficticio.')
        self.assertIn(B.PUBLICO,texto);return item

    def caso(self,f,enc='utf-8',pos=16127):return {'familia':f,'desplazamiento':pos,'codificacion':enc}

    def test_campo_con_espacios_entre_etiqueta_y_valor(self):self.leer(self.caso('espacios'))
    def test_asignacion_con_valor_largo_y_prefijo_partido(self):self.leer(self.caso('campo'),True)
    def test_cabecera_larga_sigue_protegida(self):self.leer(self.caso('cabecera'),True)
    def test_autoridad_url_con_valor_largo(self):self.leer(self.caso('url'),True)
    def test_token_con_prefijo_partido(self):self.leer(self.caso('token'),True)
    def test_env_con_nombre_largo_y_valor_en_otro_bloque(self):self.leer(self.caso('env',pos=16122),True)
    def test_marcador_privado_incrustado_y_partido(self):self.leer(self.caso('pem_inline'),True)
    def test_utf16_conserva_publico_sin_exponer_el_valor(self):self.leer(self.caso('espacios','utf-16'))

    def test_filtro_rapido_conserva_todas_las_familias_de_prefijos(self):
        ejemplos=['PASSWORD','passwd','contraseña','api-key','access_token','auth_token','secret_key','private_key','Authorization','Cookie']
        for nombre in ejemplos:
            with self.subTest(etiqueta=nombre):self.assertIsNotNone(L._inicio_sensible_pendiente(nombre+' =',' '*300))
        ejemplos=['Bearer '+('X'*30),'sk-'+('X'*30),'AIza'+('X'*30),'AKIA'+('X'*16),'hf_'+('X'*30),'xoxb-'+('X'*30),'ghp_'+('X'*30),'github_pat_'+('X'*30),'eyJ'+('X'*30),'https://usuario:valor']
        for valor in ejemplos:
            # No imprimir ni parametrizar valores con forma de credencial.
            self.assertIsNotNone(L._inicio_sensible_pendiente(valor,'X'*256))

    def test_omision_conservadora_se_declara_parcial(self):
        item=self.leer(self.caso('espacios'));self.assertTrue(item.get('cortado'));self.assertIn('sensible',item.get('aviso','').casefold())

    def test_texto_largo_publico_sigue_completo(self):
        original='dato publico '*15000+'\nFIN_PUBLICO\n';item={'nombre':'fuente.txt'}
        texto=''.join(t for _,t in L.bloques_texto(io.BytesIO(original.encode()),item,300000))
        self.assertEqual(texto,original);self.assertFalse(item.get('cortado'))

    def test_url_publica_con_puerto_y_ruta_no_se_convierte_en_credencial(self):
        original='dato publico '*1400+'https://example.invalid:443/ruta '+('dato '*5000)+'\n';item={'nombre':'fuente.txt'}
        texto=''.join(t for _,t in L.bloques_texto(io.BytesIO(original.encode()),item,300000))
        self.assertEqual(texto,original);self.assertFalse(item.get('cortado'))

    def test_worker_e_indice_no_reciben_fragmentos_privados(self):
        with tempfile.TemporaryDirectory(dir=T.L.RAIZ) as tmp:
            base=Path(tmp);raw,privados=B.preparar(self.caso('espacios','utf-16'));p=base/'fuente.txt';p.write_bytes(raw)
            with patch.object(T,'RAIZ',base/'indice'):
                d=T.indexar(T.crear([p])['id'],False);r=T.buscar(d['id'],B.PUBLICO,presupuesto=5000)
                self.assertTrue(any(B.PUBLICO in x['texto'] for x in r['trozos']));self.assertEqual(d['archivos'][0]['estado'],'parcial')
                with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:
                    textos=''.join(x[0] for x in db.execute('SELECT texto FROM trozos'))+' '.join(x[0] for x in db.execute('SELECT meta FROM fuentes'))
                self.assertFalse(any(v[i:i+8] in textos for v in privados for i in range(len(v)-7)))
            self.assertEqual(p.read_bytes(),raw)

    def test_indice_de_lector_anterior_no_expone_una_copia_insegura(self):
        with tempfile.TemporaryDirectory(dir=T.L.RAIZ) as tmp:
            base=Path(tmp);p=base/'fuente.txt';p.write_text('DATO_PUBLICO anterior.')
            with patch.object(T,'RAIZ',base/'indice'):
                with patch.object(T,'LECTOR_VERSION',9):d=T.indexar(T.crear([p])['id'],False)
                with closing(sqlite3.connect(T.RAIZ/'trozos.sqlite')) as db:db.execute('UPDATE trozos SET texto=?',('VALOR_FICTICIO_ANTIGUO_73',));db.commit()
                r=T.buscar(d['id'],'VALOR_FICTICIO_ANTIGUO_73');self.assertEqual(r['trozos'],[]);self.assertIn('/indexar',r['aviso'])


if __name__=='__main__':unittest.main()
