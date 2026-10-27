"""Conversor Office: contratos, aislamiento y rechazo; sin ejecutar LibreOffice."""
import hashlib
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch,Mock
from xml.etree import ElementTree as E

import office_seguro as O


def biff(ident,cuerpo=b''):return struct.pack('<HH',ident,len(cuerpo))+cuerpo


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=O.L.RAIZ)
        self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.doc=self.base/'original.doc';self.doc.write_bytes(b'{\\rtf1 DATO_LITERAL}')

    def convertido(self,cmd,registro,perfil=None):
        salida=Path(cmd[cmd.index('--bind')+1]);(salida/'fuente.txt').write_text('TEXTO_COMPROBADO Ñuñoa',encoding='utf-8')

    def test_perfil_bloquea_antes_de_abrir_sin_fuentes_de_confianza(self):
        p=self.base/'perfil';p.mkdir();q=O._perfil(p);r=E.parse(q).getroot();ns='{'+O.OOR+'}'
        valores={(i.attrib[ns+'path'],x.attrib.get(ns+'name')):x.findtext('value') for i in r for x in i if x.tag=='prop'}
        camino='/org.openoffice.Office.Common/Security/Scripting'
        for clave in ['DisableMacrosExecution','DisableActiveContent','DisablePythonRuntime','DisableOLEAutomation','BlockUntrustedRefererLinks']:
            self.assertEqual(valores[(camino,clave)],'true')
        self.assertEqual(valores[(camino,'MacroSecurityLevel')],'3');self.assertEqual(valores[(camino,'SecureURL')],'')
        self.assertEqual(valores[('/org.openoffice.Office.Writer/Content/Update','Link')],'2')
        self.assertEqual(valores[('/org.openoffice.Office.Calc/Content/Update','Link')],'1')
        self.assertEqual(stat.S_IMODE(q.stat().st_mode),0o600);self.assertEqual(stat.S_IMODE(q.parent.stat().st_mode),0o700)

    def test_comando_cerrado_sin_red_ni_perfil_real(self):
        cmd=O._comando(Path('/tmp/fuente.doc'),Path('/tmp/salida'),Path('/tmp/perfil'),'txt:Text','/usr/bin/bwrap','/usr/bin/prlimit')
        self.assertIn('--unshare-all',cmd);self.assertIn('--new-session',cmd);self.assertIn('--die-with-parent',cmd)
        self.assertIn('--clearenv',cmd);self.assertNotIn('--share-net',cmd)
        self.assertIn('--as=1073741824',cmd);self.assertIn('--cpu=30',cmd);self.assertIn('--fsize=16777216',cmd)
        self.assertIn('-env:UserInstallation=file:///tmp/jarvis-office/perfil',cmd)
        self.assertEqual(cmd.count('--bind'),2)
        montajes=[(cmd[i+1],cmd[i+2]) for i,x in enumerate(cmd) if x=='--ro-bind']
        self.assertNotIn(('/','/'),montajes)
        permitidos={'/usr','/etc/ld.so.cache','/etc/fonts','/etc/libreoffice','/etc/locale.alias','/etc/localtime','/tmp/fuente.doc'}
        self.assertTrue(all(origen in permitidos for origen,_ in montajes))
        self.assertEqual(cmd[-1],'/tmp/jarvis-office/entrada/fuente.doc');self.assertNotIn('sh',cmd)

    def test_no_sube_el_techo_heredado_del_lector(self):
        import resource
        for mib in (64,256,512):
            with self.subTest(mib=mib),patch.object(resource,'getrlimit',return_value=(mib*1024**2,mib*1024**2)):
                cmd=O._comando(self.doc,self.base,self.base,'txt:Text','bwrap','prlimit')
                self.assertIn(f'--as={mib*1024**2}',cmd)

    def test_no_herramientas_no_abre_documento(self):
        with patch.object(O.shutil,'which',return_value=None),patch.object(O.subprocess,'Popen') as p:
            with self.assertRaises(O.OfficeNoDisponible):O.convertir(self.doc)
        p.assert_not_called()

    def test_esquema_ausente_no_abre_documento(self):
        with patch.object(O,'ESQUEMA',self.base/'ausente.xcd'),patch.object(O.shutil,'which',return_value='/bin/true'),patch.object(O,'BINARIO',Path('/bin/true')):
            with self.assertRaises(O.OfficeNoDisponible):O._herramientas()

    def test_esquema_sin_interruptor_global_se_rechaza(self):
        q=self.base/'schema.xcd';q.write_text('<data/>')
        with patch.object(O,'ESQUEMA',q),patch.object(O.shutil,'which',return_value='/bin/true'),patch.object(O,'BINARIO',Path('/bin/true')):
            with self.assertRaises(O.OfficeNoDisponible):O._herramientas()

    def test_texto_funcional_simulado_original_intacto_y_temporal_se_borra(self):
        antes=hashlib.sha256(self.doc.read_bytes()).hexdigest();vistos=[]
        def convertir(cmd,registro,perfil=None):
            self.assertTrue((perfil/'user/registrymodifications.xcu').is_file())
            entrada=next(Path(cmd[i+1]) for i,x in enumerate(cmd) if x=='--ro-bind' and cmd[i+2].endswith('/entrada/fuente.doc'));vistos.append(entrada)
            self.assertEqual(entrada.read_bytes(),self.doc.read_bytes());self.assertNotEqual(entrada,self.doc)
            self.convertido(cmd,registro,perfil)
        with patch.object(O,'_herramientas',return_value=('/usr/bin/bwrap','/usr/bin/prlimit')),patch.object(O,'_ejecutar',side_effect=convertir):
            self.assertIn('TEXTO_COMPROBADO',O.convertir(self.doc))
        self.assertEqual(hashlib.sha256(self.doc.read_bytes()).hexdigest(),antes);self.assertTrue(vistos);self.assertFalse(vistos[0].exists())

    def test_formato_arbitrario_rechazado_antes_de_abrir(self):
        with patch.object(O.subprocess,'Popen') as p,self.assertRaises(ValueError):O.convertir(self.doc,'pdf;rm -rf /')
        p.assert_not_called()

    def test_fuera_de_alcance_no_lanza_conversor(self):
        with patch.object(O.L,'_resolver',side_effect=ValueError('No autorizado')),patch.object(O,'_ejecutar') as ejecutar:
            with self.assertRaises(ValueError):O.convertir(self.doc)
        ejecutar.assert_not_called()

    def test_tamano_entrada_no_carga_archivo(self):
        with self.doc.open('wb') as f:f.truncate(O.MAX_ENTRADA+1)
        with patch.object(O,'_copiar') as copiar,self.assertRaises(ValueError):O.convertir(self.doc)
        copiar.assert_not_called()

    def test_fuente_cambiada_no_se_presenta(self):
        def cambiado(cmd,registro,perfil=None):self.convertido(cmd,registro,perfil);self.doc.write_bytes(b'cambiado')
        with patch.object(O,'_herramientas',return_value=('bwrap','prlimit')),patch.object(O,'_ejecutar',side_effect=cambiado),self.assertRaisesRegex(ValueError,'cambió'):
            O.convertir(self.doc)

    def test_salida_enlazada_rechazada(self):
        def enlazar(cmd,registro,perfil=None):Path(cmd[cmd.index('--bind')+1],'fuente.txt').symlink_to(self.doc)
        with patch.object(O,'_herramientas',return_value=('bwrap','prlimit')),patch.object(O,'_ejecutar',side_effect=enlazar),self.assertRaisesRegex(ValueError,'no produjo'):
            O.convertir(self.doc)

    def test_salida_recortada_tiene_aviso_sin_leer_todo(self):
        def extensa(cmd,registro,perfil=None):Path(cmd[cmd.index('--bind')+1],'fuente.txt').write_text('T'*20000)
        with patch.object(O,'_herramientas',return_value=('bwrap','prlimit')),patch.object(O,'_ejecutar',side_effect=extensa):t=O.convertir(self.doc,max_caracteres=200)
        self.assertLessEqual(len(t),200);self.assertIn('parcial',t)

    def test_plazo_mata_grupo_y_no_reintenta_sin_control(self):
        p=Mock(pid=123456);p.wait.side_effect=[subprocess.TimeoutExpired(['falso'],35),0]
        with patch.object(O.subprocess,'Popen',return_value=p) as abrir,patch.object(O.os,'killpg') as matar:
            with self.assertRaisesRegex(ValueError,'plazo'):O._ejecutar(['falso'],self.base/'log')
        self.assertEqual(abrir.call_count,1);matar.assert_called_once_with(123456,O.signal.SIGKILL)

    def test_namespace_rechazado_no_tiene_fallback(self):
        p=Mock();p.wait.return_value=1
        def lanzar(*a,**kw):kw['stdout'].write(b'bwrap: namespace denied');return p
        with patch.object(O.subprocess,'Popen',side_effect=lanzar) as abrir:
            with self.assertRaises(O.OfficeNoDisponible):O._ejecutar(['bwrap'],self.base/'log')
        self.assertEqual(abrir.call_count,1)

    def test_reinicio81_acotado_restaura_perfil(self):
        perfil=self.base/'perfil';perfil.mkdir();O._perfil(perfil)
        a=Mock();a.wait.return_value=81;b=Mock();b.wait.return_value=0
        with patch.object(O.subprocess,'Popen',side_effect=[a,b]) as abrir,patch.object(O,'_perfil',wraps=O._perfil) as politica:
            O._ejecutar(['falso'],self.base/'log',perfil=perfil)
        self.assertEqual(abrir.call_count,2);self.assertEqual(politica.call_count,1)

    def test_biff_valores_sin_formulas_se_acepta(self):
        datos=biff(0x0809,struct.pack('<HH',0x0600,0x0005))+biff(0x0203,b'\0'*14)+biff(0x000A)
        self.assertEqual(O._validar_biff([datos[:7],datos[7:]]),3)

    def test_biff_formula_no_llega_a_conversor(self):
        inicio=biff(0x0809,struct.pack('<HH',0x0600,0x0005))
        for ident in [0x0006,0x0206,0x0406,0x0221,0x04BC,0x0018,0x01AE,0x002F]:
            with self.subTest(ident=ident),self.assertRaises(ValueError):O._validar_biff([inicio+biff(ident,b'NO_EJECUTAR')])

    def test_biff_hoja_macro_o_truncado_se_rechaza(self):
        with self.assertRaises(ValueError):O._validar_biff([biff(0x0809,struct.pack('<HH',0x0600,0x0040))])
        with self.assertRaises(ValueError):O._validar_biff([biff(0x0809,struct.pack('<HH',0x0600,0x0005))+b'\x06\x00\xff'])

    def test_xls_no_verificable_no_llega_a_conversor(self):
        p=self.base/'no.xls';p.write_bytes(b'no es un OLE')
        with patch.object(O,'_herramientas',return_value=('bwrap','prlimit')),patch.object(O,'_ejecutar') as ejecutar:
            with self.assertRaises(ValueError):O.convertir(p,'csv:Text - txt - csv (StarCalc)')
        ejecutar.assert_not_called()

    def test_configuracion_de_perfil_no_se_sigue_por_enlace(self):
        p=self.base/'perfil';p.mkdir();(p/'user').symlink_to(self.base)
        with self.assertRaises(ValueError):O._perfil(p)


if __name__=='__main__':unittest.main()
