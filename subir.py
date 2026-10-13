#!/usr/bin/env python3
"""
Sube a YouTube el vídeo largo y los shorts de una historia, con miniaturas,
títulos, descripciones, etiquetas, lista de reproducción y fecha de publicación.

Uso:
    python3 subir.py RUTA/A/LA/CARPETA/DE/LA/HISTORIA
    python3 subir.py RUTA/... --prueba     # revisa todo sin subir nada

La carpeta de la historia debe tener un archivo publicacion.json
(mira ejemplo/publicacion.json).
"""

import argparse
import datetime as dt
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

CARPETA_SCRIPT = Path(__file__).resolve().parent
CLIENT_SECRET = CARPETA_SCRIPT / "client_secret.json"
TOKEN = CARPETA_SCRIPT / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]
ZONA_HORARIA = "Europe/Madrid"
TAM_TROZO = 8 * 1024 * 1024  # se sube en trozos de 8 MB
MAX_REINTENTOS = 8
MAX_MINIATURA = 2 * 1024 * 1024  # YouTube no acepta miniaturas de más de 2 MB

VALORES_POR_DEFECTO = {
    "categoria": "24",  # Entretenimiento
    "idioma": "es",
    "etiquetas": [],
    "privacidad": "private",
    "para_ninos": False,
    "contenido_sintetico": True,  # imágenes hechas con IA
    "lista_reproduccion": "",
}


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

class ErrorConfig(Exception):
    pass


def avisar(texto):
    print(f"  ⚠️  {texto}")


def leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ErrorConfig(f"{ruta.name} tiene un error de formato en la línea {e.lineno}: {e.msg}")


def guardar_json(ruta, datos):
    tmp = ruta.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    tmp.replace(ruta)


def fecha_a_utc(texto):
    """'2026-10-20 18:00' (hora de Madrid) -> '2026-10-20T16:00:00Z'."""
    from zoneinfo import ZoneInfo

    texto = texto.strip().replace("T", " ")
    try:
        local = dt.datetime.strptime(texto, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ErrorConfig(f"Fecha «{texto}» no válida. Usa el formato 2026-10-20 18:00")
    local = local.replace(tzinfo=ZoneInfo(ZONA_HORARIA))
    return local.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def comprobar_fecha_futura(v):
    utc = dt.datetime.strptime(v["_publicar_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if utc <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15):
        raise ErrorConfig(f"la fecha {v['publicar']} ya ha pasado o es demasiado pronto (mínimo 15 min).")


def info_video(ruta):
    """Devuelve (duración en s, ancho, alto) si ffprobe está instalado; si no, None."""
    if not shutil.which("ffprobe"):
        return None
    try:
        salida = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", str(ruta)],
            capture_output=True, text=True, timeout=60,
        ).stdout
        d = json.loads(salida)
        s = d["streams"][0]
        return float(d["format"]["duration"]), int(s["width"]), int(s["height"])
    except Exception:
        return None


# --------------------------------------------------------------------------
# Preparar y revisar la configuración
# --------------------------------------------------------------------------

def cargar_historia(carpeta):
    ruta = carpeta / "publicacion.json"
    if not ruta.exists():
        raise ErrorConfig(f"No encuentro publicacion.json en {carpeta}")
    datos = leer_json(ruta)
    comun = {**VALORES_POR_DEFECTO, **datos.get("comun", {})}
    entradas = datos.get("videos", [])
    if not entradas:
        raise ErrorConfig("publicacion.json no tiene ningún vídeo en la lista «videos».")

    videos = []
    for i, e in enumerate(entradas, 1):
        v = {**comun, **e}
        nombre = v.get("archivo") or f"(entrada {i})"
        v["_nombre"] = nombre

        if v.get("tipo") not in ("video", "short"):
            raise ErrorConfig(f"{nombre}: «tipo» debe ser \"video\" o \"short\".")
        if not v.get("archivo"):
            raise ErrorConfig(f"Entrada {i}: falta «archivo».")
        v["_ruta"] = carpeta / v["archivo"]
        if not v["_ruta"].exists():
            raise ErrorConfig(f"{nombre}: no existe el archivo {v['_ruta']}")

        # Descripción: directa o desde un .txt
        if v.get("descripcion_archivo"):
            r = carpeta / v["descripcion_archivo"]
            if not r.exists():
                raise ErrorConfig(f"{nombre}: no existe {r}")
            v["descripcion"] = r.read_text(encoding="utf-8").strip()
        v.setdefault("descripcion", "")

        titulo = (v.get("titulo") or "").strip()
        if not titulo:
            raise ErrorConfig(f"{nombre}: falta «titulo».")
        if len(titulo) > 100:
            raise ErrorConfig(f"{nombre}: el título tiene {len(titulo)} caracteres (máximo 100).")
        if "<" in titulo or ">" in titulo or "<" in v["descripcion"] or ">" in v["descripcion"]:
            raise ErrorConfig(f"{nombre}: YouTube no permite los caracteres < ni > en título o descripción.")
        if len(v["descripcion"].encode("utf-8")) > 5000:
            raise ErrorConfig(f"{nombre}: la descripción supera los 5000 bytes.")
        if len(",".join(v["etiquetas"])) > 480:
            raise ErrorConfig(f"{nombre}: demasiadas etiquetas (máx. ~500 caracteres en total).")

        if v.get("miniatura"):
            m = carpeta / v["miniatura"]
            if not m.exists():
                raise ErrorConfig(f"{nombre}: no existe la miniatura {m}")
            if m.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                raise ErrorConfig(f"{nombre}: la miniatura debe ser .jpg o .png")
            if m.stat().st_size > MAX_MINIATURA:
                raise ErrorConfig(f"{nombre}: la miniatura pesa más de 2 MB.")
            v["_miniatura"] = m

        if v.get("privacidad") not in ("private", "unlisted", "public"):
            raise ErrorConfig(f"{nombre}: «privacidad» debe ser private, unlisted o public.")
        v["_publicar_utc"] = fecha_a_utc(v["publicar"]) if v.get("publicar") else None

        videos.append(v)

    if sum(1 for v in videos if v["tipo"] == "video") > 1:
        raise ErrorConfig("Solo puede haber un vídeo de tipo \"video\" (el largo) por historia.")
    usa_enlace = any("{enlace_video}" in v["descripcion"] for v in videos if v["tipo"] == "short")
    if usa_enlace and not any(v["tipo"] == "video" for v in videos):
        raise ErrorConfig("Algún short usa {enlace_video} pero no hay vídeo largo en la lista.")

    # El vídeo largo va primero, para tener su enlace al subir los shorts
    videos.sort(key=lambda v: 0 if v["tipo"] == "video" else 1)
    return videos


def revisar_formato(v):
    info = info_video(v["_ruta"])
    if info is None:
        return
    dur, ancho, alto = info
    if v["tipo"] == "short":
        if dur > 180:
            avisar(f"dura {dur:.0f} s: YouTube solo lo tratará como short si dura 3 min o menos.")
        if ancho > alto:
            avisar("es horizontal: para que sea short debe ser vertical o cuadrado.")
    elif dur <= 180 and alto >= ancho:
        avisar("es vertical y dura 3 min o menos: YouTube lo tratará como short.")


# --------------------------------------------------------------------------
# YouTube
# --------------------------------------------------------------------------

def conectar():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Faltan las librerías de Google. Ejecuta primero:  pip install -r requirements.txt")

    if not CLIENT_SECRET.exists():
        sys.exit(f"No encuentro {CLIENT_SECRET.name} en {CARPETA_SCRIPT}. Mira el LEEME.md, paso 2.")

    cred = None
    if TOKEN.exists():
        cred = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not cred or not cred.valid:
        if cred and cred.expired and cred.refresh_token:
            try:
                cred.refresh(Request())
            except Exception:
                cred = None
        if not cred or not cred.valid:
            print("Se va a abrir el navegador para que des permiso con tu cuenta de YouTube…")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            cred = flow.run_local_server(port=0)
        TOKEN.write_text(cred.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=cred)


def con_reintentos(funcion, descripcion):
    from googleapiclient.errors import HttpError

    for intento in range(MAX_REINTENTOS + 1):
        try:
            return funcion()
        except HttpError as e:
            if e.resp.status not in (500, 502, 503, 504) or intento == MAX_REINTENTOS:
                raise
            error = f"error {e.resp.status} de YouTube"
        except (ConnectionError, TimeoutError, OSError) as e:
            if intento == MAX_REINTENTOS:
                raise
            error = f"fallo de conexión ({e.__class__.__name__})"
        espera = min(2 ** intento + random.random(), 64)
        avisar(f"{descripcion}: {error}, reintento en {espera:.0f} s…")
        time.sleep(espera)


def buscar_lista(youtube, nombre, cache):
    if nombre in cache:
        return cache[nombre]
    peticion = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    nombres = []
    while peticion is not None:
        resp = con_reintentos(peticion.execute, "buscando listas")
        for item in resp.get("items", []):
            titulo = item["snippet"]["title"]
            nombres.append(titulo)
            if titulo.strip().lower() == nombre.strip().lower() or item["id"] == nombre:
                cache[nombre] = item["id"]
                return item["id"]
        peticion = youtube.playlists().list_next(peticion, resp)
    raise ErrorConfig(
        f"No encuentro la lista de reproducción «{nombre}» en tu canal. "
        f"Listas que existen: {', '.join(nombres) or '(ninguna)'}"
    )


def subir_video(youtube, v, descripcion):
    from googleapiclient.http import MediaFileUpload

    estado = {
        "privacyStatus": "private" if v["_publicar_utc"] else v["privacidad"],
        "selfDeclaredMadeForKids": bool(v["para_ninos"]),
        "containsSyntheticMedia": bool(v["contenido_sintetico"]),
    }
    if v["_publicar_utc"]:
        estado["publishAt"] = v["_publicar_utc"]

    cuerpo = {
        "snippet": {
            "title": v["titulo"].strip(),
            "description": descripcion,
            "tags": v["etiquetas"],
            "categoryId": str(v["categoria"]),
            "defaultLanguage": v["idioma"],
            "defaultAudioLanguage": v["idioma"],
        },
        "status": estado,
    }
    media = MediaFileUpload(str(v["_ruta"]), chunksize=TAM_TROZO, resumable=True)
    peticion = youtube.videos().insert(part="snippet,status", body=cuerpo, media_body=media)

    respuesta = None
    while respuesta is None:
        progreso, respuesta = con_reintentos(peticion.next_chunk, "subiendo")
        if progreso:
            print(f"\r  Subiendo… {progreso.progress() * 100:5.1f} %", end="", flush=True)
    print("\r  Subido al 100 %          ")
    return respuesta["id"]


def poner_miniatura(youtube, video_id, ruta):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    try:
        con_reintentos(
            lambda: youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(ruta))).execute(),
            "poniendo miniatura",
        )
        print("  Miniatura puesta.")
        return True
    except HttpError as e:
        if e.resp.status == 403:
            avisar("YouTube no deja poner la miniatura: verifica tu canal por teléfono en "
                   "youtube.com/verify (necesario para miniaturas personalizadas).")
        else:
            avisar(f"no se pudo poner la miniatura ({e.resp.status}). Se reintentará la próxima vez.")
        return False


def anadir_a_lista(youtube, video_id, lista_id):
    con_reintentos(
        lambda: youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": lista_id,
                              "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
        ).execute(),
        "añadiendo a la lista",
    )
    print("  Añadido a la lista de reproducción.")


# --------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------

def url_de(video_id, tipo):
    return f"https://youtube.com/shorts/{video_id}" if tipo == "short" else f"https://youtu.be/{video_id}"


def main():
    parser = argparse.ArgumentParser(description="Sube a YouTube el vídeo y los shorts de una historia.")
    parser.add_argument("carpeta", help="carpeta de la historia (con publicacion.json)")
    parser.add_argument("--prueba", action="store_true", help="revisa todo sin subir nada")
    parser.add_argument("--forzar", action="store_true", help="vuelve a subir aunque ya conste como subido")
    args = parser.parse_args()

    carpeta = Path(args.carpeta).expanduser().resolve()
    try:
        videos = cargar_historia(carpeta)
    except ErrorConfig as e:
        sys.exit(f"❌ {e}")

    ruta_registro = carpeta / "subidos.json"
    registro = leer_json(ruta_registro) if ruta_registro.exists() else {}

    print(f"\nHistoria: {carpeta.name}  ({len(videos)} archivos)\n")
    for v in videos:
        hecho = registro.get(v["archivo"])
        cuando = f"programado {v['publicar']}" if v.get("publicar") else v["privacidad"]
        pendiente = not hecho or args.forzar
        marca = cuando if pendiente else "ya subido"
        print(f"• [{v['tipo']}] {v['archivo']} → «{v['titulo']}» ({marca})")
        if pendiente:
            revisar_formato(v)
            if v["_publicar_utc"]:
                try:
                    comprobar_fecha_futura(v)
                except ErrorConfig as e:
                    sys.exit(f"❌ {v['archivo']}: {e}")

    if args.prueba:
        print("\n✅ Modo prueba: todo está en orden, no se ha subido nada.")
        return

    youtube = conectar()
    listas = {}
    enlace_video = None
    errores = 0

    for v in videos:
        print(f"\n▶ {v['archivo']}")
        hecho = registro.get(v["archivo"])
        try:
            if hecho and not args.forzar:
                video_id = hecho["id"]
                print(f"  Ya estaba subido: {hecho['url']}")
                if v.get("_miniatura") and not hecho.get("miniatura"):
                    hecho["miniatura"] = poner_miniatura(youtube, video_id, v["_miniatura"])
                    guardar_json(ruta_registro, registro)
            else:
                descripcion = v["descripcion"]
                if "{enlace_video}" in descripcion:
                    if not enlace_video:
                        raise ErrorConfig("no tengo el enlace del vídeo largo (¿falló su subida?).")
                    descripcion = descripcion.replace("{enlace_video}", enlace_video)

                video_id = subir_video(youtube, v, descripcion)
                hecho = {
                    "id": video_id,
                    "url": url_de(video_id, v["tipo"]),
                    "titulo": v["titulo"],
                    "subido": dt.datetime.now().isoformat(timespec="seconds"),
                    "publicar": v.get("publicar"),
                    "miniatura": False,
                    "lista": False,
                }
                registro[v["archivo"]] = hecho
                guardar_json(ruta_registro, registro)
                print(f"  {hecho['url']}")

                if v.get("_miniatura"):
                    hecho["miniatura"] = poner_miniatura(youtube, video_id, v["_miniatura"])
                    guardar_json(ruta_registro, registro)

            if v.get("lista_reproduccion") and not hecho.get("lista"):
                anadir_a_lista(youtube, video_id, buscar_lista(youtube, v["lista_reproduccion"], listas))
                hecho["lista"] = True
                guardar_json(ruta_registro, registro)

            if v["tipo"] == "video":
                enlace_video = hecho["url"]

        except ErrorConfig as e:
            errores += 1
            print(f"  ❌ {e}")
        except Exception as e:
            errores += 1
            texto = str(e)
            if "uploadLimitExceeded" in texto:
                texto = "has llegado al límite diario de subidas de tu canal. Prueba mañana."
            elif "quotaExceeded" in texto:
                texto = "se ha gastado el cupo diario de la API. Se renueva a las 9:00 (hora de Madrid)."
            print(f"  ❌ Error: {texto}")
            if "quotaExceeded" in str(e) or "uploadLimitExceeded" in str(e):
                break

    print("\n" + ("✅ Todo subido." if not errores else f"⚠️  Terminado con {errores} error(es). "
          "Vuelve a ejecutar el mismo comando: lo ya subido no se repite."))
    print(f"Enlaces guardados en {ruta_registro}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelado.")
