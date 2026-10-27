"""Prueba real de opciones y embedding; solo modelos instalados, sin prompts privados."""
import os,json,tempfile,time
from pathlib import Path
from unittest.mock import patch
RAIZ=Path(__file__).resolve().parents[1]
DESTINO=RAIZ/'registros/reportes/ronda_mixta_20261020/cargas_ps_y_embedding_r3.json'

def main():
    if DESTINO.exists():raise ValueError('No sobrescribir otra comprobación')
    with tempfile.TemporaryDirectory(prefix='jarvis-cargas-real-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1')
        import cliente_ollama as O,configuracion_jarvis as C,recursos_ollama as R
        a=C.validar(dict(C.DEFAULT,keep_alive='1m'));datos=[]
        def pedir(ruta,cuerpo=None,**kw):
            with patch('entorno_jarvis.en_pruebas',return_value=False),patch.object(O,'leer',return_value=(a,'')):
                return O.solicitar(ruta,cuerpo,**kw)
        modelo=C.MODELO_PREDETERMINADO
        def descargar(nombre):
            pedir('/api/generate',{'model':nombre,'keep_alive':0,'stream':False},timeout=30)
            R.esperar_descarga(O,[nombre],time.monotonic()+10)
        for modo,capas,ctx in [('auto',37,16384),('mixto',24,32768),('mixto',12,32768),('cpu',0,32768)]:
            descargar(modelo);a.update(modo_gpu=modo,capas_gpu=max(1,capas),num_ctx=ctx)
            inicio=time.monotonic();error=None;repetida=None;r=None;ps_primera=None
            cuerpo={'model':modelo,'keep_alive':'1m','think':False,'stream':False,'messages':[{'role':'user','content':'Responde solamente CARGA'}],'options':{'num_ctx':ctx,'num_gpu':capas,'num_predict':128}}
            try:
                r=pedir('/api/chat',cuerpo,timeout=120)
                ps_primera=pedir('/api/ps')
                repetida=pedir('/api/chat',cuerpo,timeout=120)
            except Exception as exc:error={'texto':str(exc),'recursos':getattr(exc,'recursos',None)}
            ps=pedir('/api/ps');m=next((m for m in ps.get('models',[]) if m.get('name')==modelo),None)
            datos.append({'modo':modo,'capas_pedidas':capas,'contexto_pedido':ctx,'carga_segundos':time.monotonic()-inicio,'respuesta_original':r,'ps_primera':ps_primera,'segunda_peticion_misma_carga':repetida,'error':error,'ps':ps,'gpu':R.gpu(),'comprobado':bool(m and not error and m.get('context_length')==ctx and (m.get('size_vram')==0 if capas==0 else m.get('size_vram',0)>0))})
            DESTINO.write_text(json.dumps({'cargas':datos,'completa':False},ensure_ascii=False,indent=2)+'\n');print(modo,capas,ctx,datos[-1]['comprobado'],error,flush=True)

        descargar(modelo);a.update(modo_gpu='mixto',capas_gpu=24,num_ctx=32768)
        nombre='nomic-embed-text:latest';antes={m.get('name') for m in pedir('/api/ps').get('models',[])}
        tags=pedir('/api/tags').get('models',[])
        emb={'probado':False,'motivo':'No instalado; no se descarga'}
        if any(m.get('name')==nombre for m in tags):
            r=pedir('/api/embed',{'model':nombre,'input':'Texto sintético de inventario'},timeout=60)
            vectores=r.get('embeddings',[]);emb={'probado':True,'dimensiones':len(vectores[0]) if vectores else 0,'ok':bool(vectores and len(vectores[0])>0),'ps':pedir('/api/ps'),'ya_cargado_antes':nombre in antes}
            if nombre not in antes:descargar(nombre)
        DESTINO.write_text(json.dumps({'cargas':datos,'embedding':emb,'completa':True,'ps_final':pedir('/api/ps')},ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
