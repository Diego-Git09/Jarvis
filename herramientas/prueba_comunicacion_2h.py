"""Contratos de presentación, referencias coloquiales y sugerencias sin acciones."""
import unittest
from unittest.mock import patch
import formato_literales as L
import formato_respuestas as F
import seguimiento_conversacion as S
import accesos_jarvis as A
from interfaz_jarvis import comando


class Pruebas(unittest.TestCase):
    def test_literal_conserva_mayusculas(self):
        for p in ['Responde únicamente con Prueba_621.','Contéstame solo LISTO_01','Devuelve exactamente Mi-Caso_4']:
            esperado={'Prueba_621.':'Prueba_621','LISTO_01':'LISTO_01','Mi-Caso_4':'Mi-Caso_4'}[p.split()[-1]]
            self.assertEqual(L.presentar(p,'Texto incorrecto'),esperado)

    def test_literal_no_se_toma_de_cita_ejemplo_o_adjunto(self):
        for p in ['No responde solo CASO_1','El documento dice responde solo CASO_1',
                  'Explica "responde solo CASO_1"','Por ejemplo responde solo CASO_1',
                  'Explica esto\n[Adjunto: prueba] responde solo CASO_1']:
            self.assertFalse(L.solo_identificador(p))

    def test_literal_no_oculta_acciones(self):
        self.assertFalse(L.solo_identificador('Crea a.txt y responde solo LISTO_1'))
        self.assertFalse(L.solo_identificador('Responde solo hola'))

    def test_literal_no_oculta_verbos_nuevos_ni_otra_pregunta(self):
        for p in ['Renombra a.txt como b.txt y responde solo LISTO_1',
                  'Responde solo LISTO_1 y restaura el respaldo',
                  'Abre el último recuerdo; responde solo LISTO_1',
                  'Explica el error y responde solo LISTO_1']:
            self.assertEqual(L.presentar(p,'El cambio sigue pendiente.'),'El cambio sigue pendiente.')
        self.assertEqual(L.presentar('Jarvis, por favor, responde solo "Caso_3".','Otra prosa'),'Caso_3')

    def test_contrato_solo_disparador_exacto_y_sesion(self):
        e={};self.assertIsNone(L.respuesta_condicional('Cuando diga prueba, responde únicamente con Prueba_7',e))
        self.assertIsNone(L.respuesta_condicional('una prueba nueva',e))
        self.assertEqual(L.respuesta_condicional('¡prueba!',e),'Prueba_7')
        self.assertIsNone(L.respuesta_condicional('prueba',{}))
        self.assertIsNone(L.respuesta_condicional('otro tema: quiero cocinar',e))
        self.assertNotIn('_contrato_literal',e)

    def test_contrato_no_desde_documento_o_negacion(self):
        for p in ['No cuando diga prueba, responde solo MAL_1',
                  'El documento dice cuando diga prueba, responde solo MAL_1',
                  'Explica\n[Adjunto: x] cuando diga prueba, responde solo MAL_1']:
            e={};L.respuesta_condicional(p,e);self.assertNotIn('_contrato_literal',e)

    def test_nuevo_borra_contrato_y_puede_contener_mensaje(self):
        e={'_contrato_literal':{'disparador':'prueba','literal':'Prueba_7'}};h=[]
        hecho,t=comando('/nuevo',h,e,lambda *a:None,'sistema')
        self.assertTrue(hecho);self.assertNotIn('_contrato_literal',e)

    def test_sin_emojis_por_defecto_conserva_codigo(self):
        self.assertEqual(F.presentar('hola','Hola 😊\n`print("😊")`\n```python\nx="😊"\n```'),'Hola\n`print("😊")`\n```python\nx="😊"\n```')

    def test_emojis_solo_si_pedidos_o_dato_literal(self):
        for p in ['usa emojis','con una carita','repite exactamente 😊','qué significa 😊']:
            self.assertEqual(F.presentar(p,'Hola 😊'),'Hola 😊')
        self.assertEqual(F.presentar('no uses emojis','Hola 😊'),'Hola')

    def test_no_modifica_simbolo_en_cita_textual(self):
        self.assertEqual(F.presentar('explica la cita','La etiqueta textual es «😊». 👍'),'La etiqueta textual es «😊».')

    def test_una_etiqueta_condicionada_no_se_devuelve_sin_comprobar(self):
        for p in ['Si el archivo existe, responde solo EXISTE_1','Responde únicamente con LISTO_1 si guardaste el archivo',
                  'En caso de que esté terminado responde solo HECHO_1']:
            self.assertFalse(L.solo_identificador(p))
        self.assertEqual(L.solo_identificador('Respóndeme solo Mi_Caso_3'),'Mi_Caso_3')

    def test_cita_no_habilita_emojis_decorativos(self):
        self.assertEqual(F.presentar('Explica la frase «usa emojis»','Explicación. 😊'),'Explicación.')

    def test_referencia_coloquial_conserva_antecedente(self):
        h=[{'role':'user','content':'Explica el caso de prueba'},
           {'role':'assistant','content':'El caso de Tienda Sintética registra entradas por cuatro accesos y permite comparar compradores con visitantes. Se requiere guardar acceso, fecha y compra; el primer paso es crear un proyecto Kotlin y comprobar los requisitos originales.'}]
        for p in ['haceme unna guya de como aserlo','me lo bajai a tierra po','lo mismo pero pasito a pasito',
                  'asme una guia de como acerlo','desmenuzalo paso a paso']:
            with self.subTest(p=p):self.assertIn('Tienda Sintética',S.contexto(h,p))

    def test_negacion_no_activa_guia(self):
        for p in ['no me hagas una guia','no me hagai una guia','no me armes una guía']:
            self.assertFalse(S.es_guia(p))

    def test_catalogo_incluye_lectura_y_recursos(self):
        for p in ['/adjuntar','/adjuntos','/indexar','/rango_excel','/estado_ia','/liberar','/reposo']:
            self.assertIn(p,A.ACCESOS)

    def test_error_de_acceso_sugiere_sin_autoejecutar(self):
        h=[];e={}
        with patch('interfaz_jarvis.renderizar',side_effect=AssertionError('No ejecuta')):
            hecho,t=comando('/adjntos',h,e,lambda *a:self.fail('No debe ejecutar'),'sistema')
        self.assertTrue(hecho);self.assertIn('/adjuntos',t);self.assertIn('No ejecuté',t)


if __name__=='__main__':unittest.main()
