import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import revision_humana as R
import limpieza_r4 as L
import administracion_local as A

class Cliente:
    def __init__(self):self.d={i:{'id':i,'proyecto':'CHAT JARVIS','contenido':'Conexión token=FICTICIO_PARA_PRUEBAS'} for i in (1009,1010,1011)};self.cambios=[]
    def llamar(self,n,args):
        i=args['id_memoria']
        if n=='consultar_memoria':return {'memorias':[dict(self.d[i])]}
        assert n=='corregir_memoria';assert self.d[i]['contenido']==args['contenido_esperado']
        self.cambios.append(i);self.d[i]['contenido']=args['contenido_nuevo'];return {'ok':True}

class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
        for mod,nombre,valor in [(R,'ARCHIVO',self.p/'datos/revision.json'),(R,'DATOS',self.p/'datos'),(R,'ORIGEN',self.p/'fuentes'),(L,'DATOS',self.p/'datos'),(L,'PROPUESTAS',self.p/'propuestas')]:
            q=patch.object(mod,nombre,valor);q.start();self.addCleanup(q.stop)
        R.ORIGEN.mkdir();L.PROPUESTAS.mkdir()
        filas=[{'id':i,'pregunta':'pregunta sintética '+str(i),'respuesta_original_jarvis':'respuesta original '+str(i)} for i in [1,18,40]]
        (R.ORIGEN/'seleccion_40_r8.jsonl').write_text('\n'.join(map(json.dumps,filas)))
        (R.ORIGEN/'piloto_adicional').mkdir()
        for r in ['r3','r4']:(R.ORIGEN/f'piloto_adicional/piloto_{r}.jsonl').write_text(json.dumps(filas[0]))
    def test_muestra_original_y_no_inventa_marcas_humanas(self):
        e={};hecho,t=R.comando('/revisar_respuestas',e,lambda _:self.fail('No guardar al leer'))
        self.assertTrue(hecho);self.assertIn('respuesta original 1',t);self.assertFalse(R.ARCHIVO.exists());self.assertIn('0/3',R.resumen())
    def test_marca_necesita_permiso_y_persiste_separada_de_codex(self):
        e={};R.comando('/revisar_respuestas',e,lambda _:False)
        R.comando('parcial falta un ejemplo',e,lambda _:False);self.assertFalse(R.ARCHIVO.exists())
        R.comando('bien se entiende',e,lambda _:True)
        d=R.leer()['marcas'];self.assertEqual(next(iter(d.values()))['autor'],'usuario');self.assertEqual(R.ARCHIVO.stat().st_mode&0o777,0o600)
        self.assertIn('bien 1',R.resumen());self.assertIn('separada',R.resumen())
    def test_comentario_sensible_redactado(self):
        e={};R.comando('/revisar_respuestas',e,lambda _:False);R.comando('mal token=FICTICIO_PARA_PRUEBA',e,lambda _:True)
        self.assertNotIn('FICTICIO_PARA_PRUEBA',R.ARCHIVO.read_text())
    def test_fuente_modificada_no_reutiliza_calificacion(self):
        e={};R.comando('/revisar_respuestas',e,lambda _:False);R.comando('bien',e,lambda _:True)
        p=R.ORIGEN/'seleccion_40_r8.jsonl';p.write_text(p.read_text().replace('respuesta original 1','respuesta modificada'))
        self.assertIn('0/3',R.resumen())
    def test_pausar_y_navegar_no_escribe(self):
        e={};R.comando('/revisar_respuestas',e,lambda _:False);R.comando('siguiente',e,lambda _:False)
        self.assertEqual(e['_revision_respuestas']['pos'],1);R.comando('/revisar_respuestas salir',e,lambda _:False)
        self.assertFalse(e);self.assertFalse(R.ARCHIVO.exists())
    def test_parciales_no_se_suman_a_las_cuarenta(self):
        self.assertEqual(len(R.cargar('parciales')),3);self.assertEqual(len(R.cargar('ronda3')),3)
    def test_administracion_solo_califica_si_hay_una_revision_pendiente(self):
        self.assertFalse(A.es_entrada('bien',{}));self.assertTrue(A.es_entrada('bien',{'_revision_respuestas':{}}) is False)
        self.assertTrue(A.es_entrada('mal faltan pasos',{'_revision_respuestas':{'tanda':'ronda3'}}))
    def preparar_hilos(self):
        p=L.DATOS/'hilos';p.mkdir(parents=True)
        ident='a'*32;f=p/(ident+'.json');f.write_text(json.dumps({'id':ident,'objetivo':'sintético'}))
        (p/'ultimo.json').write_text(json.dumps({'id':ident}))
        (L.PROPUESTAS/'propuesta_hilos.json').write_text(json.dumps({'candidatos':[{'id_local':ident,'elegible':True,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}]}))
        return f
    def test_limpieza_sin_si_no_copia_ni_aparta(self):
        f=self.preparar_hilos();r=L.apartar_hilos(lambda _:False);self.assertFalse(r['ok']);self.assertTrue(f.exists());self.assertFalse((L.DATOS/'limpieza_r4').exists())
    def test_limpieza_respalda_y_comprueba_antes_de_apartar(self):
        f=self.preparar_hilos();bruto=f.read_bytes();r=L.apartar_hilos(lambda _:True)
        self.assertTrue(r['ok']);self.assertFalse(f.exists());b=Path(r['respaldo'])/f.name
        self.assertEqual(b.read_bytes(),bruto);self.assertEqual(b.stat().st_mode&0o777,0o600);self.assertTrue(r['puntero_retirado'])
    def test_hilo_cambiado_se_detiene_antes_del_permiso(self):
        f=self.preparar_hilos();f.write_text('modificado')
        with self.assertRaises(ValueError):L.apartar_hilos(lambda _:self.fail('Propuesta vencida'))
        self.assertTrue(f.exists())
    def preparar_recuerdos(self,c):
        from conversaciones_jarvis import _redactar
        filas=[{'id':i,'proyecto':'CHAT JARVIS','sha256_esperado':hashlib.sha256(c.d[i]['contenido'].encode()).hexdigest(),'contenido_propuesto':_redactar(c.d[i]['contenido'])} for i in c.d]
        (L.PROPUESTAS/'propuestas_redaccion_recuerdos.json').write_text(json.dumps({'propuestas':filas}))
    def test_recuerdos_sin_permiso_no_se_cambian(self):
        c=Cliente();self.preparar_recuerdos(c);r=L.redactar_recuerdos(c,lambda _:False)
        self.assertFalse(r['ok']);self.assertEqual(c.cambios,[])
    def test_recuerdos_con_cas_y_lectura_posterior_sin_copia_por_defecto(self):
        c=Cliente();self.preparar_recuerdos(c);r=L.redactar_recuerdos(c,lambda _:True)
        self.assertEqual(c.cambios,[1009,1010,1011]);self.assertTrue(r['ok']);self.assertIsNone(r['copia_original'])
    def test_copia_original_solo_cuando_se_pide(self):
        c=Cliente();self.preparar_recuerdos(c);r=L.redactar_recuerdos(c,lambda _:True,copia_original=True)
        self.assertEqual((Path(r['copia_original'])/'1009.txt').stat().st_mode&0o777,0o600)
    def test_recuerdo_cambiado_no_se_toca(self):
        c=Cliente();self.preparar_recuerdos(c);c.d[1009]['contenido']='otro contenido'
        with self.assertRaises(ValueError):L.redactar_recuerdos(c,lambda _:self.fail('No pedir autorización de propuesta vencida'))
        self.assertEqual(c.cambios,[])

if __name__=='__main__':unittest.main()
