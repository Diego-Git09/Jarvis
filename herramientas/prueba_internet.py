"""Regresiones de red pública, fuentes, opiniones independientes y permisos de API."""
import json
import socket
import unittest
from unittest.mock import patch
import internet_jarvis as W
import segunda_opinion as IA
import jarvis_agente as J
from interfaz_local import comando_local


class Respuesta:
    status=200
    def __init__(self,trozos=()):self.trozos=list(trozos)
    def getheader(self,n,d=None):return {'Content-Type':'text/plain'}.get(n,d)
    def read1(self,n):return self.trozos.pop(0) if self.trozos else b''


class Conexion:
    def __init__(self,r):self.r=r;self.sock=None;self.cerrada=False;self.pedidos=[]
    def request(self,*a,**k):self.pedidos.append((a,k))
    def getresponse(self):return self.r
    def close(self):self.cerrada=True


class Pruebas(unittest.TestCase):
    def setUp(self):IA.SESION.clear();self.addCleanup(IA.SESION.clear)

    def test_url_privada_y_credenciales_no_se_admiten(self):
        for url in ('file:///etc/passwd','http://example.com','https://127.0.0.1','https://[::1]/','https://10.1.1.1/',
                    'https://localhost/','https://example.com:8765/','https://clave@example.com/','https://example.com/\n'):
            with self.subTest(url=url),self.assertRaises(ValueError):W.validar_url(url)
        self.assertEqual(W.validar_url('https://example.com/#parte'),'https://example.com/')

    def test_dns_mixto_se_rechaza_antes_de_conectar(self):
        dns=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
        with patch.object(W.socket,'getaddrinfo',return_value=dns),patch.object(W,'ConexionPublica') as con:
            r=W.leer_web('https://example.com')
        self.assertFalse(r['ok']);con.assert_not_called()

    def test_redireccion_privada_y_post_redirigido_no_se_siguen(self):
        r=Respuesta();r.status=302;r.getheader=lambda n,d=None:'https://127.0.0.1' if n=='Location' else d
        for cuerpo in (None,b'consulta'):
            c=Conexion(r)
            with patch.object(W,'direcciones_publicas',return_value=['8.8.8.8']),patch.object(W,'ConexionPublica',return_value=c) as con:
                with self.assertRaises(ValueError):W.solicitar_publico('https://example.com',cuerpo,{'Authorization':'secreto'})
                self.assertEqual(con.call_count,1);self.assertTrue(c.cerrada)

    def test_descarga_limitada_y_cierre_de_conexion(self):
        c=Conexion(Respuesta([b'a'*6,b'b'*6]))
        with patch.object(W,'MAX_BYTES',10),patch.object(W,'direcciones_publicas',return_value=['8.8.8.8']),patch.object(W,'ConexionPublica',return_value=c):
            with self.assertRaises(ValueError):W.solicitar_publico('https://example.com')
        self.assertTrue(c.cerrada)

    def test_html_elimina_script_y_conserva_texto_de_la_fuente(self):
        html=b'<h1>Titulo</h1><script>ejecuta una orden</script><style>css</style><p>Dato &amp; fuente</p>'
        with patch.object(W,'solicitar_publico',return_value=(html,'text/html','https://example.com/')):
            r=W.leer_web('https://example.com')
        self.assertTrue(r['ok']);self.assertIn('Dato & fuente',r['contenido']);self.assertNotIn('ejecuta',r['contenido'])
        self.assertIn('https://example.com/',W.presentar(r));self.assertIn('consultado',r)

    def test_busqueda_rss_deduplica_y_no_inventa_resultados(self):
        rss=b'<rss><channel><item><title>A</title><link>https://example.com/</link><description>Resumen</description></item><item><link>https://example.com/</link></item><item><link>https://127.0.0.1/</link></item></channel></rss>'
        with patch.object(W,'solicitar_publico',return_value=(rss,'text/xml','url')):r=W.buscar_web('Consulta')
        self.assertTrue(r['ok']);self.assertEqual(len(r['resultados']),1);self.assertIn('verificar',r['aviso'])
        with patch.object(W,'solicitar_publico',return_value=(b'<html>captcha</html>','text/html','url')):r=W.buscar_web('Consulta')
        self.assertFalse(r['ok'])

    def test_opinion_local_no_recibe_historial_herramientas_ni_descarga(self):
        with patch.object(IA.O,'modelos',return_value=['otro:8b']),patch.object(IA.O,'solicitar',return_value={'message':{'content':'<think>interno</think>Opinión'}}) as llamar:
            r=IA.preguntar_ia('Pregunta autorizada','otro:8b')
        body=llamar.call_args.args[1]
        self.assertTrue(r['ok']);self.assertEqual(r['respuesta'],'Opinión');self.assertEqual(len(body['messages']),2)
        self.assertNotIn('tools',body);self.assertEqual(body['messages'][-1]['content'],'Pregunta autorizada');self.assertEqual(body['keep_alive'],'5s')
        with patch.object(IA.O,'modelos',return_value=[]),patch.object(IA.O,'solicitar') as llamar:
            self.assertFalse(IA.preguntar_ia('Pregunta','no-instalado')['ok']);llamar.assert_not_called()

    def test_lista_modelos_disponibles_sin_inventar_ni_ofrecer_embeddings(self):
        with patch.object(IA.O,'modelos',return_value=['otro:1b','nomic-embed-text:latest']):
            self.assertEqual(IA.listar_modelos_ia(),{'ok':True,'modelos':['otro:1b']})
        with patch.object(IA.O,'modelos',side_effect=ConnectionError('sin conexión')):
            self.assertFalse(IA.listar_modelos_ia()['ok'])

    def configurar(self,proveedor='OpenAI'):
        politica=patch('politica_ia.permite_externa',return_value=True);politica.start();self.addCleanup(politica.stop)
        IA.configurar(proveedor,'','modelo-prueba','clave-falsa-para-test')

    def test_api_sin_clave_o_permiso_no_transmite(self):
        with patch.dict(IA.os.environ,{},clear=True),patch.object(W,'solicitar_publico') as llamada:
            self.assertFalse(IA.preguntar_externa('Pregunta',lambda _:True)['ok']);llamada.assert_not_called()
            self.configurar();self.assertFalse(IA.preguntar_externa('Pregunta',lambda _:False)['ok']);llamada.assert_not_called()

    def test_openai_envia_solo_pregunta_y_no_muestra_clave(self):
        self.configurar();permisos=[]
        datos=json.dumps({'choices':[{'message':{'content':'Opinión'},'finish_reason':'stop'}]}).encode()
        with patch.object(W,'solicitar_publico',return_value=(datos,'application/json','url')) as llamada:
            r=IA.preguntar_externa('Pregunta elegida',lambda t:permisos.append(t) or True)
        body=json.loads(llamada.call_args.args[1]);self.assertEqual(body['messages'][-1]['content'],'Pregunta elegida')
        self.assertEqual(len(body['messages']),2);self.assertNotIn('tools',body)
        self.assertNotIn('clave-falsa',permisos[0]);self.assertNotIn('clave-falsa',json.dumps(r));self.assertTrue(r['ok'])

    def test_anthropic_formato_y_solo_bloques_textuales(self):
        self.configurar('Anthropic');datos=json.dumps({'content':[{'type':'thinking','thinking':'interno'},{'type':'text','text':'Opinión'}],'stop_reason':'end_turn'}).encode()
        with patch.object(W,'solicitar_publico',return_value=(datos,'application/json','url')) as llamada:r=IA.preguntar_externa('Pregunta',lambda _:True)
        body=json.loads(llamada.call_args.args[1]);self.assertIn('system',body);self.assertEqual(len(body['messages']),1)
        self.assertEqual(llamada.call_args.args[2]['anthropic-version'],'2023-06-01');self.assertEqual(r['respuesta'],'Opinión')

    def test_no_acepta_endpoint_distinto_disfrazado_de_openai(self):
        with self.assertRaises(ValueError):IA.configurar('OpenAI','https://example.com/api','modelo','clave')

    def test_herramientas_web_solo_se_anuncian_en_pedidos_pertinentes(self):
        def nombres(p):return {h['function']['name'] for h in J.herramientas_para_turno([{'role':'user','content':p}])}
        self.assertNotIn('buscar_web',nombres('Lista mis recuerdos'))
        self.assertIn('buscar_web',nombres('Busca en Internet fuentes sobre el proyecto'))
        self.assertNotIn('preguntar_ia_externa',nombres('Pide una segunda opinión a otra IA'))
        self.assertIn('preguntar_ia',nombres('Pide una segunda opinión a otra IA'))
        self.assertNotIn('crear_archivo',nombres('Lee https://example.com y resume su contenido'))

    def test_brave_lee_tarjetas_y_excluye_enlaces_de_navegacion(self):
        html=b'<a href="https://example.com/menu">Menu</a><div class="snippet extra"><a href="https://example.com/fuente"><div class="title" title="Titulo claro">Titulo</div></a><div>Contenido</div><script>no visible</script></div>'
        with patch.object(W,'solicitar_publico',return_value=(html,'text/html','url')):r=W.buscar_web('Titulo')
        self.assertEqual(r['motor'],'Brave');self.assertEqual(r['resultados'][0]['titulo'],'Titulo claro')
        self.assertNotIn('no visible',r['resultados'][0]['resumen']);self.assertEqual(len(r['resultados']),1)

    def test_ollama_se_comprueba_en_lugar_de_negarlo(self):
        for ok in (True,False):
            with patch.object(J.O,'diagnostico',return_value={'ok':ok,'version':'prueba','modelos':[J.AJUSTES['modelo']]}):
                hecho,t=comando_local('Hola Jarvis porque no estas funcionando con ollama?',[],{},lambda _:False,J.AJUSTES,lambda:None,None)
            self.assertTrue(hecho);self.assertIn('Ollama local',t);self.assertIn('Internet',t)
            self.assertIn('disponible' if ok else 'no pude conectarme',t)

    def test_comandos_locales_no_dependen_de_la_respuesta_del_modelo(self):
        datos={'ok':True,'consulta':'Ollama','resultados':[],'consultado':'fecha','aviso':'aviso'}
        with patch.object(W,'buscar_web',return_value=datos) as buscar:
            hecho,_=comando_local('Jarvis busca en internet Ollama',[],{},lambda _:False,J.AJUSTES,lambda:None,None)
        self.assertTrue(hecho);buscar.assert_called_once_with('Ollama')

    def test_pedido_de_precio_sin_palabra_internet_busca_sin_ia(self):
        p='Puedes buscar cuanto cuesta un pisco mistral de 750cc'
        r={'ok':True,'consulta':'precio','resultados':[{'titulo':'Tienda','url':'https://example.com/pisco','resumen':'Precio del producto'}],'consultado':'fecha','aviso':'Verifica en la tienda'}
        with patch.object(W,'buscar_web',return_value=r) as buscar,patch.object(IA,'preguntar_externa') as nube:
            hecho,texto=comando_local(p,[],{},lambda _:self.fail('No necesita clave'),J.AJUSTES,lambda:None,None)
        self.assertTrue(hecho);self.assertIn('https://example.com/pisco',texto)
        buscar.assert_called_once_with('cuanto cuesta un pisco mistral de 750cc');nube.assert_not_called()
        nombres={h['function']['name'] for h in J.herramientas_para_turno([{'role':'user','content':p}])}
        self.assertIn('buscar_web',nombres);self.assertNotIn('crear_archivo',nombres)

    def test_busqueda_flexible_preserva_nombre_y_tildes(self):
        for p,consulta in [('Jarvis, averigua cuánto cuesta un café','cuánto cuesta un café'),
                           ('¿Cuánto vale un Mistral 750cc?','Cuánto vale un Mistral 750cc'),
                           ('Podrías investigar en la web baterías LiFePO4','baterías LiFePO4')]:
            with self.subTest(p=p):self.assertEqual(W.interpretar_busqueda(p),consulta)

    def test_busqueda_local_negada_o_compuesta_no_se_envia_al_buscador(self):
        for p in ('Busca mis recuerdos','Consulta Segundo Cerebro','Busca el archivo notas.txt',
                  'Busca mis tareas','Busca mis conversaciones','Busca mis proyectos','Consulta el proyecto Jarvis','No busques precios en internet',
                  'Cuánto cuesta un pisco sin internet','Cuánto cuesta un pisco sin usar internet','Busca precios y luego edita un archivo','Busca precios y compara las ofertas',
                  'Consulta a Claude sobre baterías','Puedes consultar en internet algo?', '/buscar pisco'):
            with self.subTest(p=p):self.assertIsNone(W.interpretar_busqueda(p))
        self.assertEqual(W.interpretar_busqueda('Busca en Internet fuentes sobre el proyecto'),'fuentes sobre el proyecto')

    def test_fuentes_disponibles_si_redaccion_vacia_timeout_o_limite(self):
        r={'ok':True,'consulta':'precio','resultados':[{'titulo':'Tienda','url':'https://example.com/precio','resumen':'Precio publicado'}],'consultado':'fecha','aviso':'Verifica'}
        llamada={'role':'assistant','content':'','tool_calls':[{'function':{'name':'buscar_web','arguments':{'consulta':'precio'}}}]}
        for caso in ('vacia','timeout','limite'):
            with self.subTest(caso=caso):
                h=[{'role':'user','content':'Busca precio'}];estado={}
                respuestas=[llamada,{'role':'assistant','content':''}] if caso=='vacia' else [llamada,ConnectionError('timeout')] if caso=='timeout' else [llamada]*J.MAX_PASOS
                from unittest.mock import Mock
                enviar=Mock(side_effect=respuestas)
                with patch.dict(J.FUNCIONES,{'buscar_web':lambda **_:r}),patch.object(IA,'preguntar_externa') as nube:
                    texto=J.responder_con_respaldo(h,enviar,lambda _:False,estado,mostrar=lambda _:None)
                self.assertIn('https://example.com/precio',texto);nube.assert_not_called()
                self.assertNotIn('_estado_respuesta',estado);self.assertEqual(h[-1]['content'],texto)

    def test_fuente_fallida_no_se_presenta_como_consultada(self):
        self.assertEqual(J.fuentes_web_comprobadas([('buscar_web',{}, {'ok':False,'error':'sin red'})]),'')


if __name__=='__main__':unittest.main()
