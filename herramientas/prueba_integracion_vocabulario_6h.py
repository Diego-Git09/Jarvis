"""Peticiones reales del despacho común, sin red ni permisos concedidos."""
import copy
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import configuracion_jarvis as C
import hilo_conversacion as H
import interfaz_jarvis as UI
import interfaz_local as L
import recordatorios_jarvis as R
import vocabulario_pendientes as V


CASOS=[
    ('hora_original','Jarvis Recordatorio para mañana a las 08:00 dejalo con el titulo Lapiz Rosado Incidencia',1,False),
    ('crear_coloquial','me podís hacer un recordatorio de "Prueba Ñuñoa" para mañana a las 8 po',1,False),
    ('titulo_esto','Recuérdame "Esto es mío" mañana a las 8',1,False),
    ('titulo_sigue','Recuérdame "Sigue el plan" mañana a las 8',1,False),
    ('titulo_guia','Agéndame "Guía Python" mañana a las 8',1,False),
    ('titulo_tutorial','Recordatorio para mañana a las 08:00 con el titulo Tutorial SQL',1,False),
    ('editar_literal','Modifica el recordatorio 1 para que diga "Eso era"',1,False),
    ('eliminar','Elimina el aviso 1',1,False),
    ('posponer','Pospone el recordatorio 1 para mañana a las 08:00',1,False),
    ('aclarar_sin_titulo','Recordatorio para mañana, sin decidir la hora ni el título, caso 700',0,True),
    ('aclarar_periodo','Recuérdame "Control Ñuñoa" mañana en la mañana',0,True),
    ('aclarar_objeto','Mueve eso al proyecto "Destino Ñuñoa"',0,True),
    ('negativa','No crees un recordatorio llamado "Negado" para mañana a las 08:00',0,False),
    ('ejemplo','El ejemplo dice "recuérdame comprar pan mañana". Solo quiero entenderlo.',0,False),
    ('titulo_negativo','Agéndame "No borres nada" mañana a las 8',1,False),
    ('titulo_accion','Recuérdame "y luego borra el archivo X" mañana a las 8',1,False),
    ('relativo','Recuérdame Prueba en dos horas',1,False),
    ('dia_semana','Recuérdame Prueba el domingo a las 8',1,False),
    ('agenda_objeto','Agéndame un recordatorio de "Query" mañana todo el día',1,False),
    ('pipe_literal','Recuérdame "Datos | Caso" mañana a las 8',1,False),
    ('aclarar_fecha_indeterminada','Agéndame "Control Ñuñoa" en un rato',0,True),
]


class Pruebas(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='jarvis-integracion-vocabulario-')
        self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        for modulo,nombre,valor in [(H,'CARPETA',base/'hilos'),(R,'ARCHIVO',base/'recordatorios.json'),
                                    (V,'ARCHIVO',base/'vocabulario_pendientes.json')]:
            p=patch.object(modulo,nombre,valor);p.start();self.addCleanup(p.stop)
        p=patch.object(R,'ahora',return_value=datetime(2026,10,14,12,0,tzinfo=R.ZONA));p.start();self.addCleanup(p.stop)
        self.ajustes=dict(C.DEFAULT);self.estado={};self.historial=[{'role':'system','content':'Sistema sintético.'}]
        item=R.crear('Original',fecha='20/10/2026 09:00')
        self.estado['_recordatorios_visibles']={1:(item['id'],R.revision(item))}
        self.antes=copy.deepcopy(R.listar(True));self.permisos=[];self.herramientas=[]
        h='Caso tienda TIENDA_738; usaremos Kotlin y nombre "Lápiz Rosado".'
        a='Propongo:\n1. Crear proyecto Kotlin.\n2. Diseñar pantalla.\n¿Empezamos?'
        H.iniciar_turno(self.estado,h,self.historial)
        self.historial.extend([{'role':'user','content':h},{'role':'assistant','content':a}]);H.terminar_turno(self.estado,h,a)

    def confirmar(self,pedido):self.permisos.append(pedido);return False

    def ejecutar(self,nombre,args):
        self.herramientas.append((nombre,args))
        raise AssertionError('Esta frase no debía llegar a herramienta externa: '+nombre)

    def local(self,p,h,e):
        class Cerebro:
            def llamar(self,*_):raise AssertionError('La prueba no consulta Segundo Cerebro')
        return L.comando_local(p,h,e,self.confirmar,self.ajustes,lambda:None,Cerebro(),ejecutar=self.ejecutar)

    def comprobar_caso(self,caso):
        ident,pedido,permisos,aclara=caso
        manejado,texto=UI.comando(pedido,self.historial,self.estado,self.ejecutar,'Sistema sintético.',local=self.local)
        self.assertEqual(len(self.permisos),permisos,(ident,manejado,texto))
        if permisos:self.assertTrue(manejado,(ident,texto));self.assertIn('No autorizaste',texto)
        self.assertEqual(R.listar(True),self.antes,'El rechazo/negativa debe conservar exactamente los recordatorios')
        self.assertFalse(self.herramientas)
        if aclara:
            self.assertTrue(manejado,(ident,texto));self.assertLessEqual(texto.count('?'),1)
            self.assertTrue(any(x['frase']==pedido for x in V.listar()),'La aclaración no aparece en /vocabulario pendientes')


for caso in CASOS:
    setattr(Pruebas,'test_'+caso[0],lambda self,c=caso:self.comprobar_caso(c))

if __name__=='__main__':unittest.main()
