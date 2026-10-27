"""Corpus documental sintético congelado; recuperación/citas, nunca conversación real."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import time
import zipfile

CORPUS=Path(__file__).with_name('corpus_adjuntos_6h.json')
EXTS='txt md rst log csv tsv json jsonl yaml toml ini xml html rtf tex srt vtt ipynb sql py java kt kts gradle js ts jsx tsx c cpp h cs go rs php rb sh bat ps1 properties env docx xlsx xlsm pptx odt ods odp epub eml mbox vcf ics db sqlite zip tar tgz gz'.split()

def congelar():
    casos=[]
    for i in range(100):
        ext=EXTS[i%len(EXTS)];encoding=['utf-8','utf-16','cp1252','latin-1'][i//len(EXTS)]
        casos.append({'id':f'DOC6H_{i+1:03}','extension':ext,'codificacion':encoding,
                      'clave':f'ORO6H{i+1:03}','dato':f'Existencias verificables {i+37}',
                      'referencia': 'hoja Ventas' if ext in {'xlsx','xlsm'} else 'tabla inventario' if ext in {'db','sqlite'} else 'contenido.txt' if ext in {'zip','tar','tgz'} else '',
                      'criterio':'La recuperación contiene la clave y el dato exactos, y cita el archivo y la unidad oro si corresponde.'})
    texto=json.dumps(casos,ensure_ascii=False,indent=2)+'\n'
    if CORPUS.exists() and CORPUS.read_text()!=texto:raise ValueError('Corpus ya congelado distinto; no lo sobrescribo.')
    if not CORPUS.exists():CORPUS.write_text(texto)
    huella=hashlib.sha256(CORPUS.read_bytes()).hexdigest();CORPUS.with_suffix('.sha256').write_text(huella+'\n')
    return huella

def preparar(base,c):
    ext=c['extension'];p=base/(c['id']+'.'+ext);t=c['clave']+' '+c['dato'];raw=t.encode(c['codificacion'])
    if ext=='env':raw=('NOMBRE='+t+'\nCLAVE_PRIVADA=secreto-ficticio\n').encode()
    if ext in {'docx','xlsx','xlsm','pptx','odt','ods','odp','epub','zip'}:
        with zipfile.ZipFile(p,'w') as z:
            if ext=='docx':z.writestr('word/document.xml','<w:document xmlns:w="urn:w"><w:body><w:p><w:t>'+t+'</w:t></w:p></w:body></w:document>')
            elif ext in {'xlsx','xlsm'}:
                z.writestr('xl/workbook.xml','<workbook xmlns:r="urn:r"><sheets><sheet name="Ventas" r:id="r1"/></sheets></workbook>');z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>');z.writestr('xl/worksheets/sheet1.xml','<worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>'+t+'</t></is></c></row></sheetData></worksheet>')
                if ext=='xlsm':z.writestr('xl/vbaProject.bin',b'MACRO NO EJECUTABLE SINTETICA')
            elif ext=='pptx':z.writestr('ppt/slides/slide1.xml','<sld><p><t>'+t+'</t></p></sld>')
            elif ext in {'odt','ods','odp'}:z.writestr('content.xml','<document><p>'+t+'</p></document>')
            elif ext=='epub':z.writestr('OEBPS/capitulo.xhtml','<html><body><p>'+t+'</p></body></html>')
            else:z.writestr('contenido.txt',raw)
    elif ext in {'tar','tgz'}:
        with tarfile.open(p,'w:gz' if ext=='tgz' else 'w') as z:
            n=tarfile.TarInfo('contenido.txt');n.size=len(raw);z.addfile(n,io.BytesIO(raw))
    elif ext=='gz':
        with gzip.open(p,'wb') as z:z.write(raw)
    elif ext in {'db','sqlite'}:
        with sqlite3.connect(p) as db:db.execute('CREATE TABLE inventario (dato TEXT)');db.execute('INSERT INTO inventario VALUES (?)',(t,));db.commit()
    elif ext=='html':p.write_text('<html><script>NO_EJECUTAR_INSTRUCCIONES</script><p>'+t+'</p></html>')
    elif ext=='rtf':p.write_text('{\\rtf1\\ansi '+t+'}')
    elif ext=='eml':p.write_text('From: ficticio@example.invalid\nSubject: '+c['clave']+'\nContent-Type: text/plain; charset=utf-8\n\n'+t)
    elif ext=='mbox':p.write_text('From ficticio@example.invalid Thu Oct 15 00:00:00 2026\nSubject: '+c['clave']+'\n\n'+t+'\n')
    elif ext=='ipynb':p.write_text(json.dumps({'cells':[{'cell_type':'markdown','source':[t]}],'metadata':{},'nbformat':4,'nbformat_minor':5}))
    else:p.write_bytes(raw)
    return p,c

def evaluar(salida,rubrica=2,baseline=None):
    huella=hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if huella!=CORPUS.with_suffix('.sha256').read_text().strip():raise ValueError('El corpus perdió su huella.')
    with tempfile.TemporaryDirectory(prefix='jarvis-documentos-eval-') as tmp:
        raiz=Path(tmp);os.environ['JARVIS_DIR']=str(raiz);os.environ['JARVIS_PRUEBAS']='1';os.environ['PYTHONDONTWRITEBYTECODE']='1';base=raiz/'trabajo';base.mkdir()
        if baseline:sys.path.insert(0,str(baseline))
        import tandas_documentales as T
        resultados=[]
        for c in json.loads(CORPUS.read_text()):
            p,actual=preparar(base,c);inicio=time.monotonic()
            try:
                d=T.indexar(T.crear([p])['id'],False);r=T.buscar(d['id'],'NOMBRE' if c['extension']=='env' and rubrica==2 else c['clave'],limite=5,presupuesto=5000)
                oro=[x for x in r['trozos'] if (c['clave'] in x['texto'] and actual['dato'] in x['texto'] and p.name in x['referencia'] and c['referencia'] in x['referencia'])]
                if c['extension']=='env':
                    oro=[x for x in r['trozos'] if '[REDACTADO]' in x['texto'] and c['clave'] not in x['texto'] and c['dato'] not in x['texto'] and 'secreto-ficticio' not in x['texto'] and p.name in x['referencia']] if rubrica==2 else []
                ok=bool(oro);detalle={'estado':d['archivos'][0]['estado'],'aviso':d['archivos'][0].get('aviso'),'referencias':[x['referencia'] for x in r['trozos']]}
            except Exception as e:ok=False;detalle={'error':type(e).__name__+': '+str(e)}
            resultados.append({'id':c['id'],'extension':c['extension'],'recall_5':int(ok),'cita_correcta':ok,'segundos':round(time.monotonic()-inicio,4),**detalle})
        salida.parent.mkdir(parents=True,exist_ok=True);salida.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in resultados));os.chmod(salida,0o600)
        resumen={'corpus_sha256':huella,'rubrica':rubrica,'casos':len(resultados),'aprobados':sum(x['cita_correcta'] for x in resultados),'fallidos':[x['id'] for x in resultados if not x['cita_correcta']],'tipo':'98 casos recuperación lexical y 2 redacción .env; sin Ollama ni conversación.','cambio_rubrica':'V2 corrige únicamente DOC6H_041/100: no debe recuperar valores .env privados, debe citar marcador redactado.' if rubrica==2 else 'V1 exigía valores .env incompatibles con privacidad.'}
        salida.with_suffix('.resumen.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2));print(json.dumps(resumen,ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--congelar',action='store_true');ap.add_argument('--salida',type=Path);ap.add_argument('--baseline',type=Path);ap.add_argument('--rubrica',type=int,choices=[1,2],default=2);a=ap.parse_args()
    if a.congelar:print(congelar())
    if a.salida:evaluar(a.salida,a.rubrica,a.baseline)
