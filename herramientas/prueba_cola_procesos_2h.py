"""Chat y terminal comparten una reserva acotada, con procesos propios de prueba."""
import io,json,os,select,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import cola_inferencia as C
import cliente_ollama as O


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        self.parche=patch.object(C,'DATOS',self.base/'datos');self.parche.start();self.addCleanup(self.parche.stop)

    def hijo(self):
        fuente='import sys;sys.path.insert(0,'+repr(str(Path(__file__).resolve().parent))+');import cola_inferencia as C\nwith C.reservar(3):\n print("RESERVADO",flush=True)\n input()\n'
        p=subprocess.Popen([sys.executable,'-B','-c',fuente],env=dict(os.environ,JARVIS_DIR=str(self.base),JARVIS_PRUEBAS='1'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def limpiar():
            if p.poll() is None:p.terminate()
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=3)
            for flujo in (p.stdin,p.stdout,p.stderr):flujo.close()
        self.addCleanup(limpiar)
        self.assertTrue(select.select([p.stdout],[],[],3)[0],'El hijo no confirmó su reserva')
        self.assertEqual(p.stdout.readline().strip(),'RESERVADO')
        return p

    def test_otro_proceso_impide_inferencia_y_respeta_plazo(self):
        self.hijo();inicio=time.monotonic()
        with patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama) as error:
            O.solicitar('/api/chat',{},timeout=.08)
        self.assertEqual(error.exception.tipo,'cola');abrir.assert_not_called();self.assertLess(time.monotonic()-inicio,1)

    def test_cierre_del_proceso_libera_reserva_sin_borrar_archivo(self):
        p=self.hijo();p.terminate();p.wait(timeout=3)
        with C.reservar(.2):self.assertTrue((C.DATOS/'ollama_inferencia.lock').is_file())
        self.assertTrue((C.DATOS/'ollama_inferencia.lock').exists())

    def test_anidacion_en_mismo_hilo_no_se_bloquea(self):
        with C.reservar(.2):
            with C.reservar(.01):self.assertEqual(C.LOCAL.profundidad,2)
        self.assertEqual(C.LOCAL.profundidad,0)

    def test_error_de_inferencia_libera_reserva(self):
        with patch.object(O,'ABRIR',return_value=io.BytesIO(b'{"message":{"content":"texto"}}')):
            with self.assertRaisesRegex(RuntimeError,'sintético'):
                with C.reservar(.1):raise RuntimeError('sintético')
        with C.reservar(.1):pass

    def test_metadatos_siguen_disponibles_mientras_otra_terminal_infiere(self):
        self.hijo()
        with patch.object(O,'ABRIR',return_value=io.BytesIO(b'{"version":"ficticia"}')):
            self.assertEqual(O.solicitar('/api/version')['version'],'ficticia')

    def test_reserva_no_sigue_enlace_ni_toca_destino(self):
        C.DATOS.mkdir();fuera=self.base/'fuera';fuera.write_text('CONSERVAR');(C.DATOS/'ollama_inferencia.lock').symlink_to(fuera)
        with self.assertRaises(OSError):
            with C.reservar(.1):self.fail('No debe aceptar enlaces')
        self.assertEqual(fuera.read_text(),'CONSERVAR')


if __name__=='__main__':unittest.main()
