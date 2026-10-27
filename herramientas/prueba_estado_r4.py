import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import estado_ia_r4_texto as R
import estado_ia as E
class Pruebas(unittest.TestCase):
    def test_android_solo_acredita_compilacion_con_recibo_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=p/'ronda4_continuacion_20261021';r.mkdir()
            (r/'android_verificacion.json').write_text(json.dumps({'verificado':True,'junit_pruebas':2,'junit_fallos':0,'sha256_apk':'a'*64,'room_generado':True,'texto':'NO_COPIAR'}))
            t=R.android_resumen(p/'ronda4_20261021')
            self.assertIn('compilado',t);self.assertIn('No se probó en dispositivo',t);self.assertNotIn('NO_COPIAR',t)
    def test_android_no_se_acredita_con_datos_falsos_o_incompletos(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=p/'ronda4_continuacion_20261021';r.mkdir()
            for d in ({'verificado':True},{'verificado':True,'junit_pruebas':2,'junit_fallos':1,'sha256_apk':'a'*64,'room_generado':True}):
                (r/'android_verificacion.json').write_text(json.dumps(d))
                self.assertIn('sin compilación comprobada',R.android_resumen(p/'ronda4_20261021'))
    def test_continuacion_usa_solo_cifras_validadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=p/'ronda4_continuacion_20261021';r.mkdir()
            f=r/'resumen_continuacion.json'
            f.write_text(json.dumps({'rondas':{'sesenta_coherencia':{'total':60,'conteos_codex':{'bien':43,'parcial':10,'mal':7},'texto':'NO_COPIAR'}}}))
            t=R.cifras_continuacion(p/'ronda4_20261021')
            self.assertIn('43/10/7',t);self.assertNotIn('NO_COPIAR',t)
    def test_continuacion_rechaza_cifras_falsas_y_texto(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=p/'ronda4_continuacion_20261021';r.mkdir()
            f=r/'resumen_continuacion.json'
            for c in ({'bien':60,'parcial':10,'mal':7},{'bien':'NO_COPIAR','parcial':0,'mal':0}):
                f.write_text(json.dumps({'rondas':{'sesenta_coherencia':{'total':60,'conteos_codex':c}}}))
                self.assertEqual(R.cifras_continuacion(p/'ronda4_20261021'),'')
    def test_informe_de_mediciones_no_inyecta_textos_privados(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);f=p/'resumen_mediciones.json'
            f.write_text(json.dumps({'rondas':{'sesenta_corregida':{'total':60,'conteos_codex':{'bien':49,'parcial':5,'mal':6},'texto':'NO_COPIAR_TEXTO'}}}))
            t=R.cifras(p);self.assertIn('49 bien/5 parcial/6 mal',t);self.assertNotIn('NO_COPIAR',t)
            f.write_text(json.dumps({'rondas':{'sesenta_corregida':{'total':60,'conteos_codex':{'bien':'NO_COPIAR_TEXTO'}}}}))
            self.assertIn('sin resumen válido',R.cifras(p));self.assertNotIn('NO_COPIAR',R.cifras(p))
    def test_bateria_con_etapa_compuesta_y_focal_ignorado(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);r=p/'reportes';r.mkdir()
            for nombre,total,fecha in [('pruebas_etapa_CH_1.txt',2250,1),('pruebas_etapa_DF_1.txt',2269,2),('pruebas_focal_inventado.txt',90000,3)]:
                f=r/nombre;f.write_text(f'Total: {total} pruebas. Archivos con fallos: 0.');os.utime(f,(fecha,fecha))
            with patch.object(E,'REGISTROS',p):d=E._ultima_bateria()
            self.assertEqual(d[2],2269)
    def test_lectura_personal_de_otro_comando_pausa_confirmacion_anterior(self):
        import administracion_local as A,metricas_modelos as M
        e={'_confirmacion_vocabulario':{'forma':'ejemplo'},'_revision_respuestas':{'pos':0}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(M,'ARCHIVO',Path(tmp)/'metricas'):
            A.comando('/modelo estadisticas',e,lambda _:self.fail('Solo lectura'))
        self.assertNotIn('_confirmacion_vocabulario',e);self.assertNotIn('_revision_respuestas',e)
if __name__=='__main__':unittest.main()
