import json
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch
import externo_zen as Z
from seguridad_texto import privacidad_externa

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);r=Path(self.tmp.name)
        for k,v in [('DATOS',r),('ARCHIVO',r/'estado.json'),('AUDITORIA',r/'envios.jsonl'),('CLAVE',r/'privado'/'zen.key')]:
            p=patch.object(Z,k,v);p.start();self.addCleanup(p.stop)
        p=patch.dict('os.environ',{},clear=True);p.start();self.addCleanup(p.stop)
        self.modelo=next(m for m in Z.modelos() if m['id']=='deepseek-v4.1-flash-free')
        self.pregunta='Escribe una función Python que sume dos enteros. Solo un ejemplo de texto.'
    def activar(self):
        Z.guardar_clave('CLAVE_FICTICIA_PARA_PRUEBAS')
        Z.guardar(dict(Z.estado(),encendido=True,catalogo=[self.modelo['id']],catalogo_fecha=time.time()))
    def test_apagado_inicial_y_bloqueo_anterior_conservado(self):
        import politica_ia
        self.assertFalse(Z.estado()['encendido']);self.assertFalse(politica_ia.permite_externa())
        self.assertIsNone(Z.elegir(self.pregunta,'compleja',{},fallo=True)[0])
    def test_guardado_clave_privado_sin_chat(self):
        Z.guardar_clave('CLAVE_FICTICIA_PARA_PRUEBAS');self.assertEqual(Z.clave(),'CLAVE_FICTICIA_PARA_PRUEBAS');self.assertEqual(Z.CLAVE.stat().st_mode&0o777,0o600)
        Z.CLAVE.chmod(0o644);self.assertEqual(Z.clave(),'')
    def test_sin_catalogo_autenticado_no_envia(self):
        self.activar();d=Z.estado();d.pop('catalogo_fecha');Z.guardar(d)
        self.assertIsNone(Z.elegir(self.pregunta,'compleja',{},fallo=True)[0])
    def test_solo_local_primer_intento(self):
        self.activar();self.assertIsNone(Z.elegir(self.pregunta,'compleja',{})[0]);self.assertIsNotNone(Z.elegir(self.pregunta,'compleja',{},fallo=True)[0])
    def test_saludos_y_simples_no_suben(self):
        self.activar()
        for p in ['hola','Que es un byte?','/diagnostico']:self.assertIsNone(Z.elegir(p,'simple',{},fallo=True)[0])
    def test_negacion_persiste_en_conversacion(self):
        self.activar();e={};Z.elegir('solo local, no uses internet','simple',e)
        self.assertIsNone(Z.elegir(self.pregunta,'compleja',e,fallo=True)[0])
    def test_adjuntos_memorias_y_herramientas_no_llegan(self):
        self.activar()
        for k in ['_adjuntos_turno','_fuentes_turno','_uso_memoria_turno','_hubo_herramientas_turno']:
            self.assertIsNone(Z.elegir(self.pregunta,'compleja',{k:True},fallo=True)[0])
        self.assertIsNone(Z.elegir(self.pregunta,'compleja',{'_tanda_documentos':'a'*32,'_fuentes_turno':True},fallo=True)[0])
    def test_servidor_falso_recibe_solo_pregunta_actual(self):
        self.activar();recibido=[]
        def falso(url,cuerpo,**kw):recibido.append((url,cuerpo));return {'choices':[{'message':{'content':'def suma(a, b): return a + b'}}]}
        r=Z.preguntar(self.pregunta,self.modelo,'fallo local',falso)
        self.assertIn('Respondió: externo',r);url,cuerpo=recibido[0];self.assertEqual(url,Z.ENDPOINT);self.assertEqual(cuerpo['messages'][-1]['content'],self.pregunta);self.assertNotIn('tools',cuerpo)
        auditoria=Z.AUDITORIA.read_text();self.assertNotIn(self.pregunta,auditoria);self.assertNotIn('CLAVE_FICTICIA',auditoria);self.assertEqual(len(json.loads(auditoria)['sha256']),64)
    def test_apagar_descarta_respuesta_ya_en_curso(self):
        self.activar()
        def falso(*a,**kw):Z.apagar();return {'choices':[{'message':{'content':'Respuesta tardía'}}]}
        with self.assertRaises(ConnectionError):Z.preguntar(self.pregunta,self.modelo,'fallo local',falso)
        self.assertFalse(Z.estado()['encendido'])
    def test_http_error_real_sin_inferencias_de_pago(self):
        self.activar()
        def falso(*a,**kw):raise ConnectionError('Zen respondió HTTP 429.')
        with self.assertRaisesRegex(ConnectionError,'429'):Z.preguntar(self.pregunta,self.modelo,'fallo local',falso)
        self.assertNotIn('saldo',Z.estado()['ultimo_error']);self.assertNotIn('pago',Z.estado()['ultimo_error'])
    def test_modelo_desaparecido_se_marca(self):
        self.activar()
        def falso(*a,**kw):raise ConnectionError('Zen respondió HTTP 404.')
        with self.assertRaises(ConnectionError):Z.preguntar(self.pregunta,self.modelo,'fallo local',falso)
        self.assertEqual(Z.estado()['modelos'][self.modelo['id']],'no disponible')
    def test_otro_destino_no_sale_a_red(self):
        with self.assertRaises(ValueError):Z.transporte('https://otro.invalid/chat',{})
    def test_adversos_secretos_rutas_y_datos_academicos(self):
        self.activar()
        for p in ['usa el externo con token=CLAVE_FICTICIA','Explica este log usuario@equipo:~$ comando','Escribe codigo /home/prueba/privado.py','Analiza CRM y contactos','Explica mi evaluación universitaria']:
            self.assertFalse(privacidad_externa(p)[0],p)
            with self.assertRaises(ValueError):Z.preguntar(p,self.modelo,'fallo local',lambda *a,**kw:self.fail('No debe enviar'))
    def test_herramienta_externa_se_rechaza(self):
        self.activar()
        with self.assertRaises(ConnectionError):Z.preguntar(self.pregunta,self.modelo,'fallo local',lambda *a,**kw:{'choices':[{'message':{'content':'hacer','tool_calls':[{}]}}]})
    def test_registro_no_promueve_sin_evidencia(self):
        hecho,t=Z.comando('/externo permitir big-pickle',lambda _:self.fail('No hay ventaja verificada'));self.assertTrue(hecho);self.assertIn('Falta',t)
    def test_actualizacion_catalogo_no_envia_texto(self):
        self.activar();recibido=[]
        def falso(url,**kw):recibido.append(url);return {'data':[{'id':self.modelo['id']}]}
        Z.actualizar_catalogo(lambda _:True,falso);self.assertEqual(recibido,[Z.CATALOGO])
    def test_banco_sin_clave_declara_no_probado(self):
        self.assertIn('No probado con el servicio real',Z.evaluar_modelo(self.modelo['id'],lambda _:self.fail('No hay clave')))
    def test_banco_usa_corpus_fijo_y_no_promueve(self):
        self.activar();import medir_seleccion_20261020 as M
        llamadas=[]
        def falso(url,cuerpo,**kw):
            llamadas.append(cuerpo);return {'choices':[{'message':{'content':'Respuesta sintética CLAVE_FICTICIA_PARA_PRUEBAS'}}]}
        with patch.object(M,'CASOS',[('Explica un byte','simple','byte')]):Z.evaluar_modelo(self.modelo['id'],lambda _:True,falso)
        self.assertEqual(len(llamadas),4)
        archivo=next((Z.DATOS/'evaluaciones_zen').glob('*.json'));d=json.loads(archivo.read_text());self.assertFalse(d['promocion']);self.assertNotIn('CLAVE_FICTICIA_PARA_PRUEBAS',archivo.read_text())
    def test_banco_cancelado_no_hace_otro_envio(self):
        self.activar();llamadas=[]
        def falso(*a,**kw):llamadas.append(1);Z.apagar();return {'choices':[{'message':{'content':'No presentar'}}]}
        Z.evaluar_modelo(self.modelo['id'],lambda _:True,falso)
        self.assertEqual(len(llamadas),1)
        archivo=next((Z.DATOS/'evaluaciones_zen').glob('*.json'));self.assertNotIn('No presentar',archivo.read_text())

if __name__=='__main__':unittest.main()
