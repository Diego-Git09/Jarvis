"""Comprueba verificación, confirmación y destino del movimiento desde el explorador."""
import sys
import unittest
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clasificacion_interfaz import mover, mover_varios


class ClienteFalso:
    def __init__(self, cambio=False):
        self.registros={17:{'id':17,'titulo':'Idea de Jarvis','contenido':'Organizar recuerdos pendientes.',
                            'proyecto':'sin_clasificar','tipo':'recuerdo'},
                        18:{'id':18,'titulo':'Mejorar vocabulario','contenido':'Agregar sinónimos chilenos.',
                            'proyecto':'sin_clasificar','tipo':'recuerdo'}}
        self.cambio=cambio
        self.llamadas=[]

    def llamar(self, nombre, argumentos):
        self.llamadas.append((nombre,dict(argumentos)))
        if nombre == 'consultar_memoria':
            registro=dict(self.registros[argumentos['id_memoria']])
            if self.cambio: registro['contenido']='Texto actualizado por otra aplicación.'
            return {'ok':True,'memorias':[registro]}
        if nombre == 'listar_proyectos':
            return {'ok':True,'proyectos':[{'proyecto':'sin_clasificar'},{'proyecto':'Jarvis'}]}
        if nombre == 'crear_proyecto':
            return {'ok':True,'proyecto':argumentos['proyecto']}
        if nombre == 'clasificar_memoria':
            return {'ok':True,'estado':'clasificada','proyecto':argumentos['proyecto']}
        raise AssertionError(nombre)


class PruebasClasificacionInterfaz(unittest.TestCase):
    def registro(self):
        return {'id':17,'titulo':'Idea de Jarvis','contenido':'Organizar recuerdos pendientes.',
                'proyecto':'sin_clasificar','tipo':'recuerdo'}

    def test_mover_verifica_y_pide_permiso_antes_de_clasificar(self):
        cliente=ClienteFalso(); permisos=[]
        resultado=mover(cliente,self.registro(),'Jarvis',lambda texto:permisos.append(texto) or True)
        self.assertTrue(resultado['ok'])
        self.assertEqual(resultado['proyecto'],'Jarvis')
        self.assertIn('consultar_memoria',[n for n,_ in cliente.llamadas])
        self.assertIn('clasificar_memoria',[n for n,_ in cliente.llamadas])
        self.assertEqual(len(permisos),1)
        self.assertIn('sin_clasificar',permisos[0]); self.assertIn('Jarvis',permisos[0])

    def test_recuerdo_cambiado_no_se_mueve(self):
        cliente=ClienteFalso(cambio=True); permisos=[]
        resultado=mover(cliente,self.registro(),'Jarvis',lambda texto:permisos.append(texto) or True)
        self.assertFalse(resultado['ok'])
        self.assertEqual(permisos,[])
        self.assertNotIn('clasificar_memoria',[n for n,_ in cliente.llamadas])

    def test_destino_nuevo_se_crea_y_mueve_con_una_confirmacion(self):
        cliente=ClienteFalso(); permisos=[]
        resultado=mover(cliente,self.registro(),'Proyecto nuevo',lambda texto:permisos.append(texto) or True)
        self.assertTrue(resultado['ok'])
        self.assertEqual([n for n,_ in cliente.llamadas].count('crear_proyecto'),1)
        self.assertEqual([n for n,_ in cliente.llamadas].count('clasificar_memoria'),1)
        self.assertEqual(len(permisos),1)
        self.assertIn('se creará el proyecto',permisos[0])

    def test_denegar_no_crea_ni_mueve(self):
        cliente=ClienteFalso()
        resultado=mover(cliente,self.registro(),'Proyecto nuevo',lambda _texto:False)
        self.assertFalse(resultado['ok'])
        self.assertNotIn('crear_proyecto',[n for n,_ in cliente.llamadas])
        self.assertNotIn('clasificar_memoria',[n for n,_ in cliente.llamadas])

    def test_conversacion_seleccionada_puede_moverse_igual(self):
        cliente=ClienteFalso(); registro=self.registro(); registro['tipo']='conversacion'
        resultado=mover(cliente,registro,'Jarvis',lambda _texto:True)
        self.assertTrue(resultado['ok'])

    def test_seleccion_multiple_se_mueve_con_una_sola_confirmacion(self):
        cliente=ClienteFalso(); permisos=[]
        segundo=dict(cliente.registros[18])
        resultado=mover_varios(cliente,[self.registro(),segundo],'Jarvis',lambda texto:permisos.append(texto) or True)
        self.assertTrue(resultado['ok'])
        self.assertEqual(resultado['cantidad'],2)
        self.assertEqual(len(permisos),1)
        self.assertEqual([n for n,_ in cliente.llamadas].count('clasificar_memoria'),2)
        self.assertIn('Mover 2 registro(s)',permisos[0])

    def test_texto_recortado_se_verifica_por_huella_y_mueve_completo(self):
        cliente=ClienteFalso();contenido='A'*2000
        cliente.registros[17]['contenido']=contenido
        visto=dict(cliente.registros[17],contenido=contenido[:1600],recortado=True,
                   contenido_sha256=hashlib.sha256(contenido.encode()).hexdigest())
        r=mover(cliente,visto,'Jarvis',lambda _:True)
        self.assertTrue(r['ok'])
        escrita=next(a for n,a in cliente.llamadas if n=='clasificar_memoria')
        self.assertEqual(escrita['contenido_esperado'],contenido)

    def test_cambio_fuera_del_fragmento_visible_no_pasa_verificacion(self):
        cliente=ClienteFalso();contenido='A'*2000
        cliente.registros[17]['contenido']=contenido[:-1]+'B'
        visto=dict(cliente.registros[17],contenido=contenido[:1600],recortado=True,
                   contenido_sha256=hashlib.sha256(contenido.encode()).hexdigest())
        r=mover(cliente,visto,'Jarvis',lambda _:self.fail('No debe pedir permiso'))
        self.assertFalse(r['ok']);self.assertNotIn('clasificar_memoria',[n for n,_ in cliente.llamadas])


if __name__ == '__main__':
    unittest.main()
