"""Reproduce confirmaciones con Ollama y un caso ficticio, sin modificar proyectos."""
import json
import os
from pathlib import Path
import re
import tempfile
import time
from unittest.mock import patch

def main():
    salida=Path('/home/usuario/Jarvis/registros/reportes/continuidad_android_20261014/conversacion_real_final.json')
    with tempfile.TemporaryDirectory(prefix='jarvis-continuidad-') as tmp:
        os.environ.update(JARVIS_DIR=tmp,JARVIS_PRUEBAS='1');base=Path(tmp);(base/'trabajo').mkdir()
        import jarvis_agente as J
        import tandas_documentales as T
        fuente=base/'trabajo'/'caso_ficticio.txt'
        fuente.write_text('Caso sintético Tienda Ficticia: cuatro accesos. Distinguir conteos agregados de tránsito y compradores. MVP con datos sintéticos, Kotlin, Android Studio, Jetpack Compose, Material Design 3 y MVVM. Backend Spring Boot API REST, persistencia Room. No hay credenciales ni datos reales. Primer paso: crear una app nueva, sin adoptar proyectos existentes. MVVM es organización del código, no un selector del asistente de creación; Material 3 se configura en dependencias y tema.')
        d=T.indexar(T.crear([fuente])['id'],semantico=False);estado={'_tanda_documentos':d['id']}
        propuesta='Vamos a trabajar en el caso de Tienda Ficticia en Kotlin y Android Studio.\n1. Iniciar el proyecto con Kotlin y Compose.\n2. Definir funcionalidades.\n3. Estructura de carpetas.\n4. Crear pantalla principal.\n¿Confirmas que empecemos?'
        h=[{'role':'system','content':J.prompt_para_turno('Ayúdame con este caso en Kotlin Android Studio')},{'role':'user','content':'Ayúdame con este caso en Kotlin Android Studio'},{'role':'assistant','content':propuesta}];resultados=[]
        for p in ['SI te confirmo empecemos','empecemos con el 1','empecemos a hacer el caso']:
            h[0]['content']=J.prompt_para_turno(p,estado);h.append({'role':'user','content':p});inicio=time.monotonic();permisos=[]
            def denegar(t):permisos.append(t);return False
            with patch.object(J.IA.P,'opciones',return_value={'configurado':True,'automatico':True,'timeout_local':35,'preferido':'Falso'}),patch.object(J.IA,'preguntar_externa') as nube,patch.object(J.O,'solicitar',wraps=J.O.solicitar) as local:
                texto=J.responder_con_respaldo(h,J.enviar_a_ollama,denegar,estado);nube.assert_not_called()
            resultados.append({'pedido':p,'respuesta':texto,'segundos':round(time.monotonic()-inicio,2),'sin_error_ollama':not texto.startswith('No pude'),'sin_reconfirmacion_general':not J.SEGUIMIENTO.reconfirma_inicio(p,texto),'paso_android_concreto':bool(re.search(r'Empty Activity|New Project|Nuevo proyecto|File\s*>|nombre del proyecto|MainActivity|Android Studio',texto,re.I)),'permisos_solicitados':len(permisos),'escrituras_aprobadas':0,'llamadas_ollama':local.call_count,'inicio_guiado_por_controlador':True})
        salida.write_text(json.dumps({'criterio':'Sin error Ollama; sin reconfirmación general; paso Android concreto. Comprobación adicional más estricta que la primera inspección, conservada en conversacion_real.json. Datos sintéticos, cero escrituras aprobadas y cero consultas externas.','resultados':resultados},ensure_ascii=False,indent=2))
        print([{k:v for k,v in r.items() if k!='respuesta'} for r in resultados])
if __name__=='__main__':main()
