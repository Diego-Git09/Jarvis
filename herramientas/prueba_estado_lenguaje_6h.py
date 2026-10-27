"""Diagnóstico explícito y respeto de ejemplos/negativas, con respuestas falsas."""
import hashlib
import json
import unittest
from unittest.mock import Mock,patch

import configuracion_jarvis as C
import interfaz_jarvis as I
import interfaz_local as L
from evaluar_estado_lenguaje_6h import CASOS


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.cb=Mock();self.cb.llamar.return_value={'ok':True,'consultado':'2030-01-01T00:00:00+00:00','fuentes':[]}
        self.estado={};self.h=[{'role':'system','content':'Reglas sintéticas sin modelo.'}]
        self.permisos=Mock(return_value=False);self.acciones=Mock(side_effect=AssertionError('No ejecutar herramientas externas'))
        self.dato={'ok':True,'version':'VERSION_FICTICIA_41','modelos':[C.DEFAULT['modelo']]}
        self.local=lambda p,h,e:L.comando_local(p,h,e,self.permisos,dict(C.DEFAULT),lambda:None,self.cb,ejecutar=self.acciones)

    def pedir(self,p):return I.comando(p,self.h,self.estado,self.acciones,'reglas',local=self.local)

    def test_corpus_estado_conserva_la_huella_original(self):
        raw=(json.dumps(CASOS,ensure_ascii=False,indent=2)+'\n').encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'713646022ed69c80ac0ad5cd83d014d086c19548ad6ff44e1f400fb300b8cc45')

    def test_destino_remoto_no_se_describe_como_conexion_local(self):
        with patch.object(L.O,'BASE','http://servidor.example.invalid:11434'),patch.object(L.O,'diagnostico',return_value=self.dato):
            ok,t=self.pedir('revisa si Ollama responde')
        self.assertTrue(ok);self.assertIn('servidor Ollama configurado',t);self.assertNotIn('Ollama local',t)
        self.assertNotIn('no requiere Internet',t)

    def test_fallo_actual_no_niega_capacidades_ni_confirma_respuestas_anteriores(self):
        with patch.object(L.O,'diagnostico',return_value={'ok':False,'error':'Error HTTP sintético'}):ok,t=self.pedir('¿estás conectado a Ollama?')
        self.assertTrue(ok);self.assertIn('no pude conectarme',t);self.assertIn('Error HTTP sintético',t)
        self.assertIn('no prueba que una respuesta anterior',t);self.assertNotIn('no tengo herramientas',t)

    def test_modelo_ausente_se_distingue_de_servidor_disponible(self):
        with patch.object(L.O,'diagnostico',return_value=dict(self.dato,modelos=[])):ok,t=self.pedir('funciona Ollama')
        self.assertTrue(ok);self.assertIn('Ollama disponible',t);self.assertIn('no aparece instalado',t)

    def test_practica_con_ejemplo_de_estado_no_dispara_consultas(self):
        self.estado['_entrenamiento_pendiente']={'caso':'Caso sintético'}
        item={'situacion':'Caso sintético','preferencia':'Ollama está funcionando'}
        with patch.object(L.MEJORAS,'proponer',return_value=item),patch.object(L.O,'diagnostico') as comprobar:
            ok,t=self.pedir(item['preferencia'])
        self.assertTrue(ok);comprobar.assert_not_called();self.cb.llamar.assert_not_called()
        self.assertIn('No guardé la preferencia',t)

    def test_practica_con_ejemplo_de_cerebro_no_lo_consulta(self):
        self.estado['_entrenamiento_pendiente']={'caso':'Caso sintético'}
        item={'situacion':'Caso sintético','preferencia':'puedes ver mi segundo cerebro'}
        with patch.object(L.MEJORAS,'proponer',return_value=item):ok,t=self.pedir(item['preferencia'])
        self.assertTrue(ok);self.cb.llamar.assert_not_called();self.assertIn('No guardé la preferencia',t)


def caso(c):
    def prueba(self):
        with patch.object(L.O,'diagnostico',return_value=self.dato) as consultar:
            ok,t=self.pedir(c['pedido'])
        if c['diagnostico_esperado']:
            self.assertTrue(ok);consultar.assert_called_once();self.assertIn('VERSION_FICTICIA_41',t)
        else:consultar.assert_not_called()
        self.permisos.assert_not_called();self.acciones.assert_not_called()
    return prueba


for c in CASOS:setattr(Pruebas,'test_'+c['id'].replace('-','_'),caso(c))
if __name__=='__main__':unittest.main()
