import json,tempfile,unittest
from pathlib import Path
import estado_ia_r5_texto as R
class Pruebas(unittest.TestCase):
    def test_cifras_no_copian_transcripciones_ni_conteos_imposibles(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);f=p/'resumen_mediciones.json'
            f.write_text(json.dumps({'bancos':{'real52_final':{'casos':52,'revision_codex':{'bien':48,'parcial':3,'mal':1},'respuesta':'NO_COPIAR'}}}))
            t=R.cifras(p);self.assertIn('48 bien/3 parcial/1 mal',t);self.assertNotIn('NO_COPIAR',t);self.assertIn('pendiente',t)
            for n in ('NO_COPIAR',True,70):
                f.write_text(json.dumps({'bancos':{'real52_final':{'casos':52,'revision_codex':{'bien':n,'parcial':3,'mal':1}}}}))
                t=R.cifras(p);self.assertNotIn('NO_COPIAR',t);self.assertIn('sin resumen final',t)
    def test_simulacion_no_se_presenta_como_calidad_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'resumen_mediciones.json').write_text(json.dumps({'bancos':{'simulado52':{'casos':52,'correctos':52}}}))
            t=R.cifras(p);self.assertIn('Simulación',t);self.assertIn('no evalúa calidad',t)
if __name__=='__main__':unittest.main()
