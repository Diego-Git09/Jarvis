"""Ejecuta la consola real en un directorio temporal; no necesita Qwen ni red."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Se propaga a todos los subprocesos, también cuando se ejecuta este archivo solo.
os.environ['JARVIS_PRUEBAS']='1'


class Pruebas(unittest.TestCase):
    def test_archivos_config_tareas_y_sesiones_en_la_consola(self):
        with tempfile.TemporaryDirectory() as carpeta:
            proyecto=Path(carpeta)/'Jarvis';trabajo=proyecto/'trabajo';trabajo.mkdir(parents=True)
            (trabajo/'notas.txt').write_text('Comprar pan\nLlamar a Ana\n',encoding='utf-8')
            comandos=['/modo breve','/timeout 30','/anotar Comprar leche','/tareas','/hecho 1','/tareas todas','/reabrir 1',
                      '/archivos','/copiar notas.txt copia.txt','s','/mover copia.txt final.txt','s','/cambios','/deshacer','s',
                      '/reemplazar notas.txt "Comprar pan" "Comprar leche"','s',
                      '/guardar almuerzo','s','/nuevo','/sesiones','/continuar almuerzo','s','/leer notas.txt','/ultima_accion','/salir']
            env=dict(os.environ,JARVIS_DIR=str(proyecto),PYTHONDONTWRITEBYTECODE='1',NO_COLOR='1')
            p=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('jarvis_agente.py'))],input='\n'.join(comandos)+'\n',env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertNotIn('Traceback',p.stdout)
            self.assertIn('Sesión «almuerzo» recuperada',p.stdout)
            self.assertIn('Comprar leche',p.stdout)
            self.assertEqual((trabajo/'notas.txt').read_text(),'Comprar leche\nLlamar a Ana\n')
            self.assertTrue((trabajo/'copia.txt').exists());self.assertFalse((trabajo/'final.txt').exists())
            config=json.loads((proyecto/'datos'/'configuracion.json').read_text())
            self.assertEqual(config['modo'],'breve');self.assertEqual(config['timeout_modelo'],30)
            tareas=json.loads((proyecto/'datos'/'tareas.json').read_text())
            self.assertFalse(tareas[0]['hecha'])
            sesion=json.loads((proyecto/'datos'/'sesiones'/'almuerzo.json').read_text())
            self.assertTrue(sesion['mensajes'])
            self.assertNotIn('_memorias',sesion['preferencias'])

    def test_respuesta_modelo_interrumpida_no_impide_accesos(self):
        with tempfile.TemporaryDirectory() as carpeta:
            env=dict(os.environ,JARVIS_DIR=carpeta,NO_COLOR='1')
            p=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('jarvis_agente.py'))],input='/ayuda archivos\n/config\n/tareas\n/salir\n',env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('/copiar',p.stdout)
            self.assertIn('Configuración actual',p.stdout)
            self.assertIn('No hay tareas pendientes',p.stdout)

    def test_conversacion_larga_se_guarda_completa(self):
        with tempfile.TemporaryDirectory() as carpeta:
            env=dict(os.environ,JARVIS_DIR=carpeta,NO_COLOR='1')
            comandos=['/hora']*30+['/contexto','/guardar completa','s','/salir']
            p=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('jarvis_agente.py'))],input='\n'.join(comandos)+'\n',env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            sesion=json.loads((Path(carpeta)/'datos'/'sesiones'/'completa.json').read_text())
            self.assertEqual(sum(m['role']=='user' and m['content']=='/hora' for m in sesion['mensajes']),30)
            self.assertIn('Turnos anteriores fuera del contexto',p.stdout)

    def test_utilidades_tareas_exportacion_y_pegado_cancelado(self):
        with tempfile.TemporaryDirectory() as carpeta:
            root=Path(carpeta);env=dict(os.environ,JARVIS_DIR=carpeta,NO_COLOR='1')
            comandos=['/calcular 15% de 200','/anotar Comprar café','/anotar Revisar informe','/tareas','/prioridad 2 alta','/tareas',
                      '/editar_tarea 1 Revisar informe completo','/hecho uno y dos','/tareas todas','/exportar_tareas tareas.md','adelante',
                      '/info tareas.md','/duplicar tareas.md respaldo.md','s','/comparar tareas.md respaldo.md',
                      '/pegar','/carpeta no_crear','/cancelar','/encontrar "*.md"','/salir']
            p=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('jarvis_agente.py'))],input='\n'.join(comandos)+'\n',env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr);self.assertNotIn('Traceback',p.stdout)
            self.assertIn('15% de 200 = 30',p.stdout)
            self.assertIn('mismo contenido',p.stdout)
            self.assertFalse((root/'trabajo'/'no_crear').exists())
            self.assertIn('- [x] Revisar informe completo',(root/'trabajo'/'tareas.md').read_text())
            self.assertTrue(all(t['hecha'] for t in json.loads((root/'datos'/'tareas.json').read_text())))


if __name__=='__main__':unittest.main()
