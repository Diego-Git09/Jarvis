import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import adjuntos_jarvis as A
import revision_fallos as F
from guias_contexto_r3 import guia
import acceso_archivos as ACCESO
import conversaciones_jarvis as C

class Pruebas(unittest.TestCase):
    def test_cinco_guias_disponibles_con_limites(self):
        for t in ['spring','microservicios','kotlin','oracle','linux']:
            s=guia(t);self.assertIn('1.',s);self.assertIn('2.',s);self.assertGreater(len(s),600)
        self.assertIn('No hay SQL*Plus',guia('oracle'))
    def test_orden_de_adjuntos_y_alias_sin_inferir(self):
        e={'_adjuntos_orden':[{'nombre':'anterior.txt','ruta':'/tmp/anterior.txt'}]}
        A.recordar_referencia([{'nombre':'antes de iniciar.txt','ruta':'/tmp/uno.txt'},{'nombre':'despues de iniciar.txt','ruta':'/tmp/dos.txt'}],e)
        self.assertEqual(A.resolver_adjunto('la primera',e),'/tmp/uno.txt');self.assertEqual(A.resolver_adjunto('el segundo',e),'/tmp/dos.txt')
        self.assertEqual(A.resolver_adjunto('antes de iniciar',e),'/tmp/uno.txt');self.assertEqual(A.resolver_adjunto('el de antes',e),'/tmp/anterior.txt')
    def test_referencia_ambigua_no_elige(self):
        e={'_adjuntos_orden':[{'nombre':'antes de iniciar A.txt','ruta':'a'},{'nombre':'antes de iniciar B.txt','ruta':'b'}]}
        with self.assertRaises(ValueError):A.resolver_adjunto('antes de iniciar',e)
        with self.assertRaises(ValueError):A.resolver_adjunto('la tercera',e)
    def test_fallos_se_agrupan_sin_respuestas_como_casos(self):
        filas=[{'id':1,'proyecto':'CHAT JARVIS','contenido':'Usuario:\nExplica un concepto\n\nRespuesta parcial de Jarvis:\nno pude por memoria GPU'},
            {'id':2,'proyecto':'Jarvis','contenido':'Usuario:\nNo registrar\nRespuesta parcial:\nerror'}]
        d=F.analizar(filas);self.assertEqual(d['recursos'][0]['caso'],'Explica un concepto');self.assertEqual(sum(map(len,d.values())),1)
    def test_revisar_fallos_solo_usa_lecturas(self):
        class Cliente:
            def llamar(self,n,a):
                assert n=='listar_memorias';assert a['proyecto']=='CHAT JARVIS'
                return {'memorias':[]}
        self.assertIn('Solo lectura',F.revisar(Cliente()))
    def test_novedades_persisten_solo_con_permiso_y_no_se_releen_como_nuevas(self):
        import entorno_jarvis
        class Cliente:
            def llamar(self,n,a):return {'memorias':[]}
        with tempfile.TemporaryDirectory() as d:
            raiz=Path(d);p=raiz/'trabajo';p.mkdir()
            (p/'JARVIS_CAMBIOS_RECIENTES.md').write_text('1. Mejora comprobada\n2. Otra mejora\n')
            with patch.object(F,'VISTAS',raiz/'datos/vistas.json'),patch.object(entorno_jarvis,'PROYECTO',raiz):
                F.novedades(Cliente(),{},lambda _:False);self.assertFalse(F.VISTAS.exists())
                texto=F.novedades(Cliente(),{},lambda _:True);self.assertIn('Mejora comprobada',texto)
                self.assertEqual(F.VISTAS.stat().st_mode&0o777,0o600)
                texto=F.novedades(Cliente(),{},lambda _:False)
                self.assertIn('No hay un reporte local posterior',texto);self.assertLessEqual(len(texto.splitlines()),10)
    def test_novedades_no_sobrescribe_un_enlace(self):
        class Cliente:
            def llamar(self,n,a):return {'memorias':[]}
        with tempfile.TemporaryDirectory() as d:
            raiz=Path(d);real=raiz/'real';real.write_text('conservar');p=raiz/'vistas';p.symlink_to(real)
            with patch.object(F,'VISTAS',p),self.assertRaises(ValueError):F.novedades(Cliente(),{},lambda _:True)
            self.assertEqual(real.read_text(),'conservar')
    def test_claves_zen_y_opencode_no_son_archivos_de_chat(self):
        hogar=Path.home()
        self.assertTrue(ACCESO.protegida(hogar/'.config/jarvis/zen.key'));self.assertTrue(ACCESO.protegida(hogar/'.local/share/opencode/auth.json'))
    def test_captura_no_sigue_enlaces(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'destino').mkdir();(p/'enlace').symlink_to(p/'destino',target_is_directory=True)
            with self.assertRaises(ValueError):C._atomic(p/'enlace/datos.json',{'x':1})
            self.assertFalse((p/'destino/datos.json').exists())
    def test_contrato_sql_de_datos_ficticios(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('CREATE TABLE ventas(region TEXT,monto INTEGER); INSERT INTO ventas VALUES ("A",3),("A",5),("B",2);')
        self.assertEqual(db.execute('SELECT region, SUM(monto) FROM ventas GROUP BY region ORDER BY region').fetchall(),[('A',8),('B',2)])
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'),'Compilador Java no disponible')
    def test_logica_java_compila_y_corre_realmente(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Contrato.java';p.write_text('class Contrato { static int total(int a,int b) { return Math.addExact(a,b); } public static void main(String[] args) { if(total(3,5)!=8) throw new AssertionError(); System.out.print("OK"); }}')
            c=subprocess.run(['javac','-d',d,str(p)],capture_output=True,text=True,timeout=20);self.assertEqual(c.returncode,0,c.stderr)
            r=subprocess.run(['java','-cp',d,'Contrato'],capture_output=True,text=True,timeout=10);self.assertEqual(r.stdout,'OK');self.assertEqual(r.returncode,0)
    def test_linux_lectura_real_memoria(self):
        t=Path('/proc/meminfo').read_text();self.assertIn('MemTotal:',t);self.assertIn('MemAvailable:',t)

if __name__=='__main__':unittest.main()
