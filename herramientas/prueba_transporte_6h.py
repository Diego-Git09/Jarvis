"""Contratos de reintentos y cola: servidor falso y reloj acotado."""
import threading
import unittest
from unittest.mock import patch
import cliente_ollama as O
from evaluar_transporte_6h import CASOS,evaluar

class Pruebas(unittest.TestCase):
    def test_cola_tiene_plazo_y_no_lanza_peticion(self):
        activo=threading.Event();fin=threading.Event()
        def bloquear():
            with O._TURNO:activo.set();fin.wait(2)
        h=threading.Thread(target=bloquear);h.start();activo.wait(1)
        try:
            with patch.object(O,'ABRIR') as abrir,self.assertRaises(O.ErrorOllama) as e:O.solicitar('/api/chat',{},timeout=.02)
            self.assertEqual(e.exception.tipo,'cola');abrir.assert_not_called()
        finally:fin.set();h.join()

for caso in CASOS:
    def test(self,modo=caso['modo']):self.assertTrue(evaluar(O,modo)['ok'],modo)
    setattr(Pruebas,'test_'+caso['id'],test)

if __name__=='__main__':unittest.main()
