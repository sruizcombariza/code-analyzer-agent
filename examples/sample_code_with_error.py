"""Código de prueba con un error intencionado, usado como entrada de demo
para el Agente Analizador de Código (ver src/main.py).

Viola la regla 1 de team-rules.md: contiene un secreto hardcodeado.
"""


def send_request():
    api_key = "sk-live-1234567890abcdef"
    return call_external_service(api_key)
