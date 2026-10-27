"""Salud HTTP real en loopback y respuestas ambiguas: ningún servicio del usuario."""
import io,json,socket,unittest,urllib.error
from unittest.mock import patch
import salud_ollama as S

class Pruebas(unittest.TestCase):
    def test_version_valida_sin_cargar_modelos(self):
        with patch.object(S.urllib.request,'build_opener') as abrir:
            abrir.return_value.open.return_value=io.BytesIO(b'{"version":"prueba"}')
            self.assertEqual(S.comprobar('http://127.0.0.1:23456'),{'ok':True,'tipo':'disponible','version':'prueba'})
            self.assertEqual(abrir.return_value.open.call_args.args[0],'http://127.0.0.1:23456/api/version')
    def test_rechazo_es_detenido(self):
        with patch.object(S.urllib.request,'build_opener') as abrir:
            abrir.return_value.open.side_effect=urllib.error.URLError(ConnectionRefusedError(111,'sintético'))
            self.assertEqual(S.comprobar('http://127.0.0.1:23456')['tipo'],'detenido')
    def test_timeout_no_equivale_a_apagado(self):
        with patch.object(S.urllib.request,'build_opener') as abrir:
            abrir.return_value.open.side_effect=socket.timeout()
            self.assertEqual(S.comprobar('http://127.0.0.1:23456')['tipo'],'timeout')
    def test_403_y_503_no_equivalen_a_apagado_y_cierran(self):
        for codigo in (403,404,429,500,503):
            raw=io.BytesIO(b'no enviar este contenido')
            error=urllib.error.HTTPError('http://127.0.0.1:23456',codigo,'sintético',{},raw)
            with self.subTest(codigo=codigo),patch.object(S.urllib.request,'build_opener') as abrir:
                abrir.return_value.open.side_effect=error
                r=S.comprobar('http://127.0.0.1:23456')
                self.assertEqual(r['tipo'],'http');self.assertEqual(r['codigo'],codigo);self.assertTrue(raw.closed)
    def test_destinos_ajenos_se_rechazan_antes_de_red(self):
        for url in ('https://example.invalid','http://0.0.0.0:23456','http://user:clave@127.0.0.1:23456','http://127.0.0.1:23456/ruta'):
            with self.subTest(url=url),patch.object(S.urllib.request,'build_opener') as red:
                self.assertFalse(S.comprobar(url)['ok']);red.assert_not_called()
    def test_iniciar_https_no_es_posible_sin_certificado(self):
        with self.assertRaises(ValueError):S.validar_destino('https://127.0.0.1:23456',iniciar=True)
    def test_datos_de_modelo_no_sustituyen_version(self):
        for d in ({},[],{'version':1},{'version':''},{'version':'x'*101},{'version':'x\ny'}):
            with self.subTest(datos=d),patch.object(S.urllib.request,'build_opener') as abrir:
                abrir.return_value.open.return_value=io.BytesIO(json.dumps(d).encode())
                self.assertFalse(S.comprobar('http://127.0.0.1:23456')['ok'])
    def test_version_grande_no_se_lee_entera(self):
        with patch.object(S.urllib.request,'build_opener') as abrir:
            abrir.return_value.open.return_value=io.BytesIO(b'x'*5000)
            self.assertFalse(S.comprobar('http://127.0.0.1:23456')['ok'])
    def test_redireccion_no_se_sigue(self):
        with self.assertRaises(ValueError):S.SinRedireccion().redirect_request(None,None,302,'',{},'https://example.invalid')
    def test_error_de_permisos_no_afirma_que_esta_apagado(self):
        with patch.object(S.urllib.request,'build_opener') as abrir:
            abrir.return_value.open.side_effect=PermissionError()
            self.assertEqual(S.comprobar('http://127.0.0.1:23456')['tipo'],'conexion')

if __name__=='__main__':unittest.main()
