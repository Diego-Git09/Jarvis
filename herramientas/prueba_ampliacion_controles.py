"""Permisos de limpieza/publicación, perfiles y resistencia de colas sintéticas."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import configuracion_jarvis as C
import limpieza_cerebro as LIM
import estado_ia as E
import conversaciones_jarvis as CAP
from cerebro_mcp import ClienteCerebro,ErrorCerebro
import ordenes_compuestas as ORDEN
import desarrollo_jarvis as D

class MemoriaFalsa(ClienteCerebro):
    def __init__(self):self.d={};self.cambios=[];self.numero=0;self.iniciado=True
    def llamar(self,n,a):
        if n=='listar_memorias':return {'ok':True,'memorias':list(self.d.values())[a.get('desplazamiento',0):a.get('desplazamiento',0)+a.get('limite',100)]}
        if n=='buscar_memoria':return {'ok':True,'memorias':[dict(x) for x in self.d.values() if x['titulo']==a['consulta']]}
        if n=='consultar_memoria':return {'ok':True,'memorias':[dict(self.d[a['id_memoria']])]}
        if n=='corregir_memoria':
            x=self.d[a['id_memoria']]
            if x['contenido']!=a['contenido_esperado']:return {'ok':False}
            x['contenido']=a['contenido_nuevo'];self.cambios.append(n);return {'ok':True}
        if n=='clasificar_memoria':
            x=self.d[a['id_memoria']]
            assert x['contenido']==a['contenido_esperado'];assert x['proyecto']==a['proyecto_esperado']
            x['proyecto']=a['proyecto'];self.cambios.append(n);return {'ok':True}
        raise AssertionError(n)
    def _enviar(self,n,a):
        assert n=='tools/call' and a['name']=='guardar_memoria'
        ident=len(self.d)+1;self.d[ident]=dict(a['arguments'],id=ident);self.cambios.append('nuevo')
        return {'structuredContent':{'result':f'Memoria guardada. ID: {ident}'}}

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
    def test_perfiles_validos_sin_ampliacion_arbitraria(self):
        for n,p in C.PERFILES.items():self.assertEqual(C.validar(dict(C.DEFAULT,**p,perfil=n))['perfil'],n)
        for k,v in [('hilos',99),('perfil',[]),('keep_alive',[]),('num_ctx',999999)]:
            with self.assertRaises(ValueError):C.validar(dict(C.DEFAULT,**{k:v}))
    def test_destino_remoto_sin_credenciales(self):
        self.assertEqual(C.validar_url('http://192.168.1.10:11434/'),'http://192.168.1.10:11434')
        for u in ['ftp://pc','http://u:p@pc','http://pc/api/chat','https://pc?key=secreto','http://pc:99999']:
            with self.assertRaises(ValueError):C.validar_url(u)
    def test_resumen_actualizado_sin_copias(self):
        c=MemoriaFalsa();r=c.publicar_documento(E.TITULO,'Estado inicial',True)
        c.publicar_documento(E.TITULO,'Estado inicial',True);c.publicar_documento(E.TITULO,'Estado actualizado',True)
        self.assertEqual(len(c.d),1);self.assertEqual(c.d[r['id']]['contenido'],'Estado actualizado');self.assertEqual(c.cambios,['nuevo','corregir_memoria'])
    def test_otros_recuerdos_no_se_corrigen(self):
        c=MemoriaFalsa();c.publicar_documento('JARVIS — Tema','uno')
        with self.assertRaises(ErrorCerebro):c.publicar_documento('JARVIS — Tema','otro')
        with self.assertRaises(ValueError):c.publicar_documento('JARVIS — Tema','otro',True)
        self.assertEqual(c.d[1]['contenido'],'uno')
    def test_resumen_duplicado_no_elige_por_inferencia(self):
        c=MemoriaFalsa();c.d={1:{'id':1,'proyecto':'Jarvis','titulo':E.TITULO,'contenido':'uno'},2:{'id':2,'proyecto':'Jarvis','titulo':E.TITULO,'contenido':'dos'}}
        with self.assertRaises(ErrorCerebro):c.publicar_documento(E.TITULO,'otro',True)
        self.assertFalse(c.cambios)
    def test_limpieza_propone_y_no_muta(self):
        filas=[{'id':65,'titulo':'Conversación','proyecto':'personal','contenido':'Estamos desarrollando Jarvis con muchas funciones nuevas.'},{'id':2,'titulo':'Corto','proyecto':'Jarvis','contenido':'Hola'}];antes=json.dumps(filas)
        p=LIM.analizar(filas);self.assertEqual(json.dumps(filas),antes);self.assertTrue(any(x['id']==65 and x.get('destino')=='Jarvis' for x in p))
    def test_limpieza_sin_permiso_no_mueve(self):
        c=MemoriaFalsa();c.d[1]={'id':1,'proyecto':'personal','titulo':'Tema','contenido':'Jarvis proyecto de pruebas con texto completo.'}
        propuesta={'id':1,'titulo':'Tema','proyecto':'personal','contenido_sha256':hashlib.sha256(c.d[1]['contenido'].encode()).hexdigest(),'accion':'clasificar','destino':'Jarvis'}
        p=self.base/'propuesta.json';p.write_text(json.dumps({'propuestas':[propuesta]}))
        with patch.object(LIM,'ARCHIVO',p):r=LIM.aplicar([1],c,lambda _:False)
        self.assertIn('sin permiso',r);self.assertEqual(c.d[1]['proyecto'],'personal')
    def test_limpieza_verifica_original(self):
        c=MemoriaFalsa();c.d[1]={'id':1,'proyecto':'personal','titulo':'Tema','contenido':'Otro contenido cambiado.'}
        p=self.base/'propuesta.json';p.write_text(json.dumps({'propuestas':[{'id':1,'titulo':'Tema','proyecto':'personal','contenido_sha256':'viejo','accion':'clasificar','destino':'Jarvis'}]}))
        with patch.object(LIM,'ARCHIVO',p):r=LIM.aplicar([1],c,lambda _:True)
        self.assertIn('cambió',r);self.assertFalse(c.cambios)
    def test_orden_fuera_de_citas_y_ambiguo(self):
        self.assertEqual(ORDEN.separar('lee "uno y luego dos.txt"'),[])
        self.assertEqual(ORDEN.separar('no copies uno y luego borra dos'),[])
        pasos=ORDEN.separar('lee uno.txt y luego copia uno.txt a dos.txt');self.assertEqual(len(pasos),2)
        llamadas=[]
        r=ORDEN.ejecutar(pasos,lambda p:(llamadas.append(p) or (False,'')))
        self.assertEqual(len(llamadas),1);self.assertIn('pendiente',r)
    def test_tipos_de_argumentos_de_pruebas_no_se_ejecutan(self):
        r=D.entradas_de_pruebas(['resolver(*[[1,2,-1]])\nresolver(*[{"a":1}])'])
        self.assertIn("['list']",r);self.assertIn("['dict']",r)
    def test_cien_turnos_reintento_y_cierre_brusco_sin_sc_real(self):
        cola=self.base/'cola'
        class Cliente:
            timeout=30
            def __init__(self):self.guardadas={};self.falla=True
            def guardar_conversacion(self,p,t,c,k,**kw):
                if self.falla:raise ConnectionError('MCP falso caído')
                self.guardadas[k]=c;return {'ok':True,'tipo':'conversacion'}
        cliente=Cliente();ids=[]
        with patch.object(CAP,'COLA',cola),patch.object(CAP,'en_pruebas',return_value=False):
            for i in range(100):
                ident=CAP.iniciar(f'Pregunta sintética del turno {i} sobre el proyecto.');ids.append(ident);CAP.finalizar(ident,f'Respuesta completa sintética del turno {i} con evidencia.')
            CAP.guardar_pendientes(cliente);self.assertEqual(len(list(cola.glob('*.json'))),100)
            cliente.falla=False
            for _ in range(5):CAP.guardar_pendientes(cliente)
            self.assertEqual(len(cliente.guardadas),100);self.assertEqual(set(ids),set(cliente.guardadas))
            nuevo=CAP.iniciar('Pregunta larga pendiente antes de un cierre brusco.')
            f=cola/(nuevo+'.json');d=json.loads(f.read_text());d['pid']=2147483647;f.write_text(json.dumps(d))
            CAP.recuperar_interrumpidas();self.assertEqual(json.loads(f.read_text())['estado'],'interrumpida')
    def test_dudosos_no_bloquean_la_cola(self):
        with patch.object(CAP,'COLA',self.base/'cola'),patch.object(CAP,'en_pruebas',return_value=False):
            for _ in range(25):CAP.finalizar(CAP.iniciar('hola'),'hola')
            ident=CAP.iniciar('Consulta completa con bastantes palabras de contexto.');CAP.finalizar(ident,'Esta es una respuesta completa verificable.')
            class Cliente:
                timeout=20
                def guardar_conversacion(self,*a,**kw):return {'ok':True,'tipo':'conversacion'}
            r=CAP.guardar_pendientes(Cliente());self.assertEqual(r['dudosas'],25);self.assertEqual(r['guardadas'],1);self.assertEqual(r['pendientes'],0)
    def test_disco_lleno_conserva_el_turno_anterior(self):
        with patch.object(CAP,'COLA',self.base/'cola'),patch.object(CAP,'en_pruebas',return_value=False):
            i=CAP.iniciar('Una pregunta antes de un disco casi lleno.');f=CAP.COLA/(i+'.json');antes=f.read_bytes()
            with patch.object(CAP.os,'replace',side_effect=OSError('Sin espacio')):
                with self.assertRaises(OSError):CAP.finalizar(i,'Una respuesta que no pudo persistirse.')
            self.assertEqual(f.read_bytes(),antes)
if __name__=='__main__':unittest.main()
