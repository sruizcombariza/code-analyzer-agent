# Reglas de equipo

Reglas que el sub-agente de Seguridad debe verificar en cada revisión de código.

1. **Sin secretos hardcodeados**: el código no debe contener API keys, contraseñas, tokens ni cualquier otro credencial escritos directamente en el código fuente. Deben leerse desde variables de entorno o un gestor de secretos.
2. **Sin `eval`/`exec` sobre entradas externas**: no se debe ejecutar dinámicamente código construido a partir de datos de entrada no confiables.
3. **Manejo explícito de errores**: las operaciones que puedan fallar (E/S de archivos, llamadas de red) deben capturar y tratar sus excepciones, no dejarlas propagar sin control.
4. **Nombres descriptivos**: funciones y variables deben tener nombres que expliquen su propósito; se rechazan nombres de una sola letra salvo en bucles cortos o expresiones matemáticas.
