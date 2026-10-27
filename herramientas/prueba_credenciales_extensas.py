import unittest
from conversaciones_jarvis import _redactar

class Pruebas(unittest.TestCase):
    def test_urls(self):
        for url in ['https://persona:clavecorta@ejemplo.test','http://u:p@localhost:1234','https://u:p%40x@ejemplo.test/ruta']:
            r=_redactar(url);self.assertNotIn('clavecorta',r);self.assertNotIn('u:p',r);self.assertIn('REDACTADAS',r)
    def test_cabeceras(self):
        for n in ['Authorization','Proxy-Authorization','X-Api-Key','Api-Key','Cookie','Set-Cookie']:
            for valor in ['Bearer abc','Basic abc','clave corta','"secreto"']:
                r=_redactar(n+': '+valor+'\ntexto público');self.assertNotIn(valor,r);self.assertIn('texto público',r)
    def test_parametros(self):
        r=_redactar('https://ejemplo.test/?api_key=secreto&token=otro&tema=clima')
        self.assertNotIn('secreto',r);self.assertNotIn('=otro',r);self.assertIn('tema=clima',r)
    def test_prefijos_sinteticos(self):
        # Construidos únicamente para esta prueba; ninguna clave del usuario.
        for token in ['AIza'+'Z'*25,'hf_'+'Z'*25,'xoxb-'+'Z'*30,'sk-'+'z'*30]:self.assertNotIn(token,_redactar(token))
    def test_no_redacta_prosa_publica(self):
        for t in ['Tengo diez tokens de contexto disponibles.','La autorización requiere tu permiso.','El clima será templado.']:
            self.assertEqual(_redactar(t),t)
if __name__=='__main__':unittest.main()
