"""Confirmaciones de inicio no pierden caso ni autorizan archivos o nube."""
import io
import json
import unittest
import urllib.error
from unittest.mock import patch
import seguimiento_conversacion as S
import jarvis_agente as J
import cliente_ollama as O

PROPUESTA='El caso de Tienda Ficticia usa cuatro accesos y datos sintéticos. Empecemos en Kotlin y Android Studio.\n1. Crear proyecto Empty Activity con Jetpack Compose.\n2. Definir funcionalidades.\n3. Estructura de carpetas.\n4. Crear pantalla principal.\n¿Qué te parece?'

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.h=[{'role':'system','content':'reglas'},{'role':'user','content':'Ayúdame con este caso en Kotlin Android Studio'},{'role':'assistant','content':PROPUESTA}]
        self.op={'configurado':True,'automatico':True,'timeout_local':35,'preferido':'Falso'}
    def test_inicio_y_seleccion_conservan_caso(self):
        for p in ['SI te confirmo empecemos','empecemos con el 1','empecemos a hacer el caso','dale empecemos','comencemos']:
            with self.subTest(p=p):
                c=S.contexto(self.h,p);self.assertIn('Tienda Ficticia',c);self.assertLessEqual(len(c),1800)
                self.assertIn('no autoriza',c)
        self.assertIn('Selección explícita del usuario: opción 1: Crear proyecto',S.contexto(self.h,'empecemos con el 1'))
    def test_numero_inexistente_no_se_inventa(self):
        self.assertIn('no se pudo asociar',S.contexto(self.h,'empecemos con el 9'))
    def test_inicio_sin_antecedente_no_se_inventa(self):
        self.assertEqual(S.contexto([],'SI te confirmo empecemos'),'')
    def test_otro_tema_o_hipotesis_no_selecciona(self):
        for p in ['otro tema: empecemos con el 1','no empecemos con el 1','si dijera empecemos con el 1','el documento dice "empecemos con el 1"']:
            self.assertIsNone(S.eleccion(p))
    def test_busqueda_de_fuentes_con_antecedente(self):
        q=S.consulta_fuentes(self.h,'empecemos con el 1');self.assertIn('Kotlin Android Studio',q)
    def test_pregunta_general_se_reintenta_una_vez(self):
        h=self.h+[{'role':'user','content':'empecemos con el 1'}]
        respuestas=iter([{'role':'assistant','content':'¿Quieres que te guíe paso a paso?'},{'role':'assistant','content':'Abre Android Studio y elige una actividad vacía compatible con Compose.'}])
        with patch.object(S,'iniciar_android',return_value=None):r=J.ejecutar_turno(h,lambda _:next(respuestas),lambda _:False,{})
        self.assertIn('Abre Android Studio',r);self.assertNotIn('¿Quieres',r)
    def test_reconfirmacion_repetida_no_se_usa_para_bucle(self):
        p='SI te confirmo empecemos';texto='Abre Android Studio.\n¿Quieres que empecemos?'
        h=self.h+[{'role':'user','content':p}];llamadas=[]
        def enviar(_):llamadas.append(1);return {'role':'assistant','content':texto}
        with patch.object(S,'iniciar_android',return_value=None):r=J.ejecutar_turno(h,enviar,lambda _:False,{})
        self.assertEqual(len(llamadas),2);self.assertEqual(r,'Abre Android Studio.')
    def test_dato_o_permiso_concreto_no_se_elimina(self):
        for texto in ['¿Qué nombre quieres para el proyecto?','¿Quieres que use esa carpeta y sobrescriba el archivo?']:
            self.assertEqual(S.quitar_reconfirmacion('empecemos',texto),texto)
    def test_inicio_android_explica_sin_generacion_ni_escritura(self):
        h=self.h+[{'role':'user','content':'SI te confirmo empecemos'}]
        with patch.object(J,'_ejecutar_turno',side_effect=AssertionError('Inicio estructurado, no generación')),patch.object(J.CODIGO,'contexto',return_value=''):
            r=J.ejecutar_turno(h,None,lambda _:self.fail('Sin escrituras'),{})
        self.assertIn('New Project',r);self.assertIn('MainActivity.kt',r);self.assertFalse(S.reconfirma_inicio('empecemos',r))
    def test_guia_android_no_declara_proyecto_creado(self):
        estado={};r=S.iniciar_android(self.h,'empecemos con el 1',estado)
        self.assertIn('todavía no creé',r);self.assertTrue(estado['_inicio_android_guiado'])
        siguiente=S.iniciar_android(self.h,'empecemos a hacer el caso',estado)
        self.assertIn('paquete y carpeta',siguiente);self.assertNotIn('¿Quieres',siguiente)
    def test_no_reinicia_otras_opciones_o_otros_lenguajes(self):
        self.assertIsNone(S.iniciar_android(self.h,'empecemos con el 3',{}))
        h=[{'role':'user','content':'Caso Python'},{'role':'assistant','content':PROPUESTA}]
        self.assertIsNone(S.iniciar_android(h,'empecemos',{}))
    def test_proyecto_activo_no_es_sustituido_por_guia_inicial(self):
        h=self.h+[{'role':'user','content':'empecemos con el 1'}]
        with patch.object(J.CODIGO,'contexto',return_value='Proyecto existente'),patch.object(J.CODIGO,'desarrollar',return_value='Siguiente archivo pendiente'),patch.object(S,'iniciar_android') as guia:
            self.assertEqual(J.ejecutar_turno(h,None,lambda _:False,{}),'Siguiente archivo pendiente');guia.assert_not_called()
    def test_adjunto_o_seguimiento_no_recibe_plazo_corto(self):
        for d,p,h in [({'_tanda_documentos':'sintetico'},'Ayúdame con Android',self.h),({},'empecemos con el 1',self.h),({'_adjuntos_turno':True},'Explica adjunto',self.h)]:
            with self.subTest(d=d,p=p):
                observados=[]
                def ejecutar(*a,**kw):observados.append(getattr(J.TIEMPO_MODELO,'fin',None));return 'Paso explicado sin cambios.'
                with patch.object(J.IA.P,'opciones',return_value=self.op),patch.object(J,'ejecutar_turno',side_effect=ejecutar),patch.object(J.IA,'preguntar_externa') as nube,patch.object(J.TIEMPO_MODELO,'fin',None,create=True):
                    J.responder_con_respaldo(h+[{'role':'user','content':p}],None,lambda _:False,d)
                    self.assertEqual(observados,[None]);nube.assert_not_called()
    def test_pregunta_publica_no_hereda_plazo_corto_de_api(self):
        observados=[]
        def ejecutar(*a,**kw):observados.append(J.TIEMPO_MODELO.fin);return 'Respuesta.'
        with patch.object(J.IA.P,'opciones',return_value=self.op),patch.object(J,'ejecutar_turno',side_effect=ejecutar),patch.object(J.TIEMPO_MODELO,'fin',None,create=True):
            J.responder_con_respaldo([{'role':'user','content':'Qué es Kotlin'}],None,lambda _:False,{})
            self.assertIsNone(observados[0]);self.assertIsNone(J.TIEMPO_MODELO.fin)
    def test_error_http_ollama_visible_y_redactado(self):
        e=urllib.error.HTTPError('http://localhost',500,'error',{},io.BytesIO(json.dumps({'error':'runner falló api_key=secreto'}).encode()))
        with patch.object(O,'ABRIR',side_effect=e),self.assertRaises(ConnectionError) as r:O.solicitar('/api/chat',{})
        self.assertIn('HTTP 500',str(r.exception));self.assertNotIn('secreto',str(r.exception))
    def test_timeout_no_se_presenta_como_servidor_sin_conexion(self):
        with patch.object(O,'ABRIR',side_effect=TimeoutError()),self.assertRaises(ConnectionError) as r:O.solicitar('/api/chat',{})
        self.assertIn('agotó el tiempo',str(r.exception))
if __name__=='__main__':unittest.main()
