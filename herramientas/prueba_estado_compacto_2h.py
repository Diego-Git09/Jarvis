"""Estado para IA con política vigente y evidencia completa, sin transcripciones."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import estado_ia as E
import estado_ia_texto as T
import configuracion_jarvis as C


class Pruebas(unittest.TestCase):
    def test_lee_configuracion_real_al_generar_y_no_supone_modelo(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);a=dict(C.DEFAULT,modelo=C.MODELO_COTIDIANO,keep_alive='1m',timeout_auto=False,timeout_modelo=45)
            with patch.object(E,'TRABAJO',p),patch.object(E,'RESUMEN',p/'estado.md'),patch.object(E,'REGISTROS',p/'registros'),patch.object(E,'leer_config',return_value=(a,'')):
                texto=E.generar()
            self.assertIn('Modelo activo: qwen3:8b',texto);self.assertIn('espera manual (base 45s), reposo 1m',texto)
            self.assertIn('todas las consultas a IA externas bloqueadas',texto);self.assertNotIn('IA externa configurada',texto)
            self.assertLessEqual(len(texto),6200);self.assertLessEqual(len(texto.split()),2000)
            self.assertEqual((p/'estado.md').read_text(),texto)

    def test_bateria_etapa_completa_prevalece_sobre_focal_y_archivo_incompleto(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz=Path(tmp);reportes=raiz/'reportes';reportes.mkdir()
            for n,contenido,fecha in [('pruebas_etapa_E_1.txt','Total: 1999 pruebas. Archivos con fallos: 0.',1),
                                      ('pruebas_adjuntos_focal.txt','Total: 10000 pruebas. Archivos con fallos: 0.',2),
                                      ('pruebas_etapa_F_1.txt','Todavía ejecutando',3)]:
                p=reportes/n;p.write_text(contenido);os.utime(p,(fecha,fecha))
            with patch.object(E,'REGISTROS',raiz):r=E._ultima_bateria()
            self.assertEqual(r[2],1999);self.assertEqual(r[1].name,'pruebas_etapa_E_1.txt')

    def test_metricas_distinguen_real_y_muestreo_sin_copiar_preguntas(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'C_ollama_real.json').write_text(json.dumps({'casos':[{'ok':True,'pregunta':'NO_COPIAR_TEXTO'},{'ok':False}]}))
            (p/'D_recursos_reales.json').write_text(json.dumps({'casos':[{'pico_usada_mib':6153}],'reposo_1m':{'descargado':True}}))
            texto=T.metricas(p)
            self.assertIn('1/2 turnos',texto);self.assertIn('muestreado 6153',texto)
            self.assertIn('No es tope global',texto);self.assertNotIn('NO_COPIAR_TEXTO',texto)

    def test_no_lee_informe_enlazado(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);fuera=p/'fuera.json';fuera.write_text(json.dumps({'casos':[{'ok':True}]}))
            (p/'C_ollama_real.json').symlink_to(fuera)
            self.assertIn('Sin mediciones',T.metricas(p))

    def test_conserva_fallos_de_calidad_cpu_sin_copiar_respuestas(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for sufijo in ('','_2','_3'):
                (p/('streaming_CPU_real_20261020'+sufijo+'.json')).write_text(json.dumps({'ok':False,'respuesta':'NO_COPIAR_RESPUESTA'}))
            texto=T.metricas(p)
            self.assertIn('0/3 etiquetas exactas',texto);self.assertIn('calidad pendiente',texto)
            self.assertNotIn('NO_COPIAR_RESPUESTA',texto)

    def test_configuracion_ilegible_se_declara_sin_afirmar_persistencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            with patch.object(E,'TRABAJO',p),patch.object(E,'RESUMEN',p/'estado.md'),patch.object(E,'REGISTROS',p/'registros'),patch.object(E,'leer_config',return_value=(dict(C.DEFAULT),'ilegible')):
                texto=E.generar()
            self.assertIn('Configuración guardada ilegible',texto);self.assertNotIn('Modelo activo:',texto)


    def test_metricas_nuevas_no_copian_textos_o_conteos_inventados(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);archivo=p/'resumen_mediciones.json'
            archivo.write_text(json.dumps({'seleccion_final':{'utiles':31,'parciales':2,'fallos':7},'respuesta':'NO_COPIAR_TEXTO_PRIVADO'}))
            texto=T.metricas_ronda(p);self.assertIn('31/40',texto);self.assertNotIn('NO_COPIAR',texto)
            archivo.write_text(json.dumps({'seleccion_final':{'utiles':'NO_COPIAR_TEXTO_PRIVADO','parciales':2,'fallos':7}}))
            self.assertNotIn('NO_COPIAR',T.metricas_ronda(p));self.assertIn('sin resumen final',T.metricas_ronda(p))

if __name__=='__main__':unittest.main()
