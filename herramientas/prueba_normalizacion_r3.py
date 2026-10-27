import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import normalizacion_entrada as N
import vocabulario_privado as V
from seguridad_texto import privacidad_externa
from conversaciones_jarvis import _redactar
import comprension_peticion as P

class Pruebas(unittest.TestCase):
    def test_original_y_literales_permanecen_exactos(self):
        for t in ['COnsulta esto asi ?', 'edita "jarveis q modifciarlos" en /tmp/aotumatica.py', '```python\nq = "holaaa"\n```', 'guarda texto "SI  tmb"']:
            e=N.analizar(t);self.assertEqual(e.original,t)
            for m in N.PROTEGIDO.finditer(t):self.assertIn(m[0],e.vista)
    def test_vista_observada(self):
        for a,b in [('holaaa','hola'),('siii','si'),('jarveis','jarvis'),('modifciarlos','modificarlos'),('aotumatica','automatica'),('automsatico','automatico'),('promp','prompt')]:self.assertEqual(N.vista(a),b)
    def test_unidades_sin_cambiar_modelos_originales(self):
        for a,b in [('32gbram','32 gb ram'),('40w','40 w'),('60C','60 c'),('77 C','77 c'),('14900hx','14900 hx'),('rtx5070','rtx 5070'),('115 wts','115 watts')]:
            e=N.analizar(a);self.assertEqual(e.original,a);self.assertEqual(e.vista,b)
    def test_duda_no_se_transforma_en_orden(self):
        e=N.analizar('modifica itgo');self.assertTrue(e.dudas);self.assertIn('1.',N.aclaracion(e));self.assertIn('2.',N.aclaracion(e))
    def test_citas_no_producen_dudas(self):self.assertFalse(N.analizar('guarda "itgo"').dudas)
    def test_permisos_solo_afirmaciones_claras(self):
        for s in ['s','si','sí','dale','ok','listo','autorizado','confirmo']:self.assertTrue(N.permiso_claro(s))
        for s in ['siii','a ver','mm','sí pero no borres','sí pero','espera','adelante tal vez','yes','no']:self.assertFalse(N.permiso_claro(s))
    def test_aprender_con_permiso_y_quitar(self):
        with tempfile.TemporaryDirectory() as t,patch.object(V,'ARCHIVO',Path(t)/'aprendido.json'),patch.object(V,'DATOS',Path(t)):
            V.cambiar('checame','revisa',lambda _:False);self.assertEqual(V.leer(),{})
            V.cambiar('checame','revisa',lambda _:True);self.assertEqual(V.leer(),{'checame':'revisa'});self.assertEqual(V.ARCHIVO.stat().st_mode&0o777,0o600)
            V.cambiar('checame',None,lambda _:True);self.assertFalse(V.leer())
    def test_vocabulario_rechaza_codigo_y_rutas(self):
        for a,b in [('x','/borrar'),('x','sudo rm'),('x','token=secreto'),('x','a.py')]:
            if b=='sudo rm':continue
            with self.assertRaises(ValueError):V.validar(a,b)
    def test_ejemplos_no_son_acciones(self):
        for s in ['el comando borra los archivos viejos','por ejemplo copia a b','el programa mueve archivos']:
            self.assertEqual(P.principal(s),'explicar')
    def test_terminal_es_dato(self):
        for s in ['usuario@equipo:~$ comando','Traceback (most recent call last):','NVIDIA-SMI']:
            self.assertTrue(P.parece_terminal(s))
    def test_multipreguntas_y_citas(self):
        self.assertEqual(len(P.preguntas('Que es RAM? Que es CPU?')),2)
        self.assertEqual(P.preguntas('guarda "Que es RAM? Que es CPU?"'),[])
    def test_redaccion_sqlplus_flags_y_zen(self):
        for s,fragmento in [('sqlplus usuario_ficticio/clave_ficticia@host_ficticio','clave_ficticia'),('--password "CLAVE_FICTICIA"','CLAVE_FICTICIA'),('Authorization: Bearer TOKEN_FICTICIO','TOKEN_FICTICIO'),('OPENCODE_API_KEY=CLAVE_FICTICIA','CLAVE_FICTICIA'),('sk-FAKE_TEST_NO_REAL_KEY','FAKE_TEST_NO_REAL_KEY')]:
            self.assertNotIn(fragmento,_redactar(s))
    def test_privacidad_never_envia_datos_locales(self):
        for s in ['Explica este archivo /home/prueba/a.txt','Analiza Traceback y mi equipo','usuario@equipo:~$ explica','Explica mi universidad','Escribe codigo para mi CRM','usa el externo con token=PRUEBA']:
            self.assertFalse(privacidad_externa(s)[0],s)
        self.assertFalse(privacidad_externa('Explica una variable',adjuntos=True)[0]);self.assertTrue(privacidad_externa('Explica una variable')[0])

if __name__=='__main__':unittest.main()
