"""Procesos lectores sintéticos: límites, cancelación, referencias y privacidad."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import extraccion_aislada as E
import herramientas_lectura as L
import tandas_documentales as T


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=L.RAIZ)
        self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)

    def fuente(self,texto='Dato público confirmado.\n',nombre='fuente.txt',raw=None):
        p=self.base/nombre
        if raw is None:p.write_text(texto,encoding='utf-8')
        else:p.write_bytes(raw)
        return p,{'ruta':str(p),'nombre':p.name,'tipo':p.suffix.lower()}

    def extraer(self,item,**kw):return list(E.unidades(item,T.DEFAULT,**kw))

    def comando_lector_falso(self,cuerpo):
        # Código fijo del arnés, nunca un adjunto ni texto enviado por el usuario.
        codigo='import sys\nsys.path.insert(0,'+repr(str(Path(__file__).parent.resolve()))+')\nimport tandas_documentales as T\nimport extraccion_aislada as E\n'+cuerpo+'\nraise SystemExit(E._worker())\n'
        return [sys.executable,'-I','-B','-c',codigo]

    def test_texto_hash_y_original_intacto(self):
        p,item=self.fuente();antes=hashlib.sha256(p.read_bytes()).hexdigest();r=self.extraer(item)
        self.assertIn('confirmado',''.join(t for _,t in r));self.assertEqual(antes,item['sha256_aislado'])
        self.assertEqual(antes,hashlib.sha256(p.read_bytes()).hexdigest());self.assertFalse(item.get('aislado_incompleto'))

    def test_limite_as_y_rss_se_declaran_separados(self):
        _,item=self.fuente();self.extraer(item,recursos={'mb_proceso':128})
        self.assertEqual(item['aislamiento']['limite_as_mib'],128)
        self.assertGreater(item['aislamiento']['rss_max_kib'],0);self.assertIn('no RSS',item['aislamiento']['alcance'])

    def test_codigo_adjunto_no_se_ejecuta(self):
        marcador=self.base/'NO_DEBE_EXISTIR'
        _,item=self.fuente('from pathlib import Path\nPath('+repr(str(marcador))+').write_text("NO")\n',nombre='adjunto.py')
        r=self.extraer(item);self.assertTrue(r);self.assertFalse(marcador.exists())

    def test_utf16_y_rtl_literal(self):
        texto='Mañana יומן العربية confirmado\n'
        _,item=self.fuente(nombre='unicode.txt',raw=texto.encode('utf-16'))
        r=self.extraer(item);self.assertIn('יומן العربية',''.join(t for _,t in r));self.assertEqual(item['codificacion'],'utf-16')

    def test_redaccion_antes_de_fraccionar(self):
        _,item=self.fuente('dato\napi_key='+('secreto-ficticio'*2000)+'\nDATO_FINAL\n')
        r=self.extraer(item);texto=''.join(t for _,t in r)
        self.assertNotIn('secreto-ficticio',texto);self.assertIn('DATO_FINAL',texto)
        self.assertTrue(all(len(t.encode())<=E.MAX_TEXTO for _,t in r))

    def test_ipc_crudo_no_contiene_secretos(self):
        _,item=self.fuente('api_key=secreto-ficticio\nDato público\n')
        entrada=E._preparar(item,T.DEFAULT,E.validar_recursos())
        p=subprocess.run(E._comando_worker(),input=entrada,capture_output=True,timeout=5,env=dict(os.environ))
        self.assertEqual(p.returncode,0);self.assertNotIn(b'secreto-ficticio',p.stdout);self.assertNotIn(b'secreto-ficticio',p.stderr)

    def test_privada_cruza_unidades(self):
        _,item=self.fuente('-----BEGIN PRIVATE KEY-----\n'+('CUERPO_PRIVADO'*7000)+'\n-----END PRIVATE KEY-----\nDATO_FIN\n')
        texto=''.join(t for _,t in self.extraer(item))
        self.assertNotIn('CUERPO_PRIVADO',texto);self.assertIn('DATO_FIN',texto)

    def test_referencias_lineas_no_reinician_por_ipc(self):
        _,item=self.fuente(''.join(f'Linea {n:05d}\n' for n in range(1,4001)))
        r=self.extraer(item)
        for ref,texto in r:
            primera=texto.splitlines()[0]
            self.assertIn('desde línea '+str(int(primera.split()[1])),ref)

    def test_fragmento_linea_extensa_declara_columna(self):
        partes=list(E._trozos('x'*10000,'fuente.txt · desde línea 7'))
        self.assertIn('desde línea 7',partes[1][0]);self.assertIn('carácter 4097',partes[1][0])

    def test_fuera_de_alcance_no_crea_proceso(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'privado.txt';p.write_text('dato')
            item={'ruta':str(p),'nombre':p.name,'tipo':'.txt'}
            with patch.object(E.subprocess,'Popen') as iniciar:
                with self.assertRaises(L.FueraDeAlcance):self.extraer(item)
            iniciar.assert_not_called()

    def test_tamano_no_eleva_limite(self):
        p,item=self.fuente()
        with p.open('wb') as f:f.truncate(21*1024**2)
        with patch.object(E.subprocess,'Popen') as iniciar:
            with self.assertRaisesRegex(ValueError,'límite autorizado'):self.extraer(item)
        iniciar.assert_not_called()

    def test_hash_esperado_distinto_rechaza(self):
        _,item=self.fuente();item['hash']='f'*64
        with self.assertRaisesRegex(ValueError,'huella'):self.extraer(item)
        self.assertTrue(item['aislado_incompleto'])

    def test_binario_solo_metadatos(self):
        _,item=self.fuente(nombre='binario.exe',raw=b'\0\1\2contenido')
        self.assertEqual(self.extraer(item),[]);self.assertEqual(item['soporte'],'NO SOPORTADO')
        self.assertEqual(len(item['sha256_aislado']),64)

    def test_vacio_finaliza_con_hash(self):
        _,item=self.fuente('');self.assertEqual(self.extraer(item),[]);self.assertIn('sha256_aislado',item)

    def test_docx_y_unidad_grande(self):
        p=self.base/'texto.docx'
        with zipfile.ZipFile(p,'w') as z:z.writestr('word/document.xml','<document><p><t>'+('DATO '*3000)+' api_key=secreto-ficticio</t></p></document>')
        item={'ruta':str(p),'nombre':p.name,'tipo':'.docx'};r=self.extraer(item)
        self.assertGreater(len(r),1);self.assertTrue(all('párrafo 1' in ref for ref,_ in r))
        self.assertNotIn('secreto-ficticio',''.join(t for _,t in r))

    def test_zip_miembro_seguro_no_extrae(self):
        p=self.base/'fuentes.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('carpeta/dato.txt','DATO_ZIP\napi_key=secreto-ficticio')
        item={'ruta':str(p),'nombre':'fuentes.zip!carpeta/dato.txt','tipo':'.txt','miembro':'carpeta/dato.txt'}
        r=self.extraer(item);self.assertIn('DATO_ZIP',''.join(t for _,t in r));self.assertFalse((self.base/'carpeta').exists())
        self.assertNotIn('secreto-ficticio',''.join(t for _,t in r))

    def test_zip_traversal_rechazado(self):
        p=self.base/'traversal.zip'
        with zipfile.ZipFile(p,'w') as z:z.writestr('../fuera.txt','dato')
        item={'ruta':str(p),'nombre':'../fuera.txt','tipo':'.txt','miembro':'../fuera.txt'}
        with self.assertRaises(ValueError):self.extraer(item)
        self.assertFalse((self.base.parent/'fuera.txt').exists())

    def test_memoryerror_es_del_worker_y_padre_sigue(self):
        _,item=self.fuente()
        codigo='def lectura(*a,**k):\n x=bytearray(256*1024**2)\n yield "no","no"\nT._unidades=lectura'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            with self.assertRaisesRegex(MemoryError,'memoria virtual'):self.extraer(item,recursos={'mb_proceso':128})
        _,otra=self.fuente('DATO_POSTERIOR',nombre='despues.txt');self.assertIn('DATO_POSTERIOR',''.join(t for _,t in self.extraer(otra)))

    def test_timeout_no_depende_control_cooperativo_del_parser(self):
        _,item=self.fuente()
        codigo='import time\ndef lectura(*a,**k):\n while True: time.sleep(1)\n yield "no","no"\nT._unidades=lectura'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            with self.assertRaises(TimeoutError):self.extraer(item,recursos={'segundos_archivo':.15})
        self.assertTrue(item['aislado_incompleto'])

    def test_cancelacion_padre_termina_parser_no_cooperativo(self):
        _,item=self.fuente();veces=[0]
        codigo='import time\ndef lectura(*a,**k):\n while True: time.sleep(1)\n yield "no","no"\nT._unidades=lectura'
        def control():
            veces[0]+=1
            if veces[0]>5:raise InterruptedError('cancelación sintética')
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            with self.assertRaises(InterruptedError):self.extraer(item,control=control)
        self.assertTrue(item['cortado'])

    def test_cerrar_generador_termina_descendiente_propio(self):
        _,item=self.fuente()
        codigo='import subprocess,time\ndef lectura(*a,**k):\n p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(60)"])\n yield "hijo",str(p.pid)\n while True: time.sleep(1)\nT._unidades=lectura'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            generador=E.unidades(item,T.DEFAULT);_,pid=next(generador);pid=int(pid);generador.close()
        estado=Path('/proc')/str(pid)/'stat'
        try:estado_hijo=estado.read_text().split()[2]
        # El proceso puede desaparecer después de abrir /proc/<pid>/stat:
        # Linux informa ESRCH en esa carrera; también acredita su cierre.
        except (FileNotFoundError, ProcessLookupError):estado_hijo=None
        self.assertIn(estado_hijo,(None,'Z'))
        self.assertTrue(item['aislado_incompleto'])

    def test_hijo_hereda_rlimit_as(self):
        _,item=self.fuente()
        codigo='import subprocess\ndef lectura(*a,**k):\n r=subprocess.run([sys.executable,"-c","import resource; print(resource.getrlimit(resource.RLIMIT_AS)[0])"],capture_output=True,text=True,check=True)\n yield "limite",r.stdout.strip()\nT._unidades=lectura'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            r=self.extraer(item,recursos={'mb_proceso':128})
        self.assertEqual(int(r[0][1]),128*1024**2)

    def test_fuente_cambia_en_parser_no_se_declara_completa(self):
        _,item=self.fuente()
        codigo='from pathlib import Path\ndef lectura(item,*a,**k):\n Path(item["ruta"]).write_text("modificado por arnés sintético")\n yield "fuente","muestra"\nT._unidades=lectura'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            with self.assertRaisesRegex(ValueError,'cambió durante'):self.extraer(item)
        self.assertTrue(item['cortado'])

    def test_protocolo_roto_no_parece_exito(self):
        _,item=self.fuente();codigo='import sys; sys.stdin.buffer.readline(); print("NO_ES_JSON")'
        with patch.object(E,'_comando_worker',return_value=[sys.executable,'-I','-c',codigo]):
            with self.assertRaisesRegex(ValueError,'protocolo inválido'):self.extraer(item)

    def test_salida_sin_nueva_linea_acotada(self):
        _,item=self.fuente();codigo='import sys; sys.stdin.buffer.readline(); sys.stdout.write("x"*140000); sys.stdout.flush()'
        with patch.object(E,'_comando_worker',return_value=[sys.executable,'-I','-c',codigo]):
            with self.assertRaisesRegex(ValueError,'límite de su salida'):self.extraer(item)

    def test_metadatos_secretos_redactados_en_worker(self):
        _,item=self.fuente()
        codigo='def lectura(item,*a,**k):\n item["media"]={"token":"secreto-ficticio", "codec":"texto"}\n yield "fuente","dato"\nT._unidades=lectura'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):self.extraer(item)
        self.assertEqual(item['media']['token'],'[REDACTADO]');self.assertNotIn('secreto-ficticio',json.dumps(item))

    def test_control_antes_de_iniciar_worker(self):
        _,item=self.fuente()
        def control():raise InterruptedError('cancelado antes')
        with patch.object(E.subprocess,'Popen') as iniciar:
            with self.assertRaises(InterruptedError):self.extraer(item,control=control)
        iniciar.assert_not_called()

    def test_metadatos_no_pueden_cambiar_ruta(self):
        item={};linea=json.dumps({'protocolo':E.PROTOCOLO,'tipo':'fin','metadatos':{'ruta':'otra'}}).encode()
        with self.assertRaisesRegex(ValueError,'Metadatos finales'):E._recibir(linea,item)
        self.assertEqual(item,{})

    def test_recursos_invalidos(self):
        for r in ({'mb_proceso':True},{'mb_proceso':63},{'mb_proceso':1025},{'mb_buffer':0},{'segundos_archivo':float('nan')},{'ignorado':1}):
            with self.subTest(r=r),self.assertRaises(ValueError):E.validar_recursos(r)

    def test_unidad_ipc_excesiva_rechazada(self):
        linea=json.dumps({'protocolo':E.PROTOCOLO,'tipo':'unidad','referencia':'dato','texto':'x'*(E.MAX_TEXTO+1)}).encode()
        with self.assertRaisesRegex(ValueError,'unidad'):E._recibir(linea,{})

    def test_entorno_no_hereda_claves_ni_sesion_desktop(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secreto-ficticio','GEMINI_API_KEY':'otro-secreto','DBUS_SESSION_BUS_ADDRESS':'bus-ficticio','PYTHONPATH':'/ruta/no-autorizada'}):
            entorno=E._entorno_worker()
        self.assertEqual(set(entorno),{'PATH','LANG','LC_ALL','JARVIS_DIR','JARVIS_PRUEBAS'})
        self.assertNotIn('secreto-ficticio',json.dumps(entorno));self.assertNotIn('/ruta/no-autorizada',json.dumps(entorno))

    def test_worker_efectivamente_recibe_entorno_minimo(self):
        _,item=self.fuente()
        codigo='import os,json\ndef lectura(*a,**k):\n yield "entorno",json.dumps(sorted(os.environ))\nT._unidades=lectura'
        with patch.dict(os.environ,{'CLAVE_PRIVADA_FICTICIA':'secreto-ficticio'}),patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):
            r=self.extraer(item)
        self.assertNotIn('CLAVE_PRIVADA_FICTICIA',r[0][1]);self.assertNotIn('HOME',r[0][1])

    def test_pdf_selector_solo_pagina_solicitada(self):
        _,item=self.fuente(nombre='muchas.pdf',raw=b'%PDF-1.4\nPDF sintetico del arnes\n');item['_pagina_documento']=301
        codigo='import documentos_jarvis as D\ndef pdf(p,inicio):\n if inicio!=301:raise ValueError("Se intento una pagina anterior")\n return "DATO_PAGINA301 api_key=secreto-ficticio",400,False\nD._pdf=pdf'
        with patch.object(E,'_comando_worker',return_value=self.comando_lector_falso(codigo)):r=self.extraer(item)
        self.assertIn('DATO_PAGINA301',''.join(t for _,t in r));self.assertNotIn('secreto-ficticio',''.join(t for _,t in r))
        self.assertEqual(item['paginas'],400);self.assertEqual(item['paginas_leidas'],301);self.assertEqual(item['paginas_extraidas'],1)
        self.assertTrue(all('página 301' in ref for ref,_ in r))

    def test_selector_no_aplica_a_no_pdf(self):
        _,item=self.fuente();item['_pagina_documento']=2
        with self.assertRaisesRegex(ValueError,'PDF real'):self.extraer(item)

    def test_selector_invalido_no_inicia_worker(self):
        _,item=self.fuente()
        for pagina in (True,0,-1,1_000_001,'301'):
            with self.subTest(pagina=pagina),patch.object(E.subprocess,'Popen') as iniciar:
                with self.assertRaises(ValueError):self.extraer(dict(item,_pagina_documento=pagina))
                iniciar.assert_not_called()

    def test_fin_sin_huella_se_rechaza(self):
        linea=json.dumps({'protocolo':E.PROTOCOLO,'tipo':'fin','metadatos':{}}).encode()
        with self.assertRaisesRegex(ValueError,'huella final'):E._recibir(linea,{})

    def test_fin_con_firma_distinta_se_rechaza(self):
        meta={'sha256_aislado':'a'*64,'aislamiento':{'limite_as_mib':128,'rss_max_kib':1}}
        fin={'protocolo':E.PROTOCOLO,'tipo':'fin','metadatos':meta,'fuente':{'firma':[1,2,3],'sha256':'a'*64}}
        esperado={'firma':[1,2,4],'mb_proceso':128}
        with self.assertRaisesRegex(ValueError,'no corresponde'):E._recibir(json.dumps(fin).encode(),{},esperado)

    def test_fin_no_puede_aumentar_techo_de_memoria(self):
        meta={'sha256_aislado':'a'*64,'aislamiento':{'limite_as_mib':256,'rss_max_kib':1}}
        fin={'protocolo':E.PROTOCOLO,'tipo':'fin','metadatos':meta,'fuente':{'firma':[1,2,3],'sha256':'a'*64}}
        esperado={'firma':[1,2,3],'mb_proceso':128}
        with self.assertRaisesRegex(ValueError,'no corresponde'):E._recibir(json.dumps(fin).encode(),{},esperado)


if __name__=='__main__':unittest.main()
