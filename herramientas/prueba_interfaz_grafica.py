"""Pruebas de distribución adaptable y activación de la ventana gráfica."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from interfaz_grafica import Aplicacion, InstanciaUnica, calcular_geometria_memoria, etiqueta_registro, filtrar_registros
from estructura_jarvis import obtener_registro_completo,nombre_legible,texto_visible


class ClienteRegistroCompleto:
    def __init__(self, registro): self.registro=registro; self.llamadas=[]
    def llamar(self,nombre,parametros):
        self.llamadas.append((nombre,parametros))
        return {'memorias':[self.registro]}


class PruebasInterfazGrafica(unittest.TestCase):
    def test_ventana_emergente_se_ajusta_a_pantalla_completa(self):
        self.assertEqual(calcular_geometria_memoria(1_920, 1_080), (820, 840))

    def test_ventana_emergente_cabe_en_pantallas_pequenas(self):
        self.assertEqual(calcular_geometria_memoria(1_146, 780), (820, 680))
        self.assertEqual(calcular_geometria_memoria(700, 500), (620, 480))

    def test_filtro_por_proyecto_y_busqueda_no_depende_de_tildes(self):
        grupos=[
            {'proyecto':'sin_clasificar','registros':[{'titulo':'Configuración','contenido':'Qwen local'}]},
            {'proyecto':'Jarvis','registros':[{'titulo':'Interfaz','contenido':'Ventana OLED'}]},
        ]
        filas,total=filtrar_registros(grupos,'sin_clasificar','configuracion qwen')
        self.assertEqual((len(filas),total),(1,1))
        filas,total=filtrar_registros(grupos,'Todos los proyectos','ventana oled')
        self.assertEqual((filas[0]['titulo'],total),('Interfaz',2))

    def test_nombre_sin_clasificar_se_muestra_en_lenguaje_amigable(self):
        self.assertEqual(Aplicacion._etiqueta_proyecto('sin_clasificar'),'Sin clasificar')

    def test_titulo_de_conversacion_muestra_pregunta_en_formato_tu(self):
        fila={'tipo':'conversacion','titulo':'Conversación Jarvis · 12-10-2026 20:01',
              'contenido':'Tú> Hola Jarvis, ¿qué recuerdas?\n\nJarvis:\nUna nota.'}
        etiqueta=etiqueta_registro(fila)
        self.assertIn('Conversación Jarvis',etiqueta)
        self.assertIn('Hola Jarvis, ¿qué recuerdas?',etiqueta)

    def test_titulo_de_recuerdo_identifica_el_tipo(self):
        self.assertEqual(etiqueta_registro({'tipo':'recuerdo','titulo':'Preferencias'}),'Recuerdo · Preferencias')

    def test_al_abrir_registro_usa_lectura_completa_por_id(self):
        largo='transcripción completa '*300
        cliente=ClienteRegistroCompleto({'id':17,'contenido':largo})
        registro=obtener_registro_completo(cliente,17)
        self.assertEqual(registro['contenido'],largo)
        self.assertEqual(cliente.llamadas,[('consultar_memoria',{'id_memoria':17})])

    def test_titulo_no_repite_fecha_y_lector_conserva_palabras(self):
        original='Intercambio local de Jarvis.\n\nUsuario:\nHola, ¿cómo estás?\n\nRespuesta final de Jarvis:\nBien, gracias.\n\nEstado: respuesta completa.\n\nOrigen automático: jarvis; intercambio local guardado al cerrar la respuesta.'
        fila={'tipo':'conversacion','fuente':'Jarvis','titulo':'Conversación Jarvis · 12-10-2026 20:00:00','contenido':original}
        self.assertEqual(nombre_legible(fila),'Conversación Jarvis — Hola, ¿cómo estás?')
        self.assertEqual(texto_visible(fila),'Tú:\nHola, ¿cómo estás?\n\nJarvis:\nBien, gracias.')
        self.assertEqual(fila['contenido'],original)

    def test_segunda_apertura_activa_la_instancia_existente(self):
        with tempfile.TemporaryDirectory(prefix='jarvis-ui-test-') as runtime:
            os.chmod(runtime, 0o700)
            anterior = os.environ.get('XDG_RUNTIME_DIR')
            os.environ['XDG_RUNTIME_DIR'] = runtime
            activada = threading.Event()
            primera = InstanciaUnica(activada.set)
            try:
                segunda = InstanciaUnica(lambda: None)
                self.assertTrue(segunda.es_secundaria)
                self.assertTrue(activada.wait(1))
            finally:
                primera.cerrar()
                if anterior is None:
                    os.environ.pop('XDG_RUNTIME_DIR', None)
                else:
                    os.environ['XDG_RUNTIME_DIR'] = anterior


if __name__ == '__main__':
    unittest.main()
