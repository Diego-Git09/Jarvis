import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import confirmar_vocabulario as C
import normalizacion_entrada as N
import vocabulario_pendientes as P
import administracion_local as A

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);p=Path(self.tmp.name)
        for mod,k,v in [(C,'ARCHIVO',p/'confirmadas.json'),(P,'ARCHIVO',p/'pendientes.json')]:
            q=patch.object(mod,k,v);q.start();self.addCleanup(q.stop)
    def test_confirmar_no_aprende_sin_si_ni_cambia_el_base(self):
        antes=N.BASE.read_bytes();e={};C.comando('/confirmar_vocabulario',e,lambda _:self.fail('Solo lectura'))
        C.comando('si',e,lambda _:False);self.assertFalse(C.ARCHIVO.exists());self.assertEqual(N.BASE.read_bytes(),antes)
    def test_confirmado_pasa_a_observado_con_evidencia_y_permiso(self):
        e={};C.comando('/confirmar_vocabulario',e,lambda _:False);forma=e['_confirmacion_vocabulario']['forma']
        C.comando('sí',e,lambda _:True)
        self.assertEqual(C.leer()[forma]['estado'],'observado');self.assertEqual(N.lexico()[forma]['origen'],'observado')
        self.assertEqual(C.ARCHIVO.stat().st_mode&0o777,0o600)
    def test_negado_queda_pasivo_sin_cambiar_significado(self):
        e={};C.comando('/confirmar_vocabulario',e,lambda _:False);forma=e['_confirmacion_vocabulario']['forma'];significado=N.lexico()[forma]['significado']
        C.comando('no',e,lambda _:True)
        self.assertEqual(N.lexico()[forma]['origen'],'pasivo');self.assertEqual(N.lexico()[forma]['significado'],significado)
    def test_a_veces_queda_confirmado_con_frecuencia(self):
        e={};C.comando('/confirmar_vocabulario',e,lambda _:False);forma=e['_confirmacion_vocabulario']['forma'];C.comando('a veces',e,lambda _:True)
        self.assertEqual(C.leer()[forma]['uso'],'a veces')
    def test_datos_danados_conservan_lexico_base_y_no_se_sobrescriben(self):
        C.ARCHIVO.write_text('invalido')
        self.assertIn('jarveis',N.lexico())
        with self.assertRaises(ValueError):C.comando('/confirmar_vocabulario',{},lambda _:True)
        self.assertEqual(C.ARCHIVO.read_text(),'invalido')
    def test_solo_hay_una_revision_personal_pendiente(self):
        e={'_revision_respuestas':{'pos':0}};A.comando('/confirmar_vocabulario',e,lambda _:False)
        self.assertNotIn('_revision_respuestas',e);self.assertTrue(A.es_entrada('no',e))
    def test_sanear_pendientes_elimina_credenciales_rutas_correos_y_prompt(self):
        f='me llamo PersonaEjemplo correo demo@example.invalid /home/ejemplo/documento.txt token=FICTICIO_SECRETO cuenta@equipo:~$ revisar'
        P.aclarar(f,'Duda concreta',explicita=True);texto=P.ARCHIVO.read_text()
        for dato in ['PersonaEjemplo','demo@example.invalid','/home/ejemplo','FICTICIO_SECRETO','cuenta@equipo']:self.assertNotIn(dato,texto)
        self.assertIn('[CORREO]',P.presentar())
    def test_pendientes_antiguos_se_muestran_saneados_sin_reescribir(self):
        original=json.dumps([{'frase':'revisa /home/ejemplo/dato.txt correo demo@example.invalid'}]);P.ARCHIVO.write_text(original)
        self.assertNotIn('demo@example.invalid',P.presentar());self.assertEqual(P.ARCHIVO.read_text(),original)
    def test_texto_explicito_privado_no_se_pone_en_pendientes(self):
        P.aclarar('no guardes esto es privado','Duda',explicita=True);self.assertFalse(P.ARCHIVO.exists())

if __name__=='__main__':unittest.main()
