"""Configuración local del auxiliar DeepSeek."""

import os

def habilitado():
    return os.environ.get(
        "JARVIS_DEEPSEEK", "0"
    ).strip().lower() in {"1", "true", "si", "on"}

def limite_analisis():
    return 600
