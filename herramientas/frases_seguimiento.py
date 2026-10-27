"""Variantes para clasificar referencias; jamás reescribe el texto ni argumentos."""
import re


def normalizar_referencia(texto):
    cambios={'aserlo':'hacerlo','acerlo':'hacerlo','haserlo':'hacerlo','aseme':'haceme','asme':'hazme',
             'hacemee':'haceme','unna':'una','guya':'guia','guioa':'guia','desmenuzalo':'desglosalo'}
    n=re.sub(r'\b(?:'+ '|'.join(cambios)+r')\b',lambda m:cambios[m[0]],texto)
    n=re.sub(r'\blo mismo\b','lo anterior',n)
    if re.fullmatch(r'(?:me )?lo baj(?:ai|as|a) a tierra(?: po| porfa)?[ .!?]*',n):return 'explicame esto paso a paso'
    if re.fullmatch(r'(?:ya )?(?:a )?lo anterior pero pasito a pasito(?: po)?[ .!?]*',n):return 'paso a paso de lo anterior'
    return n
