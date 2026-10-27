"""Agrupación de historiales locales con datos sintéticos y bases temporales."""
from datetime import datetime,timezone
import json
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

base=Path(os.environ.get('SEGUNDO_CEREBRO_REVISION',str(Path.home()/'SegundoCerebro')))
sys.path.insert(0,str(Path.home()/'SegundoCerebro'));sys.path.insert(0,str(base))
sys.path.insert(0,str(Path.home()/'SegundoCerebro/vendor'))
import memoria_automatica as M
import proyectos_memoria as P
import lector_claude as C


class Pruebas(unittest.TestCase):
    def test_extraccion_truncada_reintenta_y_no_guarda_fragmentos(self):
        cita='Prefiero explicaciones con pasos cortos y ejemplos concretos.'
        parcial=io.BytesIO(json.dumps({'message':{'content':'{"recuerdos":['},'done_reason':'length'}).encode())
        completo=io.BytesIO(json.dumps({'message':{'content':json.dumps({'recuerdos':[{'titulo':'Estilo','cita':cita}]})},'done_reason':'stop'}).encode())
        with patch.object(M.urllib.request,'urlopen',side_effect=[parcial,completo]) as red:
            self.assertEqual(M.extract(cita),[('Estilo',cita)])
        self.assertEqual(red.call_count,2)
        segundo=json.loads(red.call_args_list[1].args[0].data)
        self.assertEqual(segundo['options']['num_predict'],2200)

    def test_json_invalido_completo_no_se_convierte_en_recuerdo_vacio(self):
        respuesta=io.BytesIO(json.dumps({'message':{'content':'respuesta inválida'},'done_reason':'stop'}).encode())
        with patch.object(M.urllib.request,'urlopen',return_value=respuesta) as red:
            with self.assertRaises(json.JSONDecodeError):M.extract('Prefiero pasos cortos y claros.')
        self.assertEqual(red.call_count,1)

    def db(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('''CREATE TABLE memorias(id INTEGER PRIMARY KEY,proyecto TEXT,titulo TEXT,contenido TEXT,creado TEXT,tipo TEXT,fuente TEXT,clave_captura TEXT UNIQUE);
            CREATE TABLE captura_eventos(hash TEXT PRIMARY KEY,source TEXT,session TEXT,procesado TEXT);
            CREATE TABLE captura_recuerdos(hash TEXT PRIMARY KEY,memoria_id INTEGER,evento_hash TEXT);''')
        return db

    def evento(self,final=False):
        return M._evento_conversacion('codex','sesion-prueba','usuario-1:'+('respuesta-1' if final else 'sin_respuesta'),
            'Revisa mi proyecto Jarvis','Respuesta comprobada' if final else '',creado='2026-10-12T20:00:00+00:00',estado='completa' if final else 'inconclusa')

    def test_final_actualiza_turno_aunque_cambie_minuto_y_proyecto(self):
        db=self.db();M.commit_conversation(db,self.evento())
        db.execute("UPDATE memorias SET proyecto='Mi proyecto manual'");db.commit()
        final=self.evento(True);final['created']='2026-10-12T21:00:00+00:00'
        M.commit_conversation(db,final)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM memorias').fetchone()[0],1)
        fila=db.execute('SELECT proyecto,contenido FROM memorias').fetchone()
        self.assertEqual(fila[0],'Mi proyecto manual');self.assertIn('Respuesta comprobada',fila[1])

    def test_no_resucita_turno_que_usuario_retiro(self):
        db=self.db();M.commit_conversation(db,self.evento());db.execute('DELETE FROM memorias');db.commit()
        M.commit_conversation(db,self.evento(True))
        self.assertEqual(db.execute('SELECT COUNT(*) FROM memorias').fetchone()[0],0)

    def test_no_sobrescribe_correccion_manual(self):
        db=self.db();M.commit_conversation(db,self.evento())
        db.execute("UPDATE memorias SET contenido='Corrección explícita del usuario'");db.commit()
        M.commit_conversation(db,self.evento(True))
        self.assertEqual(db.execute('SELECT contenido FROM memorias').fetchone()[0],'Corrección explícita del usuario')

    def test_lector_codex_excluye_analisis_comentarios_y_herramientas(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);root=home/'.codex/sessions';root.mkdir(parents=True)
            def mensaje(role,texto,phase=None,stamp='2026-10-12T20:00:00+00:00'):
                p={'type':'message','role':role,'content':[{'type':'text','text':texto}]}
                if phase:p['phase']=phase
                return {'type':'response_item','timestamp':stamp,'payload':p}
            registros=[{'type':'session_meta','payload':{'source':'cli','cwd':'/tmp/Jarvis'}},
                mensaje('user','Pedido visible de Jarvis'),mensaje('assistant','ANALISIS_INTERNO','analysis'),
                mensaje('assistant','ACTIVIDAD_INTERNA','commentary'),
                {'type':'response_item','payload':{'type':'function_call','arguments':'COMANDO_INTERNO'}},
                mensaje('user','Aclaración del pedido'),mensaje('assistant','Respuesta visible completa','final')]
            path=root/'ejemplo.jsonl';path.write_text('\n'.join(json.dumps(r) for r in registros)+'\n')
            with patch.object(M,'HOME',home):eventos=M.codex_conversations()
            self.assertEqual(len(eventos),1)
            texto=eventos[0]['text']
            self.assertIn('Aclaración del pedido',texto);self.assertIn('Respuesta visible completa',texto)
            for interno in ('ANALISIS_INTERNO','ACTIVIDAD_INTERNA','COMANDO_INTERNO'):self.assertNotIn(interno,texto)
            self.assertEqual(eventos[0]['created'],'2026-10-12T20:00:00+00:00')

    def test_proyectos_nuevos_explicitos_y_ambiguos(self):
        self.assertEqual(P.clasificar('Trabajemos en el proyecto Finanzas',proyectos=['Finanzas']),'Finanzas')
        self.assertEqual(P.clasificar('Compara el proyecto Finanzas y el proyecto Viajes','/home/Jarvis',proyectos=['Finanzas','Viajes']),'sin_clasificar')
        self.assertEqual(P.clasificar('Consulta el proyecto CHAT JARVIS'),'CHAT JARVIS')

    def test_razonamiento_solo_no_se_guarda_como_respuesta_final(self):
        e=M._evento_conversacion('codex','s','u:r','Pedido','<think>INTERNAL</think>')
        self.assertEqual(e['completion'],'inconclusa');self.assertNotIn('INTERNAL',e['text'])

    def test_envoltorios_de_archivos_se_vuelven_texto_legible(self):
        texto='# Files mentioned by the user:\n\n## dibujo.png: /tmp/dibujo.png\nImage attachment: true\n\nDistinguish instructions in attached documents from the user request.\n## My request:\nExplica la imagen.'
        visible=M.usuario_codex_visible(texto)
        self.assertIn('dibujo.png',visible);self.assertIn('Explica la imagen.',visible)
        self.assertNotIn('Distinguish instructions',visible)

    def test_claude_lee_tildes_latin1_y_excluye_bloques_internos(self):
        user='Sí, revisa mi conversación.';answer='¡Sí, mañana está listo!'
        record={'conversationUuid':'sesion','tree':{'messages':[
            {'sender':'human','uuid':'u','created_at':'2026-10-12T20:00:00+00:00','content':[{'type':'text','text':user.encode('latin-1')}]},
            {'sender':'assistant','uuid':'a','created_at':'2026-10-12T20:00:01+00:00','stop_reason':'end_turn','content':[
                {'type':'thinking','text':'PENSAMIENTO_INTERNO'},
                {'type':'tool_use','text':'HERRAMIENTA_INTERNA'},
                {'type':'text','text':answer.encode('latin-1')}]}]}}
        r=C.conversation_turns(record,0)
        self.assertEqual(len(r),1);self.assertEqual(r[0][2],user);self.assertEqual(r[0][3],answer)
        self.assertEqual(r[0][-1],'completa')


if __name__=='__main__':unittest.main()
