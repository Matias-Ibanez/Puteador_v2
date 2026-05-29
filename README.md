Puteador TTS Discord Bot (desarrollo)

Este repositorio contiene un bot de Discord mínimo en Python que lee en voz alta texto enviado mediante el comando de prefijo `!say`.

Características
- Comando `!say <texto>`: hace que el bot entre al canal de voz donde está el autor y lea el texto (máx. 250 caracteres).
- Permanecerá conectado hasta 3 minutos de inactividad y luego se desconectará automáticamente.
- Comando `!leave` para forzar la desconexión.

Requisitos
- Python 3.8+
- FFmpeg en PATH (para reproducción de audio)
- Un token de bot de Discord (poner en `.env` como `DISCORD_TOKEN`)

Instalación rápida
1. Crear entorno virtual (recomendado): `python -m venv .venv` y activarlo.
2. Instalar dependencias: `pip install -r requirements.txt`
3. Crear un archivo `.env` con: `DISCORD_TOKEN=tu_token_aqui`
4. Ejecutar: `python bot.py`

Uso
- En tu servidor de Discord, únete a un canal de voz.
- En cualquier canal de texto donde el bot tenga permiso para leer/recibir mensajes, envía:
  - `!say Hola, esto es una prueba` y el bot entrará al canal y leerá el texto.
  - `!leave` para desconectarlo manualmente.

Notas
- Este código está pensado para uso en desarrollo local según lo solicitado.
- Asegúrate de que el bot tenga permisos Connect y Speak en el servidor.
