"""Caso de guardado aportado por el usuario: permisos y cero memoria real."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import memoria_explicita as M
import jarvis_agente as J
import hilo_conversacion as H
import interfaz_jarvis as I
from cerebro_mcp import ErrorCerebro

PEDIDO='''Guarda un único recuerdo en Segundo Cerebro, proyecto existente **Jarvis**.

**Título:** Integración DeepSeek + Qwen + MCP — 15/10/2026

**Contenido:**
Se integró DeepSeek R1 8B como auxiliar automático de Qwen3:8b mediante Ollama local.
Archivos nuevos: `enrutador_modelos.py` y `coordinador_deepseek.py`.
Estado: pruebas adicionales de seguridad y rendimiento pendientes.

Solicita autorización antes de guardar y confirma el ID creado.'''


class Falso:
    iniciado=True
    def __init__(self):self.filas=[];self.envios=[];self.consultas=[];self.fallo_envio=False;self.fallo_lectura=False;self.respuesta='normal'
    def llamar(self,n,a):
        self.consultas.append((n,dict(a)))
        if n=='listar_proyectos':return {'ok':True,'memorias':[{'proyecto':'Jarvis'}]}
        if n=='buscar_memoria':return {'ok':True,'memorias':copy.deepcopy(self.filas)}
        if n=='listar_memorias':
            return {'ok':True,'memorias':copy.deepcopy(self.filas[a['desplazamiento']:a['desplazamiento']+a['limite']])}
        if n=='consultar_memoria':
            if self.fallo_lectura:raise ErrorCerebro('Lectura sintética interrumpida')
            return {'ok':True,'memorias':[copy.deepcopy(x) for x in self.filas if x['id']==a['id_memoria']]}
        raise AssertionError(n)
    def _enviar(self,n,p):
        self.envios.append((n,copy.deepcopy(p)))
        self.filas.append(dict(p['arguments'],id=1234,tipo='recuerdo'))
        if self.fallo_envio:raise ErrorCerebro('Corte sintético después de guardar')
        if self.respuesta=='incierta':return {'structuredContent':{'result':'recibido'}}
        if self.respuesta=='error':return {'isError':True}
        return {'structuredContent':{'result':'Memoria guardada. ID: 1234'}}


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.addCleanup(patch.stopall)
        patch.object(M,'CARPETA',self.base/'recuerdos').start();patch.object(H,'CARPETA',self.base/'hilos').start()
        self.cliente=Falso();self.dato=M.interpretar(PEDIDO)

    def test_literal_y_separacion_instruccion(self):
        self.assertEqual(self.dato['proyecto'],'Jarvis');self.assertEqual(self.dato['titulo'],'Integración DeepSeek + Qwen + MCP — 15/10/2026')
        self.assertIn('`enrutador_modelos.py`',self.dato['contenido']);self.assertNotIn('Solicita autorización',self.dato['contenido'])

    def test_rotulos_markdown_con_dos_posiciones_de_los_dos_puntos(self):
        for titulo,contenido in [('Título:','Contenido:'),('**Título:**','**Contenido:**'),('**Título**:','**Contenido**:')]:
            p=PEDIDO.replace('**Título:**',titulo).replace('**Contenido:**',contenido)
            with self.subTest(titulo=titulo):
                self.assertEqual(M.interpretar(p),self.dato)
                self.assertNotIn('DeepSeek',M.cabecera(p))

    def test_saltos_windows_conservan_contenido_sin_instruccion_de_control(self):
        p=PEDIDO.replace('\n','\r\n')
        self.assertEqual(M.interpretar(p),dict(self.dato,contenido=self.dato['contenido'].replace('\n','\r\n')))

    def test_no_interpreta_negaciones_ejemplos_ni_documentos(self):
        for p in ['No '+PEDIDO,'Por ejemplo: '+PEDIDO,'"'+PEDIDO+'"','El documento dice: '+PEDIDO,'Explícame cómo guardar una memoria']:
            self.assertIsNone(M.interpretar(p),p)

    def test_campos_faltantes_pide_formato_sin_escribir(self):
        ok,t=M.comando('Guarda un recuerdo en Segundo Cerebro proyecto Jarvis',self.cliente,lambda _:self.fail('Sin permiso innecesario'),{})
        self.assertTrue(ok);self.assertIn('Título',t);self.assertFalse(self.cliente.envios)

    def test_permiso_muestra_texto_real_antes_de_enviar(self):
        vistos=[]
        def confirmar(t):
            self.assertFalse(self.cliente.envios);vistos.append(t);return True
        t=M.guardar(self.cliente,self.dato,confirmar)
        self.assertIn('ID creado: 1234',t);self.assertEqual(len(vistos),1);self.assertIn(self.dato['contenido'],vistos[0])
        self.assertEqual(len(self.cliente.envios),1);self.assertEqual(self.cliente.consultas[-1][0],'consultar_memoria')

    def test_denegacion_cero_escrituras(self):
        t=M.guardar(self.cliente,self.dato,lambda _:False)
        self.assertIn('No autorizaste',t);self.assertFalse(self.cliente.envios)
        self.assertEqual(list(M.CARPETA.glob('*.json')),[])

    def test_repeticion_idempotente_sin_segundo_envio(self):
        M.guardar(self.cliente,self.dato,lambda _:True)
        t=M.guardar(self.cliente,self.dato,lambda _:self.fail('Ya existe'))
        self.assertIn('ID: 1234',t);self.assertEqual(len(self.cliente.envios),1)

    def test_corte_tras_escritura_se_recupera_por_lectura(self):
        self.cliente.fallo_envio=True
        with self.assertRaises(ErrorCerebro):M.guardar(self.cliente,self.dato,lambda _:True)
        self.assertTrue(list(M.CARPETA.glob('*.json')))
        t=M.guardar(self.cliente,self.dato,lambda _:self.fail('No volver a autorizar una segunda copia'))
        self.assertIn('ID: 1234',t);self.assertEqual(len(self.cliente.envios),1)

    def test_corte_sin_resultado_no_reintenta_automaticamente(self):
        self.cliente.fallo_envio=True
        with self.assertRaises(ErrorCerebro):M.guardar(self.cliente,self.dato,lambda _:True)
        self.cliente.filas=[]
        with self.assertRaisesRegex(ErrorCerebro,'anterior quedó sin confirmar'):M.guardar(self.cliente,self.dato,lambda _:True)
        self.assertEqual(len(self.cliente.envios),1)

    def test_lectura_posterior_incierta_no_anuncia_exito(self):
        self.cliente.fallo_lectura=True
        with self.assertRaisesRegex(ErrorCerebro,'No pude comprobar'):M.guardar(self.cliente,self.dato,lambda _:True)

    def test_mismo_titulo_otro_contenido_no_sobrescribe(self):
        self.cliente.filas=[dict(self.dato,id=1,contenido='Otro contenido')]
        with self.assertRaises(ErrorCerebro):M.guardar(self.cliente,self.dato,lambda _:self.fail('No sobrescribir'))
        self.assertFalse(self.cliente.envios)

    def test_proyecto_inexistente_no_se_crea(self):
        with self.assertRaisesRegex(ErrorCerebro,'proyecto existente'):M.guardar(self.cliente,dict(self.dato,proyecto='No existe'),lambda _:self.fail('No guardar'))
        self.assertFalse(self.cliente.envios)

    def test_dos_candidatos_no_adivina(self):
        self.cliente.filas=[dict(self.dato,id=i) for i in [1,2]]
        with self.assertRaisesRegex(ErrorCerebro,'varios recuerdos'):M.guardar(self.cliente,self.dato,lambda _:self.fail('No guardar'))

    def test_secreto_se_redacta_antes_del_permiso_y_envio(self):
        t=M.guardar(self.cliente,dict(self.dato,contenido='api_key=valor-ficticio-privado'),lambda x:'valor-ficticio-privado' not in x)
        self.assertIn('comprobado',t);self.assertNotIn('valor-ficticio-privado',str(self.cliente.envios))

    def test_comprobante_privado_sin_contenido(self):
        self.cliente.fallo_envio=True
        with self.assertRaises(ErrorCerebro):M.guardar(self.cliente,self.dato,lambda _:True)
        f=next(M.CARPETA.glob('*.json'));self.assertEqual(f.stat().st_mode&0o777,0o600)
        self.assertNotIn('DeepSeek',f.read_text())

    def test_guardado_no_es_herramienta_del_modelo(self):
        self.assertNotIn('guardar_memoria',{x['function']['name'] for x in J.HERRAMIENTAS})
        with self.assertRaises(ErrorCerebro):J.CEREBRO.llamar('guardar_memoria',{})

    def test_guardado_directo_no_usa_modelo(self):
        local=lambda p,h,e:J.comando_local(p,h,e,lambda _:True,J.AJUSTES,lambda:None,self.cliente)
        with patch.object(J.O,'solicitar',side_effect=AssertionError('No modelo')):
            ok,t=I.comando(PEDIDO,[],{},lambda *_:self.fail('No herramienta de modelo'),J.SISTEMA,local=local)
        self.assertTrue(ok);self.assertIn('ID creado: 1234',t)

    def test_instrucciones_dentro_del_contenido_no_son_acciones(self):
        pedido=PEDIDO.replace('Se integró DeepSeek R1 8B como auxiliar automático de Qwen3:8b mediante Ollama local.','Crea una carpeta y luego mueve archivo.txt a destino.txt.')
        local=lambda p,h,e:J.comando_local(p,h,e,lambda _:True,J.AJUSTES,lambda:None,self.cliente)
        ok,t=I.comando(pedido,[],{},lambda *_:self.fail('El contenido no son acciones'),J.SISTEMA,local=local)
        self.assertTrue(ok);self.assertIn('ID creado',t);self.assertEqual(len(self.cliente.envios),1)
        self.assertIn('y luego mueve archivo.txt a destino.txt.',self.cliente.envios[0][1]['arguments']['contenido'])

    def test_letras_del_titulo_no_desvian_el_guardado_a_aclaracion(self):
        p=PEDIDO.replace('Integración DeepSeek + Qwen + MCP — 15/10/2026','Eso y la última guía')
        local=lambda p,h,e:J.comando_local(p,h,e,lambda _:False,J.AJUSTES,lambda:None,self.cliente)
        ok,t=I.comando(p,[],{},lambda *_:self.fail('Sin otras acciones'),J.SISTEMA,local=local)
        self.assertTrue(ok);self.assertIn('No autorizaste',t);self.assertFalse(self.cliente.envios)

    def test_nuevo_mas_guardado_limpia_hilo_y_conserva_pedido(self):
        h=[{'role':'user','content':'ANTIGUO'}];e={'_memorias':{1:'viejo'}}
        local=lambda p,h,e:J.comando_local(p,h,e,lambda _:True,J.AJUSTES,lambda:None,self.cliente)
        ok,t=I.comando('/nuevo '+PEDIDO,h,e,lambda *_:self.fail('No herramientas'),J.SISTEMA,local=local)
        self.assertTrue(ok);self.assertIn('ID creado: 1234',t);self.assertNotIn('ANTIGUO',str(h));self.assertNotIn('_memorias',e)

    def test_nuevo_mas_pregunta_llega_sin_prefijo_al_modelo(self):
        h=[{'role':'user','content':'ANTIGUO'}];e={};p='/nuevo Explica el número primo 7 sin herramientas'
        self.assertFalse(I.comando(p,h,e,lambda *_:None,J.SISTEMA)[0]);h.append({'role':'user','content':p})
        def responder(hist,*_):
            self.assertEqual(hist[-1]['content'],'Explica el número primo 7 sin herramientas');return 'Tiene dos divisores positivos.'
        with patch.object(J,'ejecutar_turno',side_effect=responder),patch.object(J.IA.P,'opciones',return_value={'configurado':False,'automatico':False,'preferido':'','timeout_local':35}):
            J.responder_con_respaldo(h,None,lambda _:False,e)
        self.assertEqual(h[-2]['content'],p);self.assertNotIn('_entrada_tras_nuevo',e)

    def test_contenido_no_activa_archivos_internet_codigo(self):
        h=[{'role':'user','content':PEDIDO}]
        nombres={x['function']['name'] for x in J.herramientas_para_turno(h)}
        self.assertIn('listar_proyectos',nombres);self.assertNotIn('preguntar_ia_externa',nombres);self.assertNotIn('crear_archivo',nombres)
        prompt=J.prompt_para_turno(PEDIDO,{})
        self.assertNotIn('Para desarrollar una aplicación o programa por etapas',prompt)

    def test_recuerdo_antiguo_oculto_por_veinte_coincidencias_no_se_duplica(self):
        self.cliente.filas=[dict(self.dato,id=7,tipo='recuerdo')]+[
            dict(self.dato,id=100+i,titulo=f'Conversación de ejemplo {i}',tipo='conversacion') for i in range(125)]
        original=self.cliente.llamar
        def llamar(nombre,args):
            if nombre=='buscar_memoria':return {'ok':True,'memorias':copy.deepcopy(self.cliente.filas[-20:])}
            return original(nombre,args)
        with patch.object(self.cliente,'llamar',side_effect=llamar):
            texto=M.guardar(self.cliente,self.dato,lambda _:self.fail('Ya existe; no crear otra copia'))
        self.assertIn('ID: 7',texto);self.assertFalse(self.cliente.envios)

    def test_segunda_pagina_con_titulo_conflictivo_impide_guardado(self):
        self.cliente.filas=[dict(self.dato,id=100+i,titulo=f'Otro {i}') for i in range(100)]+[
            dict(self.dato,id=7,contenido='Un texto diferente que no se sobrescribe')]
        original=self.cliente.llamar
        def llamar(nombre,args):
            if nombre=='buscar_memoria':return {'ok':True,'memorias':[]}
            return original(nombre,args)
        with patch.object(self.cliente,'llamar',side_effect=llamar),self.assertRaises(ErrorCerebro):
            M.guardar(self.cliente,self.dato,lambda _:self.fail('El título ya existe'))
        self.assertFalse(self.cliente.envios)

    def test_pagina_no_verificable_no_autoriza_una_escritura(self):
        original=self.cliente.llamar
        def llamar(nombre,args):
            return {'ok':True,'memorias':[None]} if nombre=='listar_memorias' else original(nombre,args)
        with patch.object(self.cliente,'llamar',side_effect=llamar),self.assertRaises(ErrorCerebro):
            M.guardar(self.cliente,self.dato,lambda _:self.fail('No se comprobó la ausencia'))
        self.assertFalse(self.cliente.envios)

    def test_pagina_repetida_se_detiene_sin_guardar(self):
        filas=[dict(self.dato,id=i+1,titulo=f'Otro {i}') for i in range(100)]
        original=self.cliente.llamar
        def llamar(nombre,args):
            return {'ok':True,'memorias':copy.deepcopy(filas)} if nombre=='listar_memorias' else original(nombre,args)
        with patch.object(self.cliente,'llamar',side_effect=llamar),self.assertRaisesRegex(ErrorCerebro,'listado cambió'):
            M.guardar(self.cliente,self.dato,lambda _:self.fail('Listado repetido'))
        self.assertFalse(self.cliente.envios)

    def test_limite_de_comprobacion_no_se_confunde_con_ausencia(self):
        original=self.cliente.llamar;paginas=[]
        def llamar(nombre,args):
            if nombre=='listar_memorias':
                paginas.append(args['desplazamiento'])
                return {'ok':True,'memorias':[dict(self.dato,id=i+1,titulo=f'Otro {i}')
                    for i in range(args['desplazamiento'],args['desplazamiento']+100)]}
            return original(nombre,args)
        with patch.object(self.cliente,'llamar',side_effect=llamar),self.assertRaisesRegex(ErrorCerebro,'10000'):
            M.guardar(self.cliente,self.dato,lambda _:self.fail('No se comprobó la ausencia'))
        self.assertEqual(len(paginas),100);self.assertFalse(self.cliente.envios)

    def comprobar_ejemplo_de_entrenamiento(self,aceptar):
        import mejoras_jarvis as MEJORAS
        with patch.object(MEJORAS,'ARCHIVO',self.base/'preferencias.json'):
            vistos=[];e={'_entrenamiento_pendiente':True,'_entrenamiento_situacion':'Cómo responder a una petición de memoria.','_entrenamiento_tema':'general'}
            local=lambda p,h,e:J.comando_local(p,h,e,lambda texto:vistos.append(texto) or aceptar,J.AJUSTES,lambda:None,self.cliente)
            ok,t=I.comando(PEDIDO,[],e,lambda *_:self.fail('No ejecutar el ejemplo'),J.SISTEMA,local)
            self.assertTrue(ok);self.assertIn('preferencia',t.lower());self.assertEqual(len(vistos),1)
            self.assertIn('preferencia de entrenamiento local',vistos[0]);self.assertFalse(self.cliente.consultas);self.assertFalse(self.cliente.envios)
            self.assertEqual(MEJORAS.ARCHIVO.exists(),aceptar)

    def test_ejemplo_de_memoria_durante_entrenamiento_guarda_solo_preferencia(self):
        self.comprobar_ejemplo_de_entrenamiento(True)

    def test_ejemplo_de_memoria_durante_entrenamiento_denegado_no_escribe(self):
        self.comprobar_ejemplo_de_entrenamiento(False)


if __name__=='__main__':unittest.main()
