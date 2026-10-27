"""Interpretación de lenguaje natural sin ejecutar modificaciones reales."""
import unittest
from lenguaje_jarvis import interpretar, seleccion, resumen_vocabulario
from interfaz_jarvis import comando


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.state={'_lista_memorias':{1:101,2:102,3:103,4:104,5:105}}

    def test_sinonimos_movimiento(self):
        for frase in ['pasa las memorias uno y dos a Jarvis', 'pon el primero y el segundo en Jarvis',
                      'ubica 1,2 en el proyecto Jarvis', 'reubica los recuerdos 1 y 2 dentro del proyecto Jarvis',
                      'oye Jarvis, me puedes por favor asignar las memorias uno y dos al proyecto Jarvis',
                      'coloca el primero y el segundo en el proyecto Jarvis',
                      'agrega las memorias 1,2 al proyecto Jarvis porfa']:
            with self.subTest(frase=frase):
                i=interpretar(frase,self.state)
                self.assertEqual(i.nombre,'clasificar_recuerdos')
                self.assertEqual(i.argumentos,{'numeros':[1,2],'proyecto':'Jarvis'})

    def test_rangos_y_todos_se_limitan_a_pagina(self):
        for frase in ['pasa del uno al cinco a Jarvis', 'mueve recuerdos del 1 al 5 al proyecto Jarvis',
                      'asigna todos estos al proyecto Jarvis', 'mete todos los de esta página en Jarvis']:
            i=interpretar(frase,self.state)
            self.assertEqual(i.argumentos['numeros'],[1,2,3,4,5])
        self.assertIsNone(seleccion('del cinco al uno',self.state))

    def test_ordinales_en_segunda_pagina(self):
        state={'_lista_memorias':{6:106,7:107,8:108}}
        i=interpretar('pasa el primero y el segundo a Jarvis',state)
        self.assertEqual(i.argumentos['numeros'],[6,7])
        self.assertEqual(seleccion('seis y siete',state),[6,7])

    def test_pronombre_ambiguo_aclara(self):
        self.assertEqual(interpretar('ponlo en Jarvis',self.state).nombre,'aclarar')
        i=interpretar('ponlo en Jarvis',{'_lista_memorias':{8:108}})
        self.assertEqual(i.argumentos['numeros'],[8])
        self.assertEqual(interpretar('pásalos a Jarvis',self.state).argumentos['numeros'],[1,2,3,4,5])

    def test_listados_y_continuacion(self):
        for frase in ['enséñame los proyectos','dame mis proyectos','Jarvis, quiero ver los proyectos','qué proyectos tengo']:
            self.assertEqual(interpretar(frase,self.state).nombre,'/proyectos')
        for frase in ['qué tengo guardado','enséñame mis memorias','dame los recuerdos']:
            self.assertEqual(interpretar(frase,self.state).nombre,'/recuerdos')
        for frase in ['continúa','los siguientes','dame los siguientes','siguiente página']:
            self.assertEqual(interpretar(frase,self.state).nombre,'/mas')

    def test_filtro_y_orden(self):
        for frase in ['enséñame los pendientes de clasificar','dame las memorias sin proyecto','ver los no clasificados']:
            self.assertEqual(interpretar(frase,self.state).argumentos['proyecto'],'sin_clasificar')
        i=interpretar('recuerdos sin clasificar ordenados del mas antiguo al mas nuevo (por fecha)',self.state)
        self.assertEqual(i.argumentos,{'proyecto':'sin_clasificar','orden':'antiguos'})

    def test_nombre_original_y_proyectos_conocidos(self):
        i=interpretar('crea un proyecto llamado Ingeniería',self.state)
        self.assertEqual(i.argumentos['proyecto'],'Ingeniería')
        i=interpretar('enséñame el proyecto ingeniería',{'_proyectos_conocidos':['Ingeniería']})
        self.assertEqual(i.argumentos['proyecto'],'Ingeniería')
        i=interpretar('abre un proyecto que se llame Estudio de Inglés',self.state)
        self.assertEqual(i.argumentos['proyecto'],'Estudio de Inglés')

    def test_busquedas_con_consulta_intacta(self):
        for frase in ['localiza recuerdos sobre Qwen 3','encuentra las memorias que mencionan Qwen 3','búscame recuerdos relacionados con Qwen 3']:
            i=interpretar(frase,self.state)
            self.assertEqual(i.nombre,'buscar_memoria')
            self.assertEqual(i.argumentos['consulta'],'Qwen 3')

    def test_negaciones_e_hipotesis_no_ejecutan(self):
        for frase in ['no pases 1 a Jarvis', 'puedes no mover 1 a Jarvis', 'cómo puedo pasar 1 a Jarvis',
                      'si moviera 1 a Jarvis qué pasaría', 'No crees un proyecto llamado Prueba',
                      'lee el archivo proyecto Jarvis.txt']:
            self.assertIsNone(interpretar(frase,self.state))
        self.assertIsNone(interpretar('mueve 1 a Jarvis y luego borra otra memoria',self.state))

    def test_archivos_siguen_al_modelo_y_vocabulario_es_compartido(self):
        for frase in ['modifica prueba.txt','deshaz la última edición','olvida el recuerdo sobre Qwen']:
            self.assertIsNone(interpretar(frase,self.state))
        self.assertIn('editar_archivo',resumen_vocabulario())
        self.assertIn('ajusta',resumen_vocabulario())

    def test_condiciones_y_acciones_combinadas_no_son_nombres(self):
        for frase in ['crea un proyecto Jarvis si no existe','crea un proyecto Jarvis y luego mueve las memorias',
                      'busca recuerdos sobre Qwen y luego crea un proyecto']:
            self.assertIsNone(interpretar(frase,self.state))

    def test_estado_nuevo_y_salida(self):
        self.assertEqual(interpretar('¿Cómo está Segundo Cerebro?',self.state).nombre,'/estado')
        self.assertEqual(interpretar('Empecemos de nuevo',self.state).nombre,'/nuevo')
        self.assertEqual(interpretar('hasta luego',self.state).nombre,'/salir')

    def test_ultimo_recuerdo_se_consulta_y_luego_se_puede_mover(self):
        state={'_lista_memorias':{1:101},'_recuerdo_en_foco':1,'_tipo_ultimo_listado':'memorias'}
        for frase in ['¿Cuál fue el último recuerdo guardado y en qué proyecto quedó?',
                      'Muéstrame el último recuerdo que guardó Segundo Cerebro']:
            self.assertEqual(interpretar(frase,state).nombre,'consultar_ultimo_recuerdo')
        for frase in ['mueve el último recuerdo al proyecto Jarvis',
                      'mueve el recuerdo más nuevo al proyecto Jarvis',
                      'muévelo al proyecto Jarvis','muévela al proyecto Jarvis']:
            i=interpretar(frase,state)
            self.assertEqual(i.nombre,'clasificar_recuerdos',frase)
            self.assertEqual(i.argumentos,{'numeros':[1],'proyecto':'Jarvis'})

    def test_ultima_conversacion_filtra_por_ia_y_no_se_confunde_con_recuerdo(self):
        casos={
            'Muéstrame la última conversación de Claude': 'claude_desktop',
            '¿Qué fue lo último que conversé con Claude?': 'claude_desktop',
            'Muéstrame el último chat de Open WebUI': 'openwebui',
            '¿Qué fue lo último que hablé con Codex?': 'codex',
        }
        for frase,fuente in casos.items():
            i=interpretar(frase,self.state)
            self.assertEqual(i.nombre,'consultar_ultima_conversacion',frase)
            self.assertEqual(i.argumentos,{'fuente':fuente})

    def test_conversacion_seleccionada_requiere_referencia_explicita_para_mover(self):
        state={'_lista_memorias':{1:101},'_recuerdo_en_foco':1,'_tipo_ultimo_listado':'conversaciones'}
        self.assertEqual(interpretar('muévela al proyecto Jarvis',state).nombre,'aclarar')
        i=interpretar('mueve esa conversación al proyecto Jarvis',state)
        self.assertEqual(i.nombre,'clasificar_recuerdos')
        self.assertEqual(i.argumentos,{'numeros':[1],'proyecto':'Jarvis'})

    def test_pregunta_conversacional_llega_al_mcp_con_filtro_de_fuente(self):
        llamadas=[]
        handled,texto=comando('¿Qué fue lo último que conversé con Claude?',[],self.state,
            lambda n,a:llamadas.append((n,a)) or {'ok':True,'registro':{
                'titulo':'Conversación Claude Desktop · 12-10-2026 17:00','proyecto':'Jarvis',
                'creado':'12 de octubre de 2026, 18:00 (Chile)','tipo':'conversacion','fuente':'claude_desktop',
                'contenido':'Usuario: hola\nRespuesta final: hola'}} ,'s')
        self.assertTrue(handled)
        self.assertEqual(llamadas,[('consultar_ultima_conversacion',{'fuente':'claude_desktop'})])
        self.assertIn('IA de origen: claude_desktop',texto)
        self.assertIn('Proyecto: Jarvis',texto)
        self.assertIn('La conversación quedó seleccionada',texto)

    def test_integracion_intencion_usa_controlador(self):
        llamadas=[]
        handled,texto=comando('pasa las memorias uno y dos a Jarvis',[],self.state,
            lambda n,a:llamadas.append((n,a)) or {'ok':False,'error':'permiso rechazado'},'s')
        self.assertTrue(handled);self.assertEqual(texto,'permiso rechazado')
        self.assertEqual(llamadas,[('clasificar_recuerdos',{'numeros':[1,2],'proyecto':'Jarvis'})])


if __name__=='__main__':unittest.main()
