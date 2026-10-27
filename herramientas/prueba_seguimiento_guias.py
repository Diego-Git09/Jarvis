"""El caso explicado se conserva para guías; no autoriza escrituras ni nube."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import jarvis_agente as J
import seguimiento_conversacion as S
import referencia_documental as R
import adjuntos_jarvis as A

CASO=('El caso de Tienda Ejemplo consiste en una aplicación Android para registrar entradas por cuatro accesos y distinguir compradores de tránsito. '
      'Los requisitos son guardar acceso y fecha. Propongo Kotlin y una API; estas tecnologías deben contrastarse con el documento original. ')*8
VARIANTES=['haceme una guia de como hacerlo','hazme una guía de cómo hacerlo','hace una guia paso a paso','armame un instructivo',
 'me lo explicas paso a paso','ahora dame los pasos','dame un tutorial','por donde empiezo','cómo empiezo','que hago primero',
 'ayudame con esto','explicame esto','me explicas eso','pasamelo a una guia para implementarlo','guía completa de ese caso',
 'quiero una guia detallada','necesito un paso a paso','preparame una guia completa','mas detallado','sigamos']

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.h=[{'role':'system','content':'reglas'},{'role':'user','content':'Explica el caso adjunto'},{'role':'assistant','content':CASO}]
        self.addCleanup(lambda:setattr(J.TIEMPO_MODELO,'seguimiento',None))
        self.addCleanup(lambda:setattr(J.TIEMPO_MODELO,'documento',None))
        self.addCleanup(lambda:setattr(J.TIEMPO_MODELO,'codigo',None))
    def test_variantes_no_pierden_antecedente(self):
        for frase in VARIANTES:
            with self.subTest(frase=frase):
                t=S.contexto(self.h+[{'role':'user','content':frase}],frase)
                self.assertIn('Tienda Ejemplo',t);self.assertLessEqual(len(t),1800)
    def test_tema_nuevo_y_negacion_no_arrastran_caso(self):
        for frase in ['hazme una guía para cocinar arroz','otro tema: dame una guía de Ubuntu','olvida eso, quiero otra guía',
                      'no uses el documento; explica esto','hola','clima Santiago','revisa esto\n[Adjunto: Nuevo.pdf]']:
            self.assertEqual(S.contexto(self.h,frase),'')
    def test_sin_antecedente_no_se_inventa(self):
        self.assertEqual(S.contexto([{'role':'user','content':'haceme una guia'}],'haceme una guia'),'')
    def test_antecedente_es_ultima_explicacion_no_una_antigua(self):
        h=self.h+[{'role':'user','content':'Ahora explica cocinar arroz'},{'role':'assistant','content':'Para cocinar arroz necesitas agua y una olla. Lava el arroz, hierve el agua y cocina a fuego bajo hasta que esté listo.'}]
        self.assertIn('cocinar arroz',S.contexto(h,'hazme una guía'));self.assertNotIn('Tienda Ejemplo',S.contexto(h,'hazme una guía'))
    def test_guia_no_ofrece_escrituras_aunque_haya_proyecto_activo(self):
        J.TIEMPO_MODELO.codigo='proyecto activo'
        h=self.h+[{'role':'user','content':'Haceme una guía de cómo hacerlo en Android Studio'}]
        nombres={x['function']['name'] for x in J.herramientas_para_turno(h)}
        self.assertIn('leer_documento',nombres);self.assertNotIn('escribir_archivo_codigo',nombres);self.assertNotIn('crear_archivo',nombres)
    def test_guia_a_archivo_se_distingue_de_explicacion(self):
        self.assertFalse(S.es_guia('Guarda una guía en archivo pasos.md'));self.assertTrue(S.es_guia('haceme una guia de como hacerlo'))
        self.assertFalse(S.es_guia('Corrige logica.py según la guía anterior'));self.assertFalse(S.es_guia('Hazme una función Python siguiendo el tutorial'))
        self.assertFalse(S.es_guia('Hazme una guía y luego compila el proyecto'));self.assertTrue(S.es_guia('Hazme una guía de cómo compilar'))
        self.assertFalse(S.es_guia('No quiero una guía, crea un recordatorio'))
        self.assertFalse(S.es_guia('Crea un recordatorio y dame una guía de cómo editarlo'))
        self.assertFalse(S.es_guia('Calcula 15% de 200 paso a paso'))
    def test_modelo_recibe_antecedente_acotado_sin_alterar_historial(self):
        h=self.h+[{'role':'user','content':'haceme una guia de como hacerlo'}];antes=copy.deepcopy(h)
        J.TIEMPO_MODELO.seguimiento=S.contexto(h,h[-1]['content'])
        with patch.object(J.O,'solicitar',return_value={'message':{'role':'assistant','content':json.dumps({'accion':'respuesta','argumentos':{},'respuesta':'Guía del caso'})}}) as envio:
            J.enviar_a_ollama(h)
        payload=envio.call_args.args[1];self.assertIn('Tienda Ejemplo',payload['messages'][-1]['content'])
        self.assertIn('puede incluir propuestas o errores',payload['messages'][-1]['content']);self.assertEqual(h,antes)
        self.assertLess(len(json.dumps(payload['messages'])),14000)
    def test_seguimiento_no_se_filtra_a_otro_turno_o_ia(self):
        h=self.h+[{'role':'user','content':'haceme una guia de como hacerlo'}];estado={}
        with patch.object(J,'_ejecutar_turno',side_effect=ConnectionError('falló')),patch.object(J.IA.P,'opciones',return_value={'configurado':True,'automatico':True,'preferido':'Gemini','timeout_local':35}),patch.object(J.IA,'preguntar_externa') as nube:
            r=J.responder_con_respaldo(h,None,lambda _:False,estado,mostrar=lambda _:None)
        nube.assert_not_called();self.assertIn('No envié',r);self.assertIsNone(J.TIEMPO_MODELO.seguimiento)
    def test_documento_responde_a_guia_y_explicame(self):
        estado={'_documento_tramo':{'ruta':'caso.pdf'}}
        self.assertTrue(R.pertinente('haceme una guia de como hacerlo',estado));self.assertTrue(R.pertinente('explicame esto',estado))
        self.assertFalse(R.pertinente('hazme una guía para cocinar arroz',estado))
    def test_adjunto_recuerda_ruta_y_multiples_no_eligen_por_inferencia(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'caso.pdf';f.write_text('documento simulado');g=Path(t)/'otro.pdf';g.write_text('otro')
            with patch('herramientas_lectura._resolver',side_effect=lambda p:Path(p)):
                estado={};A.recordar_referencia([{'ruta':str(f)}],estado);self.assertEqual(estado['_documento_tramo']['ruta'],str(f))
                A.recordar_referencia([{'ruta':str(f),'cortado':True,'texto':'recortado'}],estado);self.assertIsNotNone(estado['_documento_tramo']['siguiente'])
                A.recordar_referencia([{'ruta':str(f)},{'ruta':str(g)}],estado);self.assertNotIn('_documento_tramo',estado)
    def test_guia_no_activa_generador_de_archivos(self):
        with patch.object(J.CODIGO,'activo',return_value={'id':'p'}),patch.object(J.CODIGO,'estado',side_effect=AssertionError('No debe generar')):
            self.assertIsNone(J.CODIGO.desarrollar('Haceme una guía del código Python',{},lambda _:False,None,'modelo'))
    def test_interrupcion_al_preparar_no_deja_antecedente_en_otro_turno(self):
        h=self.h+[{'role':'user','content':'haceme una guia de como hacerlo'}]
        with patch.object(R,'preparar',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):J.ejecutar_turno(h,None,lambda _:False,{})
        self.assertIsNone(J.TIEMPO_MODELO.seguimiento);self.assertIsNone(J.TIEMPO_MODELO.documento)

if __name__=='__main__':unittest.main()
