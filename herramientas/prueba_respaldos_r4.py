import base64,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import respaldos_configuracion as R
class Pruebas(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.raiz=Path(t.name)
        p=patch.object(R,'DATOS',self.raiz/'datos');p.start();self.addCleanup(p.stop);R.DATOS.mkdir()
        self.f=R.DATOS/'vocabulario_privado.json';self.original=b'{\n  "jarveis": "jarvis"\n}\n';self.f.write_bytes(self.original)
    def crear(self):
        t=R.crear(lambda _:True);return t.split(': ')[-1]
    def test_roundtrip_hash_y_bytes_exactos(self):
        ident=self.crear();self.f.write_text('{"jarveis":"asistente"}')
        R.restaurar(ident,lambda _:True)
        self.assertEqual(self.f.read_bytes(),self.original);self.assertEqual(self.f.stat().st_mode&0o777,0o600)
        archivo=next((R.DATOS/'respaldos').glob('*.json'));self.assertEqual(archivo.stat().st_mode&0o777,0o600)
        self.assertEqual(hashlib.sha256(R._cargar(ident)[self.f.name]).hexdigest(),hashlib.sha256(self.original).hexdigest())
    def test_sin_permiso_no_copia_ni_restaura(self):
        R.crear(lambda _:False);self.assertFalse((R.DATOS/'respaldos').exists())
        ident=self.crear();self.f.write_text('{}');R.restaurar(ident,lambda _:False);self.assertEqual(self.f.read_text(),'{}')
    def test_excluye_archivos_y_directorios_privados_sin_leerlos(self):
        for n in ['zen.key','api_externa.json','originales_privados_r4','sesiones.json']:(R.DATOS/n).write_text('NO_COPIAR')
        ident=self.crear();self.assertEqual(set(R._cargar(ident)),{self.f.name})
        self.assertNotIn('NO_COPIAR',next((R.DATOS/'respaldos').glob('*.json')).read_text())
    def test_posibles_secretos_en_archivo_permitido_rechazan(self):
        (R.DATOS/'configuracion.json').write_text('{"api_key":"FICTICIO_NO_REAL"}')
        with self.assertRaises(ValueError):R.crear(lambda _:self.fail('No copiar credenciales'))
    def test_archivo_corrupto_no_se_sobrescribe(self):
        self.f.write_text('dañado')
        with self.assertRaises(ValueError):self.crear()
        self.assertEqual(self.f.read_text(),'dañado')
    def test_destino_cambiado_durante_permiso_no_se_toca(self):
        ident=self.crear();self.f.write_text('{}')
        def si(_):self.f.write_text('{"hola":"saludo"}');return True
        with self.assertRaises(ValueError):R.restaurar(ident,si)
        self.assertEqual(self.f.read_text(),'{"hola":"saludo"}')
    def test_hash_alterado_rechazado_antes_del_permiso(self):
        ident=self.crear();p=next((R.DATOS/'respaldos').glob('*.json'));d=json.loads(p.read_text());d['archivos'][self.f.name]['sha256']='0'*64;p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):R.restaurar(ident,lambda _:self.fail('Huella inválida'))
    def test_rutas_arbitrarias_en_manifiesto_rechazadas(self):
        ident=self.crear();p=next((R.DATOS/'respaldos').glob('*.json'));d=json.loads(p.read_text());d['archivos']['../fuera']=d['archivos'].pop(self.f.name);p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):R._cargar(ident)
    def test_enlaces_rechazados(self):
        self.f.unlink();real=self.raiz/'fuera';real.write_text('{}');self.f.symlink_to(real)
        with self.assertRaises(ValueError):self.crear()
        self.assertEqual(real.read_text(),'{}')
    def test_fallo_intermedio_revierte_propio_y_conserva_respaldo(self):
        (R.DATOS/'umbrales_temperatura.json').write_text('{"gpu":80,"cpu":90}')
        ident=self.crear();self.f.write_text('{}');(R.DATOS/'umbrales_temperatura.json').write_text('{"gpu":75,"cpu":90}')
        originales={p.name:p.read_bytes() for p in R.DATOS.glob('*.json')};real=R._escribir_bytes;contador=[]
        def falla(p,b):
            contador.append(p)
            if len(contador)==2:raise OSError('Fallo simulado')
            return real(p,b)
        with patch.object(R,'_escribir_bytes',side_effect=falla),self.assertRaisesRegex(R.ErrorRestauracion,'se revirtieron'):R.restaurar(ident,lambda _:True)
        self.assertEqual({p.name:p.read_bytes() for p in R.DATOS.glob('*.json')},originales)
    def test_restauracion_no_borra_archivos_extra(self):
        ident=self.crear();extra=R.DATOS/'otros.json';extra.write_text('conservar');R.restaurar(ident,lambda _:True);self.assertEqual(extra.read_text(),'conservar')
if __name__=='__main__':unittest.main()
