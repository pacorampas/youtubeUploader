# Instrucciones para la IA: youtubeUploader

Documento para un asistente de IA (Claude u otro) que tenga que subir vídeos de Francisco a YouTube con esta herramienta. El LEEME.md es la guía para personas; este archivo es el resumen operativo.

## Qué es

`subir.py` sube a YouTube, mediante la YouTube Data API v3, el vídeo largo y los shorts de UNA historia (una carpeta), con miniatura, título, descripción, etiquetas, lista de reproducción, aviso de contenido sintético y publicación programada. Lo usan sus canales de relatos narrados (skills `canal-relatos` y `relatos-realistas`).

Ubicación en su Mac: `~/Documents/IA/youtubeUploader/`

```
youtubeUploader/
├── subir.py                 # el script
├── requirements.txt         # google-api-python-client, google-auth-oauthlib
├── client_secret.json       # credenciales OAuth del proyecto de Google Cloud (NO leer en voz alta ni copiar fuera)
├── token.json               # permiso ya concedido; se crea en la primera ejecución
├── .venv/                   # entorno Python del Mac
├── LEEME.md                 # guía para Francisco
└── ejemplo/                 # plantilla de publicacion.json y descripcion.txt
```

## Flujo para subir una historia

1. Localiza la carpeta de la historia (contiene el vídeo final, los shorts y las miniaturas).
2. Crea en ella `publicacion.json` copiando `ejemplo/publicacion.json` y rellenándolo (formato abajo). Si existe `descripcion.txt` o similar, usa `descripcion_archivo`.
3. Enséñale a Francisco títulos, descripciones y fechas antes de subir, salvo que él ya los haya dado.
4. Ejecuta primero en modo prueba y corrige lo que señale:
   `python3 subir.py "<carpeta de la historia>" --prueba`
5. Ejecuta la subida real: `python3 subir.py "<carpeta de la historia>"`
6. Lee `subidos.json` en la carpeta de la historia y pásale los enlaces.

Si una ejecución falla a medias, se repite el mismo comando: lo que ya consta en `subidos.json` no se vuelve a subir (salvo con `--forzar`, que crea duplicados: úsalo solo si él lo pide).

## Formato de publicacion.json

```json
{
  "comun": {
    "etiquetas": ["relatos", "historias"],
    "categoria": "24",
    "idioma": "es",
    "privacidad": "private",
    "contenido_sintetico": true,
    "para_ninos": false,
    "lista_reproduccion": "Nombre exacto de una lista existente"
  },
  "videos": [
    {"tipo": "video", "archivo": "video.mp4", "miniatura": "miniatura.jpg",
     "titulo": "...", "descripcion_archivo": "descripcion.txt", "publicar": "2026-10-20 18:00"},
    {"tipo": "short", "archivo": "short1.mp4", "miniatura": "short1.jpg",
     "titulo": "... #shorts", "descripcion": "Historia completa 👉 {enlace_video}", "publicar": "2026-10-21 14:00"}
  ]
}
```

Reglas:
- `comun` se aplica a todos; cualquier campo puesto en una entrada lo sobrescribe.
- Exactamente un `"tipo": "video"` como máximo; shorts, los que haya (en sus canales suelen ser 3, o las 3 partes en Relatos Realistas).
- `{enlace_video}` en la descripción de un short se sustituye por el enlace del vídeo largo (se sube siempre primero).
- `publicar`: hora de Madrid, formato `AAAA-MM-DD HH:MM`, al menos 15 min en el futuro. Si hay fecha, se sube en privado y YouTube lo publica a esa hora. Sin fecha se usa `privacidad`.
- Título ≤ 100 caracteres; descripción ≤ 5000 bytes; sin `<` ni `>`; miniatura .jpg/.png ≤ 2 MB.
- Para que YouTube lo trate como short: vertical o cuadrado y ≤ 3 min. No hay campo especial.
- `contenido_sintetico: true` por defecto, porque sus vídeos usan imágenes generadas con IA.
- La lista de reproducción debe existir ya en el canal; el script no la crea.

## Dónde ejecutarlo

- **En su Mac (lo normal):** en Terminal, `cd ~/Documents/IA/youtubeUploader && source .venv/bin/activate && python3 subir.py ...`. Si la IA no tiene terminal en su Mac, dale el comando exacto para que lo pegue.
- **Desde una shell Linux con la carpeta montada (por ejemplo, el entorno remoto de Claude):** el `.venv` del Mac no sirve ahí. Crea uno aparte (`python3 -m venv .venv-linux && .venv-linux/bin/pip install -r requirements.txt`) y usa `.venv-linux/bin/python subir.py ...`. Solo funciona si `token.json` ya existe (el primer permiso abre un navegador y tiene que hacerlo él en su Mac) y si la red permite acceder a `oauth2.googleapis.com` y `www.googleapis.com`. Si falla la red, no insistas: dale el comando para su Terminal.
- Vídeos grandes: la subida puede tardar más que el tiempo máximo de un comando remoto. En ese caso, mejor que lo ejecute él.

## Limitaciones que hay que tener presentes

- **Proyecto sin verificar por Google = vídeos bloqueados en privado para siempre** (ni la programación ni el paso manual a público funcionan). Antes de subir vídeos reales, pregunta a Francisco si ya le han aprobado la verificación ("YouTube API Services Audit"). Si no, solo pruebas, o súbelos de otra forma (YouTube Studio).
- Miniaturas personalizadas: el canal debe estar verificado por teléfono. Si falla con 403, avísale; el script lo reintenta en la siguiente ejecución.
- `quotaExceeded`: cupo diario de la API agotado; se renueva hacia las 9:00 de Madrid. `uploadLimitExceeded`: límite diario de subidas del canal.
- `invalid_grant` o errores de token: borra `token.json` y que él vuelva a ejecutar en su Mac para dar permiso de nuevo.
- Nunca muestres, copies ni subas a otro sitio el contenido de `client_secret.json` o `token.json`.
