# youtubeUploader

Sube a YouTube el vídeo largo y los shorts de una historia, con miniatura, título, descripción, etiquetas, lista de reproducción y fecha de publicación programada.

## Instalación (solo la primera vez)

### 1. Python

Abre la app **Terminal** y escribe:

```
python3 --version
```

Si el Mac te ofrece instalar las "herramientas de línea de comandos", acepta y espera a que termine. Después:

```
cd ~/Documents/IA/youtubeUploader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Proyecto en Google Cloud (para que el script pueda hablar con YouTube)

1. Entra en https://console.cloud.google.com con la cuenta de Google de tu canal y crea un proyecto nuevo (por ejemplo, `youtubeUploader`).
2. Menú → **APIs y servicios → Biblioteca** → busca **YouTube Data API v3** → **Habilitar**.
3. Menú → **Google Auth Platform** (o "Pantalla de consentimiento de OAuth"):
   - Tipo de usuario: **Externo**.
   - Nombre de la aplicación: `youtubeUploader`, y tu correo donde lo pida.
   - En **Público / Usuarios de prueba**, añade tu correo.
   - Pulsa **Publicar aplicación** (pasarla a "En producción"). Si la dejas "En pruebas", Google te obligará a volver a dar permiso cada 7 días.
4. **Clientes** (o "Credenciales") → **Crear cliente OAuth** → tipo **Aplicación de escritorio** → descarga el JSON.
5. Cambia el nombre del archivo descargado a `client_secret.json` y ponlo en esta carpeta.

La primera vez que subas algo se abrirá el navegador para dar permiso. Google te avisará de que la app "no está verificada": pulsa **Configuración avanzada → Ir a youtubeUploader**. Es tu propia app, así que no hay problema. Después se guarda en `token.json` y no lo vuelve a pedir.

## Cómo preparar una historia

Dentro de la carpeta de cada historia pon los vídeos, las miniaturas y un archivo `publicacion.json`. Tienes uno de ejemplo en `ejemplo/publicacion.json`.

- `comun`: lo que se aplica a todos (etiquetas, lista de reproducción, etc.). Cualquier vídeo puede cambiarlo poniendo ese mismo campo en su entrada.
- `videos`: uno de tipo `"video"` (el largo) y los que quieras de tipo `"short"`.

| Campo | Qué es |
|---|---|
| `tipo` | `"video"` o `"short"` |
| `archivo` | nombre del vídeo dentro de la carpeta |
| `miniatura` | .jpg o .png de menos de 2 MB (opcional) |
| `titulo` | máximo 100 caracteres |
| `descripcion` | texto directo (usa `\n` para saltos de línea)… |
| `descripcion_archivo` | …o el nombre de un .txt con la descripción, más cómodo para textos largos |
| `publicar` | fecha y hora de Madrid, `"2026-10-20 18:00"`. Se sube en privado y YouTube lo publica a esa hora |
| `privacidad` | si no hay fecha: `"private"`, `"unlisted"` o `"public"` |
| `lista_reproduccion` | nombre de una lista que ya exista en tu canal (opcional) |
| `etiquetas` | lista de etiquetas |
| `contenido_sintetico` | `true` si lleva imágenes realistas hechas con IA (activa el aviso de contenido alterado o sintético de YouTube) |
| `para_ninos` | `false` normalmente |
| `categoria` | `"24"` es Entretenimiento; `"22"` Gente y blogs |

En la descripción de los shorts puedes escribir `{enlace_video}` y se cambiará por el enlace del vídeo largo, que siempre se sube primero.

Para que YouTube trate un vídeo como short tiene que ser vertical (o cuadrado) y durar 3 minutos o menos. No hay que hacer nada más.

## Cómo subir

```
cd ~/Documents/IA/youtubeUploader
source .venv/bin/activate
python3 subir.py ~/ruta/a/la/historia --prueba
python3 subir.py ~/ruta/a/la/historia
```

- `--prueba` revisa todo (archivos, títulos, fechas…) sin subir nada. Úsalo siempre antes.
- Truco: en vez de escribir la ruta, puedes arrastrar la carpeta de la historia a la ventana de Terminal.
- Al terminar se crea `subidos.json` en la carpeta de la historia con los enlaces. Si algo falla a medias, vuelve a ejecutar el mismo comando: lo ya subido no se repite (para forzarlo, añade `--forzar`).
- Si tienes `ffprobe` instalado (viene con ffmpeg), el script también avisa si un short es horizontal o dura más de 3 minutos.

## Limitaciones importantes

- **El proyecto no ha pasado la auditoría de YouTube.** Según Google, lo que sube un proyecto sin auditar queda bloqueado en privado. En la prueba del 13/10/2026 el vídeo subido sí se pudo hacer visible a mano desde YouTube Studio, así que el flujo actual es: **subir en privado con el script y publicar o programar a mano en Studio**. La publicación programada desde el script (`publicar`) probablemente no funcione hasta pasar la auditoría ("YouTube API Services Audit and Quota Extension Form").
- La app de Google está "En producción" (páginas en https://pacorampas.github.io/youtubeUploader/), así que el permiso no caduca cada 7 días. Al dar permiso seguirá saliendo el aviso de "app no verificada": es normal, pulsa Continuar.
- Para poner miniaturas personalizadas tu canal tiene que estar verificado por teléfono (https://www.youtube.com/verify).
- En los shorts, YouTube puede no mostrar la miniatura personalizada en todas partes, aunque se suba bien.
- Límites diarios: hasta 100 subidas por día. El cupo se renueva sobre las 9:00 (hora de Madrid).

## Archivos

- `subir.py`: el script.
- `INSTRUCCIONES_IA.md`: instrucciones para que una IA sepa usar la herramienta.
- `client_secret.json` y `token.json`: tus credenciales. **No los compartas con nadie.**
- `ejemplo/`: plantilla de `publicacion.json` y de descripción.
