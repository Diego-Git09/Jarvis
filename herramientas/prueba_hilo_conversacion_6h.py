"""Hilos, referencias y resúmenes privados; fuentes sintéticas y sin red."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import contexto_jarvis as C
import hilo_conversacion as H
import seguimiento_conversacion as S
import sesiones_jarvis as SES


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.parche=patch.object(H,'CARPETA',self.base/'hilos');self.parche.start();self.addCleanup(self.parche.stop)
        self.estado={'_tanda_documentos':'a'*32};self.historial=[]

    def decir(self,pedido,respuesta):
        r=H.iniciar_turno(self.estado,pedido,self.historial)
        self.historial.extend([{'role':'user','content':r['pedido']},{'role':'assistant','content':respuesta}])
        H.terminar_turno(self.estado,pedido,respuesta)
        return r

    def propuesta(self):
        self.decir('Caso TIENDA_738 en Kotlin Android Studio; nombre "Lápiz Rosado" y presupuesto 271.',
                   'Propongo:\n1. Crear proyecto Kotlin.\n2. Diseñar pantalla.\n3. Probar datos.\n¿Empezamos?')

    def test_opciones_numeros_y_ordinales(self):
        for texto,numero in [('empecemos con el 1',1),('el segundo',2),('la última',3),('opción 2',2),('la tercera',3)]:
            with self.subTest(texto=texto):
                self.estado={};self.historial=[];self.propuesta()
                r=H.iniciar_turno(self.estado,texto)
                self.assertEqual(r['seleccion'],numero);self.assertTrue(r['aceptada']);self.assertIn('TIENDA_738',r['contexto'])

    def test_confirmar_explicacion_no_crea_permisos(self):
        self.propuesta()
        for frase in ['dale','ya po','sipo','obvio','hazlo','mándale','sí te confirmo','SI te confirmo empecemos']:
            r=H.iniciar_turno(self.estado,frase)
            self.assertTrue(r['aceptada']);H.terminar_turno(self.estado,frase,'Paso explicativo siguiente.')
        self.assertNotIn('permiso',self.estado)
        self.assertFalse(any(k in self.estado for k in ('id_propuesta','_memorias','_permisos')))

    def test_seleccion_inexistente_aclara(self):
        self.propuesta();r=H.iniciar_turno(self.estado,'empecemos con el 9')
        self.assertTrue(r['aclaracion']);self.assertFalse(r['aceptada']);self.assertNotIn('9:',r['contexto'])

    def test_sin_antecedente_no_inventa_propuesta(self):
        r=H.iniciar_turno({},'dale')
        self.assertFalse(r['aceptada']);self.assertTrue(r['aclaracion']);self.assertEqual(r['contexto'],'')

    def test_negaciones_hipotesis_y_citas_no_aceptan(self):
        self.propuesta()
        for frase in ['no hagas eso','si dijera "hazlo" no lo ejecutes','el documento dice "el segundo"','ejemplo: dale']:
            r=H.iniciar_turno(self.estado,frase);self.assertFalse(r['aceptada']);H.terminar_turno(self.estado,frase,'No ejecutado.')

    def test_cambio_tema_quita_documento_y_guia(self):
        self.propuesta();self.estado['_documento_tramo']={'ruta':'caso.pdf'};self.estado['_inicio_android_guiado']=True
        r=H.iniciar_turno(self.estado,'otro tema: ayúdame a cocinar arroz')
        self.assertEqual(r['contexto'],'');self.assertFalse(self.estado.get('_tanda_documentos'))
        self.assertNotIn('_documento_tramo',self.estado);self.assertNotIn('_inicio_android_guiado',self.estado)
        H.terminar_turno(self.estado,'otro tema: ayúdame a cocinar arroz','Lava el arroz y prepara una olla.')
        r=H.iniciar_turno(self.estado,'eso');self.assertIn('arroz',r['contexto']);self.assertNotIn('TIENDA_738',r['contexto'])

    def test_vuelve_a_tema_archivado(self):
        self.propuesta();self.decir('otro tema: cocina arroz','Hierve el agua.')
        r=H.iniciar_turno(self.estado,'vuelve al caso de la tienda')
        self.assertIn('TIENDA_738',r['contexto']);self.assertEqual(r['tanda'],'a'*32);self.assertIsNone(self.estado['_hilo_conversacion']['propuesta'])

    def test_no_uses_documento_es_explicitamente_sin_tanda(self):
        self.propuesta();r=H.iniciar_turno(self.estado,'no uses el documento; explícame álgebra')
        self.assertFalse(r['tanda']);self.assertEqual(r['contexto'],'')

    def test_dos_temas_similares_no_eligen_por_inferencia(self):
        self.decir('Caso tienda UNO_738','Tema uno.')
        self.decir('otro tema: caso tienda DOS_738','Tema dos.')
        self.decir('otro tema: recetas','Tema recetas.')
        r=H.iniciar_turno(self.estado,'vuelve al caso de la tienda')
        self.assertNotIn('UNO_738',r['contexto']);self.assertNotIn('DOS_738',r['contexto'])

    def test_reintentar_recupera_pedido_y_tanda_tras_reapertura(self):
        self.propuesta();p='Explica anexo 3 sin perder TIENDA_738'
        H.iniciar_turno(self.estado,p);H.terminar_turno(self.estado,p,'Ollama agotó la espera.',fallido=True)
        id_hilo=self.estado['_id_hilo'];self.estado={};H.recuperar(self.estado,id_hilo)
        r=H.iniciar_turno(self.estado,'reintenta');self.assertEqual(r['pedido'],p);self.assertTrue(r['reintento']);self.assertEqual(r['tanda'],'a'*32)

    def test_fallo_tras_accion_no_repite(self):
        self.propuesta();H.iniciar_turno(self.estado,'edita archivo.py')
        H.terminar_turno(self.estado,'edita archivo.py','Falló la respuesta.',fallido=True,hubo_acciones=True)
        r=H.iniciar_turno(self.estado,'sigue');self.assertFalse(r['reintento']);self.assertIn('/cambios',r['aclaracion'])

    def test_cierre_brusco_no_asume_que_no_hubo_accion(self):
        self.propuesta();H.iniciar_turno(self.estado,'continúa editando')
        H.marcar_accion(self.estado,'editar_archivo')
        ident=self.estado['_id_hilo'];e={};H.recuperar(e,ident)
        r=H.iniciar_turno(e,'reintenta');self.assertFalse(r['reintento']);self.assertTrue(r['aclaracion'])

    def test_inicio_idempotente_y_dos_turnos_identicos(self):
        self.propuesta();r=H.iniciar_turno(self.estado,'dale');dato=copy.deepcopy(self.estado['_hilo_conversacion'])
        self.assertEqual(H.iniciar_turno(self.estado,'dale'),r);self.assertEqual(dato,self.estado['_hilo_conversacion'])
        H.terminar_turno(self.estado,'dale','Siguiente paso.')
        H.iniciar_turno(self.estado,'dale');H.terminar_turno(self.estado,'dale','Otro paso.')
        self.assertEqual(self.estado['_hilo_conversacion']['turnos'],3)

    def test_archivo_estado_privado_y_redactado(self):
        self.decir('Nombre "Lápiz". Authorization: Bearer credencialsecreta','api_key=secreta respuesta')
        ruta=H.CARPETA/(self.estado['_id_hilo']+'.json')
        self.assertEqual(ruta.stat().st_mode&0o777,0o600);self.assertEqual(H.CARPETA.stat().st_mode&0o777,0o700)
        contenido=ruta.read_text();self.assertNotIn('credencialsecreta',contenido);self.assertNotIn('=secreta',contenido)

    def test_no_guardes_mensaje_no_persiste_en_turnos_posteriores(self):
        self.propuesta();r=H.iniciar_turno(self.estado,'no guardes este mensaje: MI_DATO_PRIVADO_910')
        H.terminar_turno(self.estado,r['pedido'],'Esta respuesta tiene DATO_PRIVADO_910.')
        self.decir('sigue','Siguiente paso explicativo.')
        textos=''.join(p.read_text() for p in H.CARPETA.glob('*.json'))
        self.assertNotIn('MI_DATO_PRIVADO_910',textos);self.assertNotIn('DATO_PRIVADO_910',textos)

    def test_archivo_corrupto_no_inventa_hilo(self):
        H.CARPETA.mkdir();(H.CARPETA/('a'*32+'.json')).write_text('{roto')
        with self.assertRaises(ValueError):H.recuperar({},'a'*32)

    def test_identificador_traversal_y_enlace_rechazados(self):
        for ident in ['../salir','x','A'*32]:
            with self.assertRaises(ValueError):H.recuperar({},ident)
        self.propuesta();id_hilo=self.estado['_id_hilo'];ruta=H.CARPETA/(id_hilo+'.json');contenido=ruta.read_text();ruta.unlink()
        fuera=self.base/'fuera.json';fuera.write_text(contenido);ruta.symlink_to(fuera)
        with self.assertRaises(ValueError):H.recuperar({},id_hilo)
        self.assertEqual(fuera.read_text(),contenido)

    def test_sesion_restaura_hilo_sin_propuesta_permiso_ni_cache(self):
        self.propuesta();self.estado.update(id_propuesta='peligro',_memorias={1:{'contenido':'NO_RESTAURAR'}})
        SES.guardar('caso',self.historial,self.estado,self.base/'sesiones')
        mensajes,prefs=SES.cargar('caso',self.base/'sesiones')
        self.assertIsNone(prefs['_hilo_conversacion']['propuesta']);self.assertNotIn('id_propuesta',prefs);self.assertNotIn('_memorias',prefs)
        self.assertEqual(prefs['_tanda_documentos'],'a'*32);self.assertEqual(mensajes,self.historial)
        self.assertNotIn('NO_RESTAURAR',(self.base/'sesiones/caso.json').read_text())

    def test_sesion_redacta_secretos_en_resultados_y_argumentos(self):
        h=[{'role':'user','content':'api_key=SUPERSECRETO'}, {'role':'assistant','content':'','tool_calls':[{'function':{'name':'crear_archivo','arguments':{'token':'OTROSECRETO','contenido':'password=TERCERSECRETO'}}}]}]
        SES.guardar('secreto',h,{},self.base/'sesiones')
        texto=(self.base/'sesiones/secreto.json').read_text()
        for secreto in ['SUPERSECRETO','OTROSECRETO','TERCERSECRETO']:self.assertNotIn(secreto,texto)

    def test_contexto_acotado_no_muta_literales(self):
        self.propuesta()
        for n in range(30):self.decir(f'Conserva literal "ETIQUETA_{n}" presupuesto {n+400}.','Anotado como antecedente.')
        antes=copy.deepcopy(self.estado['_hilo_conversacion'])
        texto=H.contexto(self.estado,'como dijimos',limite=900)
        self.assertLessEqual(len(texto),900);self.assertEqual(antes,self.estado['_hilo_conversacion'])

    def test_resumen_cien_turnos_conserva_decision_temprana(self):
        self.propuesta()
        for n in range(102):self.decir('Consulta secundaria '+str(n),'Respuesta secundaria sintética. '*30)
        texto=C.resumen_rodante(self.historial,self.estado)
        self.assertIn('Lápiz Rosado',texto);self.assertIn('271',texto);self.assertIn('TIENDA_738',texto)
        vista=C.recortar(self.historial,max_caracteres=6000,resumen=texto)
        self.assertIn(self.historial[-2],vista);self.assertIn(self.historial[-1],vista)
        metricas=C.metricas_ventana(self.historial,vista,texto)
        self.assertTrue(metricas['resumen_incluido']);self.assertTrue(metricas['turno_actual_incluido']);self.assertFalse(metricas['tokenizacion_exacta'])

    def test_resumen_cambio_tema_no_recupera_decision_descartada(self):
        self.propuesta()
        for n in range(10):self.decir('Consulta '+str(n),'Dato secundario.')
        self.decir('otro tema: estudia arroz','Arroz con agua.')
        resumen=C.resumen_rodante(self.historial,self.estado)
        self.assertIn('arroz',resumen);self.assertNotIn('TIENDA_738',resumen)

    def test_resumen_cache_misma_entrada(self):
        h=[{'role':'user','content':f'Nombre "NODO_{i}" presupuesto {i}'} for i in range(12)];estado={}
        primero=C.resumen_rodante(h,estado)
        with patch.object(C,'re') as r:self.assertEqual(C.resumen_rodante(h,estado),primero);r.findall.assert_not_called()

    def test_resumen_excluye_textos_privados_y_secretos(self):
        h=[{'role':'user','content':'no guardes este mensaje: PRIVADO_600'}]+[{'role':'user','content':f'Nombre "NODO_{i}" api_key=SECRETO_{i}'} for i in range(12)]
        texto=C.resumen_rodante(h,{})
        self.assertNotIn('PRIVADO_600',texto);self.assertNotIn('SECRETO_',texto)

    def test_resumen_se_omite_antes_que_turno_actual(self):
        h=[{'role':'system','content':'reglas'},{'role':'user','content':'literal actual '*40}]
        r=C.recortar(h,1000,resumen='resumen '*100)
        self.assertEqual(r,h)

    def test_contexto_persistente_consultable_por_seguimiento(self):
        self.propuesta();self.historial=[]
        texto=S.contexto(self.historial,'eso',estado=self.estado)
        self.assertIn('TIENDA_738',texto);self.assertIn('TIENDA_738',S.consulta_fuentes([], 'eso',estado=self.estado))

    def test_seleccion_anterior_desaparece_al_cambiar_tema(self):
        self.propuesta();self.decir('el segundo','Diseña una pantalla con columnas.')
        self.decir('otro tema: cocina arroz','Calienta una olla.')
        texto=H.iniciar_turno(self.estado,'eso',self.historial)['contexto']
        self.assertNotIn('Diseñar pantalla',texto)
        self.assertNotIn('seleccion_explicita',texto)

    def test_propuesta_nueva_no_arrastra_seleccion_de_lista_antigua(self):
        self.propuesta();self.decir('el segundo','Propongo:\n1. Revisar el requisito.\n2. Medir calidad.\n¿Seguimos?')
        r=H.iniciar_turno(self.estado,'eso',self.historial)
        self.assertNotIn('seleccion_explicita',r['contexto'])
        self.assertEqual(self.estado['_hilo_conversacion']['propuesta']['opciones'][1]['texto'],'Medir calidad.')
        # La elección histórica puede permanecer, claramente atribuida al
        # asistente: conservar progreso no vuelve vigente el menú anterior.
        self.assertIn('opcion_textual_del_asistente',r['contexto'])
        self.assertNotIn('Diseñar pantalla',' '.join(self.estado['_hilo_conversacion']['decisiones']))

    def test_seguimiento_respeta_hilo_vacio_y_no_vuelve_al_menu(self):
        self.propuesta();H.nueva(self.estado)
        self.assertEqual(S.contexto(self.historial,'el segundo',estado=self.estado),'')
        self.assertIsNone(S.iniciar_android(self.historial,'empecemos con el 1',self.estado))

    def test_reapertura_invalida_tambien_respuesta_y_preguntas(self):
        self.propuesta();ident=self.estado['_id_hilo'];nuevo={};H.recuperar(nuevo,ident)
        h=nuevo['_hilo_conversacion']
        self.assertEqual(h['respuesta_anterior'],'');self.assertEqual(h['preguntas'],[])
        self.assertNotIn('Crear proyecto Kotlin',H.contexto(nuevo,'el segundo'))

    def test_sesion_no_guarda_el_turno_privado_completo(self):
        historial=[{'role':'user','content':'un dato público'}, {'role':'assistant','content':'respuesta pública'},
                   {'role':'user','content':'no guardes este mensaje: RESERVADO_USUARIO_902'},
                   {'role':'assistant','content':'RESERVADO_RESPUESTA_903'},
                   {'role':'tool','tool_name':'leer','content':'RESERVADO_HERRAMIENTA_904'},
                   {'role':'user','content':'seguimos con algo público'}, {'role':'assistant','content':'otra respuesta pública'}]
        SES.guardar('privacidad',historial,{},self.base/'sesiones')
        texto=(self.base/'sesiones/privacidad.json').read_text()
        self.assertNotIn('RESERVADO_',texto)
        self.assertIn('dato público',texto);self.assertIn('otra respuesta pública',texto)

    def test_importar_historial_no_importa_respuesta_de_turno_privado(self):
        historial=[{'role':'user','content':'no guardes este mensaje: PRIVADO_930'},
                   {'role':'assistant','content':'Propongo:\n1. PRIVADO_RESPUESTA_931.\n¿Empezamos?'},
                   {'role':'user','content':'Ahora explícame Kotlin'},{'role':'assistant','content':'Explicación pública.'}]
        estado={};H.iniciar_turno(estado,'qué vimos',historial)
        texto=''.join(p.read_text() for p in H.CARPETA.glob('*.json'))
        self.assertNotIn('PRIVADO_',texto)

    def test_terminar_turno_dos_veces_no_duplica_contador(self):
        self.propuesta();turnos=self.estado['_hilo_conversacion']['turnos']
        H.terminar_turno(self.estado,'duplicado','respuesta duplicada')
        self.assertEqual(self.estado['_hilo_conversacion']['turnos'],turnos)

    def test_historial_modelo_corta_documento_y_tema_abandonado(self):
        self.propuesta();pedido='no uses el documento; explícame álgebra'
        r=H.iniciar_turno(self.estado,pedido,self.historial)
        self.historial.append({'role':'user','content':r['pedido']})
        activo=C.historial_activo(self.historial,self.estado)
        texto=json.dumps(activo,ensure_ascii=False)
        self.assertNotIn('TIENDA_738',texto);self.assertIn(pedido,texto)
        self.assertEqual(len(self.historial),3)

    def test_sesion_reanudada_no_envia_menu_antiguo_al_modelo(self):
        self.propuesta();SES.guardar('caso',self.historial,self.estado,self.base/'sesiones')
        hist,prefs=SES.cargar('caso',self.base/'sesiones')
        hist.append({'role':'user','content':'el segundo'})
        activo=C.historial_activo(hist,prefs)
        self.assertEqual(activo,[hist[-1]])

    def test_dos_frases_de_usuario_que_faltaban_en_corpus(self):
        self.assertTrue(S.es_guia('dame una explicacion de que es'))
        self.assertTrue(S.continuacion('Si te quedo algo pendiente termina'))
        self.assertFalse(S.inicio_confirmado('Si dijera "si te quedo algo pendiente termina" no lo ejecutes'))

    def test_reintento_bloqueado_sigue_bloqueado_tras_responder_aclaracion(self):
        self.propuesta();H.iniciar_turno(self.estado,'edita archivo.py',self.historial)
        H.terminar_turno(self.estado,'edita archivo.py','Respuesta interrumpida.',fallido=True,hubo_acciones=True)
        for _ in range(2):
            r=H.iniciar_turno(self.estado,'reintenta',self.historial)
            self.assertTrue(r['aclaracion']);self.assertFalse(r['reintento'])
            H.terminar_turno(self.estado,'reintenta',r['aclaracion'])

    def test_mencion_de_no_uses_documento_no_descarta_tema(self):
        self.propuesta()
        for p in ['Qué significa la frase "no uses el documento"', 'por ejemplo: otro tema: cocina arroz']:
            self.assertFalse(H.cambio_tema(p))
        r=H.iniciar_turno(self.estado,'Qué significa la frase "no uses el documento"',self.historial)
        self.assertEqual(r['tanda'],'a'*32)

    def test_sesion_antigua_no_restaura_turno_que_pedia_privacidad(self):
        carpeta=self.base/'sesiones';carpeta.mkdir()
        p=carpeta/'antigua.json'
        p.write_text(json.dumps({'version':1,'mensajes':[{'role':'user','content':'no guardes este mensaje: RESERVADO_100'},
                    {'role':'assistant','content':'RESERVADO_101'},{'role':'user','content':'tema público'}]}))
        h,_=SES.cargar('antigua',carpeta)
        self.assertEqual(h,[{'role':'user','content':'tema público'}])
        self.assertIn('RESERVADO_100',p.read_text())  # No modificar archivos antiguos por inferencia.

    def test_eleccion_no_es_una_cita_inventada_del_usuario(self):
        self.propuesta();self.decir('el segundo','Siguiente paso de la pantalla.')
        h=self.estado['_hilo_conversacion']
        self.assertNotIn('Diseñar pantalla',' '.join(h['decisiones']))
        self.assertEqual(h['elecciones_confirmadas'][-1],{'usuario_literal':'el segundo','numero':2,'opcion_textual_del_asistente':'Diseñar pantalla.'})
        ident=h['id'];nuevo={};H.recuperar(nuevo,ident)
        self.assertEqual(nuevo['_hilo_conversacion']['elecciones_confirmadas'],h['elecciones_confirmadas'])

    def test_primera_peticion_con_caso_y_tecnologia_es_objetivo(self):
        p='Jarvis me ayudas a empezar a esto en kotlin Android Studio'
        r=H.iniciar_turno(self.estado,p,[])
        self.assertFalse(r['aclaracion']);self.assertIn('Android Studio',r['contexto'])

    def test_importa_objetivo_del_caso_aunque_contenga_referencia(self):
        h=[{'role':'user','content':'Ayúdame con este caso en Kotlin Android Studio'},
           {'role':'assistant','content':'Propongo:\n1. Crear proyecto Kotlin.\n2. Diseñar pantalla.\n¿Empezamos?'}]
        r=H.iniciar_turno(self.estado,'SI te confirmo empecemos',h)
        self.assertTrue(r['aceptada']);self.assertIn('Kotlin Android Studio',r['contexto'])

    def test_referencia_vacia_no_se_convierte_en_objetivo_por_tanda(self):
        r=H.iniciar_turno(self.estado,'eso',[])
        self.assertTrue(r['aclaracion']);self.assertEqual(r['contexto'],'')

    def test_literales_en_titulos_no_son_referencias(self):
        for p in ['Recuérdame "Esto es mío" mañana','Agéndame "Sigue el plan" mañana','edita "Eso era.py"',
                  'recordatorio "el segundo" mañana','"dale"','dime qué significa "otro tema"']:
            with self.subTest(p=p):self.assertFalse(H.es_referencia(p));self.assertFalse(H.confirmacion(p));self.assertFalse(H.cambio_tema(p))
        self.assertFalse(S.es_guia('Agéndame "Guía Python" mañana'))
        self.assertFalse(S.es_guia('recordatorio "Tutorial SQL" mañana'))

    def test_reapertura_de_inferencia_sin_acciones_puede_reintentar(self):
        self.propuesta();p='Explica el anexo de la tienda';H.iniciar_turno(self.estado,p)
        nuevo={};H.recuperar(nuevo,self.estado['_id_hilo'])
        r=H.iniciar_turno(nuevo,'reintenta')
        self.assertTrue(r['reintento']);self.assertEqual(r['pedido'],p)

    def test_pendiente_antiguo_sin_marca_no_se_declara_seguro(self):
        self.propuesta();dato=H.exportar(self.estado)
        dato['pendiente']={'pedido':'edita archivo.py','tanda':'a'*32}
        self.assertFalse(H.validar_reapertura(dato)['fallido']['seguro_repetir'])

    def test_no_hay_mutacion_si_no_se_puede_persistir_marca(self):
        self.propuesta();H.iniciar_turno(self.estado,'edita archivo.py')
        with patch.object(H,'guardar',side_effect=OSError('sin espacio')):
            with self.assertRaises(OSError):H.marcar_accion(self.estado,'editar_archivo')

    def test_sesion_guardada_en_mitad_turno_recupera_estado_pendiente(self):
        self.propuesta();H.iniciar_turno(self.estado,'edita archivo.py');H.marcar_accion(self.estado,'editar_archivo')
        SES.guardar('interrumpida',self.historial,self.estado,self.base/'sesiones')
        _,prefs=SES.cargar('interrumpida',self.base/'sesiones')
        r=H.iniciar_turno(prefs,'reintenta')
        self.assertFalse(r['reintento']);self.assertTrue(r['aclaracion'])

    def test_seguimiento_no_clasifica_literales_como_continuacion(self):
        for p in ['Recuérdame "Esto es mío" mañana','Agéndame "Sigue el plan" mañana','edita "Eso era.py"']:
            with self.subTest(p=p):self.assertFalse(S.continuacion(p))

    def test_guia_android_no_vuelve_tras_cambio_a_cocina(self):
        self.propuesta();self.decir('otro tema: cocina arroz','Propongo:\n1. Lavar arroz.\n2. Cocinar.\n¿Empezamos?')
        self.assertIsNone(S.iniciar_android(self.historial,'empecemos con el 1',self.estado))

    def test_contexto_no_excede_presupuesto_minimo(self):
        self.propuesta()
        for n in range(8):self.decir('Conserva literal "ETIQUETA_'+str(n)+'" presupuesto 450.','Dato guardable del usuario.')
        self.assertLessEqual(len(H.contexto(self.estado,'eso',300)),300)

    def test_reapertura_conserva_paso_explicativo_no_permiso(self):
        self.propuesta();r=H.iniciar_turno(self.estado,'empecemos con el 1',self.historial)
        respuesta=S.iniciar_android(self.historial,r['pedido'],self.estado)
        self.assertIn('New Project',respuesta)
        H.terminar_turno(self.estado,r['pedido'],respuesta)
        nuevo={};H.recuperar(nuevo,self.estado['_id_hilo'])
        siguiente=S.iniciar_android([],'dale',nuevo)
        self.assertNotIn('New Project',siguiente);self.assertIn('nombre del proyecto',siguiente)
        self.assertNotIn('id_propuesta',nuevo);self.assertIsNone(nuevo['_hilo_conversacion']['propuesta'])


if __name__=='__main__':unittest.main()
