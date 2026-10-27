"""Clima actual, fechas y ausencia de invenciones ante errores de la fuente."""
import unittest
from unittest.mock import patch
import clima_jarvis as C
from interfaz_local import comando_local
import configuracion_jarvis as CONFIG


class Pruebas(unittest.TestCase):
    def test_pregunta_natural_del_usuario_y_manana(self):
        self.assertEqual(C.interpretar_clima('puedes verificar el clima en santiago?'),{'lugar':'santiago','periodo':'hoy'})
        self.assertEqual(C.interpretar_clima('¿Va a llover mañana en Santiago?')['periodo'],'manana')
        self.assertIsNone(C.interpretar_clima('El clima del proyecto es complicado'))
        self.assertIsNone(C.interpretar_clima('No consultes el clima en Santiago'))
        self.assertIsNone(C.interpretar_clima('Clima en Santiago y luego edita un archivo'))

    def test_clima_no_necesita_que_responda_ollama(self):
        with patch.object(C,'consultar_clima',return_value={'ok':False,'error':'sin Internet'}) as fuente:
            hecho,texto=comando_local('Puedes verificar el clima en Santiago?',[],{},lambda _:False,CONFIG.DEFAULT,lambda:None,None)
        self.assertTrue(hecho);fuente.assert_called_once();self.assertIn('No inventaré',texto)

    def test_datos_reales_de_fuente_se_presentan_con_sus_horas(self):
        geo={'results':[{'name':'Santiago','country':'Chile','country_code':'CL','latitude':-33.45,'longitude':-70.65,'population':100}]}
        tiempo={'timezone':'America/Santiago','current':{'time':'2026-10-13T09:00','temperature_2m':15,'apparent_temperature':14,'relative_humidity_2m':60,'weather_code':3,'wind_speed_10m':10},
                'daily':{'time':['2026-10-13','2026-10-14'],'temperature_2m_min':[8,9],'temperature_2m_max':[20,22],'precipitation_probability_max':[10,30],'weather_code':[3,2]}}
        with patch.object(C,'_json',side_effect=[geo,tiempo]) as fuente:r=C.consultar_clima('Santiago','manana')
        self.assertTrue(r['ok']);self.assertIn('countryCode=CL',fuente.call_args_list[0].args[0]);self.assertEqual(r['dias'][0]['fecha'],'2026-10-14')
        self.assertIn('15 °C',C.presentar(r));self.assertIn('estimaciones',C.presentar(r));self.assertIn('09:00',C.presentar(r))

    def test_lugar_ambiguo_y_nan_no_generan_datos_falsos(self):
        with patch.object(C,'_json',return_value={'results':[{'name':'Paris','country_code':'FR','country':'Francia'},{'name':'Paris','country_code':'US','country':'EEUU'}]}):r=C.consultar_clima('Paris')
        self.assertFalse(r['ok']);self.assertIn('varios',r['error'])
        with self.assertRaises(ValueError):C._numero(float('nan'))
        with self.assertRaises(ValueError):C._numero(None)


if __name__=='__main__':unittest.main()
