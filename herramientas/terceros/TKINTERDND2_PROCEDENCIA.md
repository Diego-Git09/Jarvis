# TkinterDnD2 local de Jarvis

- Versión: **0.6.4**, publicada el 11 de octubre de 2026.
- Fuente primaria: <https://pypi.org/project/tkinterdnd2/0.6.4/>.
- Repositorio upstream: <https://github.com/Eliav2/tkinterdnd2>.
- Archivo obtenido: `tkinterdnd2-0.6.4-py3-none-any.whl`.
- SHA256 verificado antes de copiar: `4b11e0ac6febd8609faf154851d782eca4068bfa68a88ca3d3dded8294367f80`.
- Descarga: <https://files.pythonhosted.org/packages/73/a6/72313c930c923406bd55fd7d389f6fcab2064ccd76be3590ef9d584cf2cf/tkinterdnd2-0.6.4-py3-none-any.whl>.

Se incluyen sin modificar `__init__.py`, `TkinterDnD.py`, la licencia MIT del
wrapper y únicamente los recursos oficiales Linux x86_64 de Tcl/Tk 8 y 9.
El manifiesto `TKINTERDND2_SHA256.json` conserva la huella de cada archivo.
Los scripts TkDND conservan íntegros sus avisos de copyright de George Petasis
y sus términos permisivos originales en las cabeceras. No se sustituyen
esos avisos por la licencia del wrapper.

No se instaló nada en Python global, paquetes del sistema o directorios del
usuario. Jarvis importa esta copia de su propio proyecto. El cargador oficial
`TkinterDnD.require(root)` elige la biblioteca de Tcl 8 o Tcl 9 según el
intérprete existente. La biblioteca nativa es código del proyecto upstream
verificado; los archivos que Diego arrastre se tratan exclusivamente como
rutas/datos y nunca se ejecutan.

El soporte empaquetado se limita a **Linux x86_64**. El Python del equipo usa
Tcl/Tk 8.6; la biblioteca oficial para Tcl 9 está incluida, pero eso no prueba
una interacción gráfica real con Tcl 9. Una sesión sin pantalla o sin una
biblioteca de sistema requerida devuelve un aviso y mantiene disponible el
selector «Adjuntar». No se descargan dependencias al iniciar Jarvis.
