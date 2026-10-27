"""Sonda de SOLO LECTURA del servidor MCP del Segundo Cerebro.

Se conecta, pregunta qué herramientas ofrece y las lista. NO llama a
ninguna herramienta, así que no lee ni cambia recuerdos.
Uso:  python3 ~/Jarvis/herramientas/sondear_mcp.py
"""
import json
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8765/mcp"
BASE = {"Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"}


def enviar(cuerpo, cabeceras_extra=None):
    cab = dict(BASE)
    cab.update(cabeceras_extra or {})
    peticion = urllib.request.Request(
        URL, data=json.dumps(cuerpo).encode("utf-8"), headers=cab)
    with urllib.request.urlopen(peticion, timeout=15) as r:
        return r.status, dict(r.headers), r.read().decode("utf-8", "replace")


def extraer_json(tipo, texto, id_esperado):
    """La respuesta puede venir como JSON normal o como eventos (SSE)."""
    if "text/event-stream" in tipo:
        for bloque in texto.split("\n"):
            if bloque.startswith("data:"):
                try:
                    dato = json.loads(bloque[5:].strip())
                except ValueError:
                    continue
                if dato.get("id") == id_esperado:
                    return dato
        return None
    return json.loads(texto) if texto.strip() else None


def tipo_de(cabeceras):
    for clave, valor in cabeceras.items():
        if clave.lower() == "content-type":
            return valor
    return ""


def sesion_de(cabeceras):
    for clave, valor in cabeceras.items():
        if clave.lower() == "mcp-session-id":
            return valor
    return None


def principal():
    try:
        estado, cab, texto = enviar({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "jarvis-sonda", "version": "0.1"}}})
    except urllib.error.HTTPError as e:
        print(f"El servidor respondió con error HTTP {e.code}:")
        print(e.read().decode("utf-8", "replace")[:500])
        return 1
    except urllib.error.URLError as e:
        print(f"No pude conectar con {URL}: {e.reason}")
        print("Prueba: systemctl --user status segundo-cerebro-mcp  "
              "(o sin --user)")
        return 1

    inicio = extraer_json(tipo_de(cab), texto, 1) or {}
    resultado = inicio.get("result", {})
    servidor = resultado.get("serverInfo", {})
    version = resultado.get("protocolVersion", "?")
    print(f"Servidor: {servidor.get('name', '?')} {servidor.get('version', '')}"
          f" · protocolo {version}")

    extra = {"MCP-Protocol-Version": version}
    sesion = sesion_de(cab)
    print("Sesión:", "sí (el servidor da identificador)" if sesion
          else "no (sin identificador de sesión)")
    if sesion:
        extra["Mcp-Session-Id"] = sesion

    try:
        enviar({"jsonrpc": "2.0", "method": "notifications/initialized"}, extra)
        estado, cab2, texto2 = enviar(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            extra)
    except urllib.error.HTTPError as e:
        print(f"Error HTTP {e.code} al pedir las herramientas:")
        print(e.read().decode("utf-8", "replace")[:500])
        return 1

    lista = (extraer_json(tipo_de(cab2), texto2, 2) or {}).get(
        "result", {}).get("tools", [])
    print(f"\nHerramientas ({len(lista)}):")
    for t in lista:
        esquema = t.get("inputSchema", {}) or {}
        requeridos = set(esquema.get("required", []))
        params = []
        for nombre, info in (esquema.get("properties", {}) or {}).items():
            marca = "*" if nombre in requeridos else ""
            params.append(f"{nombre}{marca}:{info.get('type', '?')}")
        descripcion = " ".join((t.get("description") or "").split())[:160]
        print(f"\n- {t.get('name')}({', '.join(params)})")
        if descripcion:
            print(f"    {descripcion}")
    print("\n(* = obligatorio)")
    return 0


if __name__ == "__main__":
    sys.exit(principal())