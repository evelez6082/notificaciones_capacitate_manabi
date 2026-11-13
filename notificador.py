#!/usr/bin/env python3
"""
Notificador unificado — Capacítate Manabí (Prefectura de Manabí)
=================================================================

Un único programa para enviar campañas de notificación (correo por Amazon SES y
WhatsApp por la API de Meta Cloud) a partir de listados Excel/CSV.

Características:
  * Varias campañas configurables en `config.json` (bienvenida, recordatorio, ...).
  * Historial acumulado en `historial/historial.csv`: al repetir un envío, detecta
    quién ya recibió el mensaje (por campaña + canal) y no lo reenvía.
  * Cada envío real genera automáticamente un informe en `informes/` con la fecha.
  * Los nuevos listados se dejan en `listados/` y se indican con `--excel`
    (o se define un listado por defecto en `config.json`).

COMANDOS
--------
  python3 notificador.py test      --campaign bienvenida          # 1 correo + 1 WhatsApp de prueba
  python3 notificador.py live      --campaign bienvenida --excel listados/nuevo.xlsx
  python3 notificador.py unico     --campaign bienvenida --email a@b.com --telefono 593999999999
  python3 notificador.py informe   --campaign bienvenida [--fecha 2026-10-08]
  python3 notificador.py historial
  python3 notificador.py plantillas [--guardar] [--json]

Envío individual (`unico`) — para reenviar a una sola persona:
  --email "..."   --telefono 593XXXXXXXX   (al menos uno de los dos)
  --nombre "..."  --usuario "..."  --password "..."  (opcional: autocompleta desde el listado)
  --canal email|whatsapp|ambos      --force (reintenta aunque ya esté en el historial)

Opciones útiles de `live`:
  --canal email|whatsapp|ambos     (por defecto lo que diga la campaña)
  --dry-run                        (simula, no envía nada)
  --yes                            (no pide confirmación interactiva)
  --limit N  --start-index N       (procesar un subconjunto)
  --rate N                         (máx. mensajes/segundo por canal)
  --subject "..."                  (sobreescribe el asunto del correo)
"""

import argparse
import csv
import json
import mimetypes
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from email.header import Header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas y constantes
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
TEMPLATES_DIR = BASE_DIR / "templates"
LISTADOS_DIR = BASE_DIR / "listados"
HISTORIAL_DIR = BASE_DIR / "historial"
INFORMES_DIR = BASE_DIR / "informes"
CONFIG_PATH = BASE_DIR / "config.json"
ENV_PATH = BASE_DIR / ".env"
HISTORIAL_PATH = HISTORIAL_DIR / "historial.csv"

HISTORIAL_HEADER = ["timestamp", "campaña", "canal", "destino", "nombre", "estado", "detalle"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Imágenes embebidas en el correo (Content-ID -> archivo). Los cids deben
# coincidir con los que referencia cada plantilla HTML.
INLINE_IMAGES = {
    "logo_capacitate": ASSETS_DIR / "logo_capacitate.png",
    "header_escudo": ASSETS_DIR / "header_escudo.png",
    "footer_prefectura": ASSETS_DIR / "footer_combined2.png",
}

# Placeholders que se reemplazan en las plantillas. El programa siempre
# reemplaza todos; cada plantilla usa únicamente los que necesita.
REEMPLAZOS_CLAVE = {
    "__NOMBRE__": "nombre_completo",
    "__USUARIO__": "usuario",
    "__PASSWORD__": "password",
    "__USUARIO_MOODLE__": "usuario",
}

GRAPH_API_VERSION = "v21.0"

# Códigos de error de Meta que indican límite de envío y admiten reintento.
WA_CODIGOS_RATE_LIMIT = {4, 80007, 130429}


# ---------------------------------------------------------------------------
# Configuración y variables de entorno
# ---------------------------------------------------------------------------

def cargar_env_file():
    """Carga las variables AWS_* y META_WA_* desde `.env` si no están ya en el
    entorno. Las variables ya exportadas en la terminal SIEMPRE tienen prioridad."""
    if not ENV_PATH.exists():
        return
    for linea in ENV_PATH.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if (clave.startswith("AWS_") or clave.startswith("META_WA_")) and valor and clave not in os.environ:
            os.environ[clave] = valor


def cargar_config():
    if not CONFIG_PATH.exists():
        sys.exit(f"No se encontró {CONFIG_PATH}. Cópialo desde el ejemplo o créalo.")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def obtener_campania(config, nombre):
    campanias = config.get("campanias", {})
    if nombre not in campanias:
        sys.exit(f"Campaña desconocida: '{nombre}'. Disponibles: {', '.join(campanias) or '(ninguna)'}")
    return campanias[nombre]


def resolver_listado(config, campania, excel_arg):
    if excel_arg:
        return Path(excel_arg)
    if campania.get("listado"):
        return BASE_DIR / campania["listado"]
    default = config.get("defaults", {}).get("listado")
    if default:
        return BASE_DIR / default
    sys.exit("Indica el listado con --excel (o define 'listado' en config.json).")


# ---------------------------------------------------------------------------
# Carga de contactos (Excel o CSV, formatos Moodle y legacy)
# ---------------------------------------------------------------------------

def normalizar_header(valor):
    if valor is None:
        return ""
    return str(valor).replace("\ufeff", "").strip().lower()


def quitar_tildes(valor):
    """Quita tildes/acentos para comparar cabeceras sin importar la ortografía."""
    s = unicodedata.normalize("NFD", valor)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def normalizar_celular_ec(valor):
    """Normaliza un celular de Ecuador a formato +593XXXXXXXXX.
    Devuelve None si el formato no es reconocible (para no adivinar)."""
    if valor is None:
        return None
    s = re.sub(r"[\s\-\(\)]", "", str(valor).strip())
    if not s:
        return None
    if s.startswith("+593") and len(s) == 13:
        return s
    if s.startswith("593") and len(s) == 12:
        return "+" + s
    if s.startswith("0") and len(s) == 10:
        return "+593" + s[1:]
    if s.startswith("9") and len(s) == 9:
        return "+593" + s
    return None


def _leer_filas(excel_path, hoja):
    """Devuelve las filas crudas del Excel o CSV (la primera suele ser la cabecera)."""
    excel_path = Path(excel_path)
    if not excel_path.exists():
        sys.exit(f"No se encontró el listado: {excel_path}")

    if excel_path.suffix.lower() == ".csv":
        with open(excel_path, "r", encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|") if sample else csv.excel
            except csv.Error:
                dialect = csv.excel
            lector = csv.reader(f, dialect=dialect)
            return [list(fila) for fila in lector], hoja or "csv"

    try:
        import openpyxl
    except ImportError:
        sys.exit("Falta openpyxl. Instala dependencias con:\n  pip install -r requirements.txt")

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    if hoja:
        if hoja not in wb.sheetnames:
            sys.exit(f"No se encontró la hoja '{hoja}' en {excel_path}. Hojas: {wb.sheetnames}")
        ws = wb[hoja]
    elif wb.sheetnames:
        ws = wb.active
    else:
        sys.exit(f"No hay hojas en {excel_path}.")
    return [list(fila) for fila in ws.iter_rows(values_only=True)], ws.title


def _encontrar_cabecera(filas):
    """Busca la fila que contiene 'correo' o 'email' y devuelve (idx, columnas)."""
    columnas_correo = {"correo", "email", "direccion de correo", "correo electronico"}
    for idx, fila in enumerate(filas):
        if fila and any(
            isinstance(c, str) and quitar_tildes(normalizar_header(c)) in columnas_correo
            for c in fila
        ):
            return idx, {
                quitar_tildes(normalizar_header(h)): i
                for i, h in enumerate(fila)
                if normalizar_header(h)
            }
    sys.exit("No se encontró la fila de encabezados (columna 'correo'/'email') en el listado.")


def cargar_contactos(excel_path, hoja=None):
    """Lee el listado y devuelve contactos normalizados.

    Cada contacto:
      nombre_completo, usuario, password, correo (minúsculas), correo_valido,
      celular_raw, celular (normalizado o None).
    Deduplica por correo (se queda con la primera aparición).
    """
    filas, _ = _leer_filas(excel_path, hoja)
    if not filas:
        sys.exit("El listado está vacío.")

    header_idx, col = _encontrar_cabecera(filas)

    def get(fila, *nombres):
        for nombre in nombres:
            idx = col.get(quitar_tildes(nombre))
            if idx is not None and idx < len(fila) and fila[idx] is not None:
                valor = str(fila[idx]).strip()
                if valor:
                    return valor
        return ""

    contactos = []
    vistos = set()
    for fila in filas[header_idx + 1:]:
        if not fila or all(c is None or str(c).strip() == "" for c in fila):
            continue
        correo = get(fila, "email", "correo", "correo moodle", "dirección de correo").lower()
        if not correo or not EMAIL_RE.match(correo):
            continue
        if correo in vistos:
            continue
        vistos.add(correo)

        nombre = get(fila, "firstname", "nombres", "nombre")
        apellido = get(fila, "lastname", "apellidos", "apellido")
        nombre_completo = (get(fila, "nombre completo", "nombre_completo", "apellidos y nombres")
                           or f"{nombre} {apellido}".strip())
        usuario = (get(fila, "username", "usuario moodle", "usuario_moodle", "nombre de usuario")
                   or get(fila, "cedula", "cédula"))
        password = get(fila, "password", "contraseña", "clave")
        celular_raw = get(fila, "phone1", "celular", "celular1", "telefono", "teléfono")

        contactos.append({
            "nombre_completo": nombre_completo or correo,
            "usuario": usuario,
            "password": password,
            "correo": correo,
            "correo_valido": bool(EMAIL_RE.match(correo)),
            "celular_raw": celular_raw,
            "celular": normalizar_celular_ec(celular_raw),
        })
    return contactos


def completar_credenciales(contactos, credenciales_path):
    """Rellena usuario/contraseña faltantes desde otro listado, solo si el correo
    coincide exactamente."""
    if not any(not c["usuario"] or not c["password"] for c in contactos):
        return
    credenciales_path = Path(credenciales_path)
    if not credenciales_path.exists():
        return
    por_correo = {c["correo"]: c for c in cargar_contactos(credenciales_path)}
    for c in contactos:
        fuente = por_correo.get(c["correo"])
        if fuente:
            c["usuario"] = c["usuario"] or fuente["usuario"]
            c["password"] = c["password"] or fuente["password"]


# ---------------------------------------------------------------------------
# Correo (Amazon SES)
# ---------------------------------------------------------------------------

def get_ses_client(region):
    try:
        import boto3
    except ImportError:
        sys.exit("Falta boto3. Instala dependencias con:\n  pip install -r requirements.txt")
    return boto3.client("ses", region_name=region)


def render_email(plantilla, contacto):
    import html as html_lib
    html = (TEMPLATES_DIR / f"{plantilla}.html").read_text(encoding="utf-8")
    txt = (TEMPLATES_DIR / f"{plantilla}.txt").read_text(encoding="utf-8")
    for marcador, campo in REEMPLAZOS_CLAVE.items():
        valor = contacto.get(campo, "") or ""
        html = html.replace(marcador, html_lib.escape(valor))
        txt = txt.replace(marcador, valor)
    return html, txt


def construir_mensaje_email(destinatario, contacto, asunto, remitente, plantilla):
    html_body, text_body = render_email(plantilla, contacto)

    msg = MIMEMultipart("related")
    msg["Subject"] = str(Header(asunto, "utf-8"))
    nombre_rem, direccion_rem = parseaddr(remitente)
    msg["From"] = formataddr((str(Header(nombre_rem, "utf-8")), direccion_rem)) if nombre_rem else remitente
    msg["To"] = destinatario

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    for cid, path in INLINE_IMAGES.items():
        if not path.exists():
            sys.exit(f"Falta la imagen requerida: {path}")
        mime_type, _ = mimetypes.guess_type(str(path))
        subtype = mime_type.split("/")[-1] if mime_type else "png"
        with open(path, "rb") as f:
            img = MIMEImage(f.read(), _subtype=subtype)
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=path.name)
        msg.attach(img)
    return msg


def enviar_ses(ses_client, remitente, destinatario, mime_msg):
    response = ses_client.send_raw_email(
        Source=remitente,
        Destinations=[destinatario],
        RawMessage={"Data": mime_msg.as_string()},
    )
    return response["MessageId"]


# ---------------------------------------------------------------------------
# WhatsApp (API de Meta Cloud)
# ---------------------------------------------------------------------------

class MetaWhatsAppError(Exception):
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        error = payload.get("error", {})
        mensaje = error.get("message", str(payload))
        codigo = error.get("code", "")
        subcodigo = error.get("error_subcode", "")
        super().__init__(f"[{status_code}] code={codigo} subcode={subcodigo}: {mensaje}")


def _credenciales_meta():
    token = os.environ.get("META_WA_ACCESS_TOKEN")
    phone_id = os.environ.get("META_WA_PHONE_NUMBER_ID")
    if not token or not phone_id:
        sys.exit("Faltan META_WA_ACCESS_TOKEN y/o META_WA_PHONE_NUMBER_ID.\n"
                 "  Ponlas en `.env` (ver `.env.example`) o expórtalas en la terminal.")
    return token, phone_id


def enviar_plantilla_meta(to_number, template_name, language_code="es", body_params=None,
                          timeout=20, header_image_url=None, header_video_url=None,
                          button_params=None):
    try:
        import requests
    except ImportError:
        sys.exit("Falta 'requests'. Instala dependencias con:\n  pip install -r requirements.txt")

    token, phone_id = _credenciales_meta()
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.lstrip("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }

    components = []
    if header_image_url:
        components.append({
            "type": "header",
            "parameters": [{"type": "image", "image": {"link": header_image_url}}],
        })
    if header_video_url:
        components.append({
            "type": "header",
            "parameters": [{"type": "video", "video": {"link": header_video_url}}],
        })
    if body_params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in body_params],
        })
    if button_params:
        for bp in button_params:
            components.append({
                "type": "button",
                "sub_type": bp.get("sub_type", "url"),
                "index": str(bp.get("index", 0)),
                "parameters": [{"type": "text", "text": str(bp.get("text", ""))}],
            })
    if components:
        payload["template"]["components"] = components

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.RequestException as e:
        raise MetaWhatsAppError(0, {"error": {"code": "NETWORK", "message": str(e)}})
    data = resp.json()
    if resp.status_code >= 400:
        raise MetaWhatsAppError(resp.status_code, data)
    return data["messages"][0]["id"]


def _waba_id_meta():
    """Devuelve el WABA ID (WhatsApp Business Account ID) desde el entorno.

    Es distinto del META_WA_PHONE_NUMBER_ID. Se obtiene en WhatsApp Manager →
    Configuración de la cuenta → API setup → "ID de la cuenta de WhatsApp
    Business", y se guarda en `.env` como META_WA_WABA_ID."""
    waba_id = os.environ.get("META_WA_WABA_ID")
    if not waba_id:
        sys.exit("Falta META_WA_WABA_ID.\n"
                 "  Es el 'ID de la cuenta de WhatsApp Business' (distinto del número de teléfono).\n"
                 "  Cópialo desde WhatsApp Manager → Configuración de la cuenta → API setup\n"
                 "  y añádelo a `.env` como: META_WA_WABA_ID=...")
    return waba_id.strip()


# Campos que se piden a Meta para describir cada plantilla. components trae la
# estructura (header format, variables de body, botones) para reconstruir el envío.
META_PLANTILLA_FIELDS = "id,name,status,language,category,quality_score,components"


def listar_plantillas_meta(waba_id=None, limit=100):
    """Lista TODAS las plantillas de la cuenta de WhatsApp Business (con paginación).

    Devuelve una lista de dicts, uno por plantilla, con claves: id, name, status,
    language (código), category, quality_score y components.
    """
    try:
        import requests
    except ImportError:
        sys.exit("Falta 'requests'. Instala dependencias con:\n  pip install -r requirements.txt")

    token, _ = _credenciales_meta()
    waba_id = waba_id or _waba_id_meta()
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{waba_id}/message_templates"

    plantillas = []
    after = None
    while True:
        params = {
            "fields": META_PLANTILLA_FIELDS,
            "limit": limit,
            "access_token": token,
        }
        if after:
            params["after"] = after
        try:
            resp = requests.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            raise MetaWhatsAppError(0, {"error": {"code": "NETWORK", "message": str(e)}})
        data = resp.json()
        if resp.status_code >= 400:
            raise MetaWhatsAppError(resp.status_code, data)
        plantillas.extend(data.get("data", []))
        paging = data.get("paging", {})
        after = paging.get("cursors", {}).get("after")
        if not after or not data.get("data"):
            break
    return plantillas


def descripcion_plantilla(t):
    """Resumen legible de una plantilla: nombre, idioma, estado, categoría y
    componentes (header, variables de body, botones)."""
    nombre = t.get("name", "?")
    idioma = t.get("language", "?")
    estado = t.get("status", "?")
    categoria = t.get("category", "?")
    calidad = t.get("quality_score", {}).get("score", "?") if isinstance(t.get("quality_score"), dict) else "?"
    partes = [f"{nombre} | {idioma} | {estado} | {categoria} | calidad={calidad}"]

    header = None
    vars_body = []
    botones = []
    for comp in t.get("components", []):
        tipo = comp.get("type")
        if tipo == "HEADER":
            header = comp.get("format")
        elif tipo == "BODY":
            vars_body = [p.get("text") for p in comp.get("parameters", [])
                         if p.get("type") == "text" or "text" in p]
        elif tipo == "BUTTONS":
            for b in comp.get("buttons", []):
                if b.get("type") == "URL":
                    botones.append(f"URL({b.get('text')})")
                elif b.get("type") == "PHONE_NUMBER":
                    botones.append(f"TEL({b.get('text')})")
                elif b.get("type") == "QUICK_REPLY":
                    botones.append(f"QR({b.get('text')})")
                else:
                    botones.append(b.get("type", "?"))
    if header:
        partes.append(f"header={header}")
    if vars_body:
        partes.append("vars={" + ", ".join(vars_body) + "}")
    if botones:
        partes.append("botones=[" + ", ".join(botones) + "]")
    return " ".join(partes)


def sincronizar_plantillas_meta(destino=None):
    """Lista las plantillas de Meta y las guarda en un JSON local para usarlas
    como catálogo (plantillas_meta.json). Devuelve (lista, ruta_guardada)."""
    plantillas = listar_plantillas_meta()
    destino = Path(destino) if destino else BASE_DIR / "plantillas_meta.json"
    catalogo = {}
    for t in plantillas:
        nombre = t.get("name")
        if not nombre:
            continue
        # Un nombre puede existir en varios idiomas; se guarda la lista.
        catalogo.setdefault(nombre, []).append({
            "id": t.get("id"),
            "language": t.get("language"),
            "status": t.get("status"),
            "category": t.get("category"),
            "quality_score": t.get("quality_score"),
            "components": t.get("components"),
        })
    destino.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    return plantillas, destino


# ---------------------------------------------------------------------------
# Historial y control de reenvíos
# ---------------------------------------------------------------------------

def _asegurar_historial():
    HISTORIAL_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORIAL_PATH.exists():
        with open(HISTORIAL_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HISTORIAL_HEADER)


def cargar_ya_enviados(campania):
    """Devuelve el conjunto de (canal, destino) ya enviados para una campaña."""
    enviados = set()
    if HISTORIAL_PATH.exists():
        with open(HISTORIAL_PATH, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                if fila.get("campaña") == campania and fila.get("estado") == "enviado":
                    enviados.add((fila.get("canal"), fila.get("destino", "").lower()))
    return enviados


def registrar(campania, canal, destino, nombre, estado, detalle):
    _asegurar_historial()
    with open(HISTORIAL_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().isoformat(timespec="seconds"),
            campania, canal, destino, nombre, estado, detalle,
        ])


def leer_historial():
    if not HISTORIAL_PATH.exists():
        return []
    with open(HISTORIAL_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def generar_informe(campania, descripcion, listado, canales, resumen, detalle_omitidos):
    INFORMES_DIR.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ruta = INFORMES_DIR / f"informe_{campania}_{marca}.md"

    lineas = [
        f"# Informe de envío — {campania}",
        "",
        f"- **Descripción:** {descripcion}",
        f"- **Fecha de envío:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Listado de entrada:** `{listado}`",
        f"- **Canales:** {', '.join(canales)}",
        "",
        "## Resumen",
        "",
        "| Canal | Enviados | Errores | Omitidos (ya enviados) |",
        "|-------|----------|---------|------------------------|",
    ]
    for canal in ("email", "whatsapp"):
        if canal in canales:
            lineas.append(
                f"| {'📧 Correo' if canal == 'email' else '💬 WhatsApp'} "
                f"| {resumen.get(canal + '_ok', 0)} "
                f"| {resumen.get(canal + '_error', 0)} "
                f"| {resumen.get(canal + '_omitido', 0)} |"
            )
    lineas.append("")
    lineas.append(f"**Total de mensajes enviados: "
                  f"{resumen.get('email_ok', 0) + resumen.get('whatsapp_ok', 0)}**")
    lineas.append("")

    if any(detalle_omitidos.values()):
        lineas.append("## Observaciones")
        lineas.append("")
        if detalle_omitidos.get("sin_correo"):
            lineas.append(f"- **{len(detalle_omitidos['sin_correo'])} sin correo válido:** "
                          + ", ".join(detalle_omitidos["sin_correo"]))
        if detalle_omitidos.get("sin_celular"):
            lineas.append(f"- **{len(detalle_omitidos['sin_celular'])} con celular no reconocido:** "
                          + ", ".join(detalle_omitidos["sin_celular"]))
        lineas.append("")
        lineas.append("> Los registros con celular no reconocido recibieron solo el correo.")

    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

def cmd_test(config, campania_nombre, args):
    campania = obtener_campania(config, campania_nombre)
    listado = resolver_listado(config, campania, args.excel)
    contactos = cargar_contactos(listado, args.hoja)
    if not contactos:
        sys.exit("No hay contactos válidos en el listado.")
    muestra = contactos[0]
    print(f"Datos de muestra: {muestra['nombre_completo']} (usuario: {muestra['usuario'] or '-'})")

    canales = args.canal or campania.get("canales", ["email"])

    if "email" in canales:
        print(f"Enviando correo de PRUEBA a {args.test_email}")
        msg = construir_mensaje_email(args.test_email, muestra,
                                      f"[PRUEBA] {args.subject or campania['asunto']}",
                                      args.sender, campania["plantilla"])
        if args.dry_run:
            print("  (--dry-run) correo no enviado")
        else:
            try:
                from botocore.exceptions import ClientError, BotoCoreError
                ses = get_ses_client(args.region)
                mid = enviar_ses(ses, args.sender, args.test_email, msg)
                print(f"  ✅ correo enviado. MessageId: {mid}")
            except (ClientError, BotoCoreError) as e:
                print(f"  ❌ error en correo de prueba: {e}")

    if "whatsapp" in canales:
        print(f"Enviando WhatsApp de PRUEBA a {args.test_whatsapp} "
              f"(plantilla '{campania.get('wa_template')}')")
        if args.dry_run:
            print("  (--dry-run) WhatsApp no enviado")
        else:
            try:
                wamid = enviar_plantilla_meta(
                    args.test_whatsapp,
                    campania.get("wa_template"),
                    campania.get("wa_language", "es"),
                    body_params=campania.get("wa_body_params"),
                    header_image_url=campania.get("wa_image_url"),
                )
                print(f"  ✅ WhatsApp enviado. wamid: {wamid}")
            except MetaWhatsAppError as e:
                print(f"  ❌ error en WhatsApp de prueba: {e}")


def cmd_live(config, campania_nombre, args):
    campania = obtener_campania(config, campania_nombre)
    listado = resolver_listado(config, campania, args.excel)

    contactos = cargar_contactos(listado, args.hoja)
    if args.credenciales:
        completar_credenciales(contactos, args.credenciales)
    print(f"Personas encontradas en el listado: {len(contactos)}")

    if not contactos:
        sys.exit("No hay contactos para procesar.")

    sin_correo = [c["nombre_completo"] for c in contactos if not c["correo_valido"]]
    sin_celular = [f"{c['nombre_completo']} ({c['celular_raw']})" for c in contactos if c["celular"] is None]
    if sin_correo:
        print(f"⚠️  {len(sin_correo)} sin correo válido: " + ", ".join(sin_correo))
    if sin_celular:
        print(f"⚠️  {len(sin_celular)} con celular no reconocido: " + ", ".join(sin_celular))

    canales = args.canal or campania.get("canales", ["email"])
    enviar_email = "email" in canales
    enviar_wa = "whatsapp" in canales

    faltan_credenciales = sum(not c["usuario"] or not c["password"] for c in contactos)
    if enviar_email and faltan_credenciales and campania["plantilla"] == "bienvenida":
        sys.exit(f"{faltan_credenciales} contactos no tienen usuario o contraseña. "
                 f"Completa las credenciales con --credenciales o revisa el listado.")

    ses_client = None
    ClientError = BotoCoreError = None
    if not args.dry_run:
        if enviar_email:
            from botocore.exceptions import ClientError, BotoCoreError
            ses_client = get_ses_client(args.region)

    pendientes = contactos[args.start_index:]
    if args.limit:
        pendientes = pendientes[:args.limit]

    ya_enviados = set() if args.force else cargar_ya_enviados(campania_nombre)
    print(f"Total en el rango seleccionado: {len(pendientes)}")
    print(f"Canales: {', '.join(canales)}")

    if not args.dry_run and not args.yes:
        confirm = input(f"\nEsto enviará mensajes REALES ({', '.join(canales)}) "
                        f"a {len(pendientes)} personas. Escribe ENVIAR para confirmar: ").strip()
        if confirm != "ENVIAR":
            print("Cancelado por el usuario.")
            return

    delay = 1.0 / args.rate if args.rate > 0 else 0
    resumen = {"email_ok": 0, "email_error": 0, "email_omitido": 0,
               "whatsapp_ok": 0, "whatsapp_error": 0, "whatsapp_omitido": 0}

    for i, c in enumerate(pendientes, 1):
        etiqueta = f"[{i}/{len(pendientes)}] {c['nombre_completo']}"

        if enviar_wa:
            if c["celular"] is None:
                print(f"{etiqueta} ⏭️  WhatsApp omitido (celular no reconocido: '{c['celular_raw']}')")
            elif ("whatsapp", c["celular"]) in ya_enviados:
                resumen["whatsapp_omitido"] += 1
                print(f"{etiqueta} ⏭️  WhatsApp ya enviado antes, se omite")
            elif args.dry_run:
                print(f"{etiqueta} (dry-run) WhatsApp a {c['celular']}")
            else:
                intentos = 0
                while True:
                    intentos += 1
                    try:
                        wamid = enviar_plantilla_meta(
                            c["celular"],
                            campania.get("wa_template"),
                            campania.get("wa_language", "es"),
                            body_params=campania.get("wa_body_params"),
                            header_image_url=campania.get("wa_image_url"),
                        )
                        registrar(campania_nombre, "whatsapp", c["celular"], c["nombre_completo"], "enviado", wamid)
                        resumen["whatsapp_ok"] += 1
                        print(f"{etiqueta} ✅ WhatsApp → {c['celular']}")
                        break
                    except MetaWhatsAppError as e:
                        codigo = e.payload.get("error", {}).get("code")
                        if (codigo in WA_CODIGOS_RATE_LIMIT or codigo == "NETWORK") and intentos <= 5:
                            espera = 2 ** intentos
                            # Los fallos de DNS (NETWORK) suelen recuperarse en 1-2s:
                            # da un margen mayor antes del primer reintento.
                            if codigo == "NETWORK":
                                espera = max(espera, 3)
                            print(f"{etiqueta} ⏳ WhatsApp: error transitorio, reintentando en {espera}s...")
                            time.sleep(espera)
                            continue
                        registrar(campania_nombre, "whatsapp", c["celular"], c["nombre_completo"], "error", str(e))
                        resumen["whatsapp_error"] += 1
                        print(f"{etiqueta} ❌ WhatsApp: {e}")
                        break
                if delay:
                    time.sleep(delay)

        if enviar_email:
            if not c["correo_valido"]:
                print(f"{etiqueta} ⏭️  Correo omitido (correo inválido: '{c['correo']}')")
            elif ("email", c["correo"].lower()) in ya_enviados:
                resumen["email_omitido"] += 1
                print(f"{etiqueta} ⏭️  Correo ya enviado antes, se omite")
            elif args.dry_run:
                print(f"{etiqueta} (dry-run) Correo a {c['correo']}")
            else:
                intentos = 0
                while True:
                    intentos += 1
                    msg = construir_mensaje_email(c["correo"], c,
                                                  args.subject or campania["asunto"],
                                                  args.sender, campania["plantilla"])
                    try:
                        mid = enviar_ses(ses_client, args.sender, c["correo"], msg)
                        registrar(campania_nombre, "email", c["correo"].lower(), c["nombre_completo"], "enviado", mid)
                        resumen["email_ok"] += 1
                        print(f"{etiqueta} ✅ Correo → {c['correo']}")
                        break
                    except ClientError as e:
                        codigo = e.response.get("Error", {}).get("Code", "")
                        if codigo == "Throttling" and intentos <= 5:
                            espera = 2 ** intentos
                            print(f"{etiqueta} ⏳ Correo: throttling, reintentando en {espera}s...")
                            time.sleep(espera)
                            continue
                        registrar(campania_nombre, "email", c["correo"].lower(), c["nombre_completo"], "error", str(e))
                        resumen["email_error"] += 1
                        print(f"{etiqueta} ❌ Correo: {e}")
                        break
                    except BotoCoreError as e:
                        registrar(campania_nombre, "email", c["correo"].lower(), c["nombre_completo"], "error", str(e))
                        resumen["email_error"] += 1
                        print(f"{etiqueta} ❌ Correo: {e}")
                        break
                if delay:
                    time.sleep(delay)

    print(f"\nResumen: correos enviados={resumen['email_ok']} errores={resumen['email_error']} "
          f"omitidos={resumen['email_omitido']} | whatsapp enviados={resumen['whatsapp_ok']} "
          f"errores={resumen['whatsapp_error']} omitidos={resumen['whatsapp_omitido']}")

    if args.dry_run:
        print("(--dry-run) No se envió nada; no se genera informe.")
        return

    detalle_omitidos = {"sin_correo": sin_correo, "sin_celular": sin_celular}
    ruta = generar_informe(campania_nombre, campania["descripcion"], listado, canales, resumen, detalle_omitidos)
    print(f"Informe: {ruta}")


def cmd_unico(config, campania_nombre, args):
    """Envía a un solo destinatario (correo y/o WhatsApp) indicando email/teléfono.

    Autocompleta nombre/usuario/contraseña desde el listado de la campaña si
    encuentra el correo o el celular; si no, usa --nombre/--usuario/--password.
    """
    campania = obtener_campania(config, campania_nombre)

    if not args.email and not args.telefono:
        sys.exit("Indica al menos --email o --telefono del destinatario.")

    correo = (args.email or "").strip().lower()
    telefono = normalizar_celular_ec(args.telefono) if args.telefono else None
    if args.telefono and not telefono:
        sys.exit(f"Celular no reconocido: '{args.telefono}'. Usa 593XXXXXXXX, 0XXXXXXXXX o 9XXXXXXXX.")

    nombre = args.nombre or ""
    usuario = args.usuario or ""
    password = args.password or ""

    # Autocompletar desde el listado si falta algún dato y no se pasó por CLI.
    if not (nombre and usuario and password):
        contactos = []
        try:
            listado = resolver_listado(config, campania, args.excel)
            contactos = cargar_contactos(listado, args.hoja)
        except SystemExit:
            pass
        for c in contactos:
            coincide = (correo and c["correo"] == correo) or (telefono and c["celular"] == telefono)
            if coincide:
                nombre = nombre or c["nombre_completo"]
                usuario = usuario or c["usuario"]
                password = password or c["password"]
                break

    contacto = {
        "nombre_completo": nombre or correo or args.telefono,
        "usuario": usuario,
        "password": password,
        "correo": correo,
        "correo_valido": bool(correo and EMAIL_RE.match(correo)),
        "celular_raw": args.telefono or "",
        "celular": telefono,
    }

    canales = args.canal or campania.get("canales", ["email"])
    enviar_email = "email" in canales and bool(correo)
    enviar_wa = "whatsapp" in canales and bool(telefono)

    if not enviar_email and not enviar_wa:
        sys.exit("Nada que enviar: revisa --email, --telefono y --canal.")

    if enviar_email and not contacto["correo_valido"]:
        sys.exit(f"Correo inválido: '{correo}'")

    if (enviar_email and campania["plantilla"] == "bienvenida"
            and (not contacto["usuario"] or not contacto["password"])):
        sys.exit("No se encontró usuario/contraseña para el correo. "
                 "Pásalos con --usuario y --password.")

    etiqueta = contacto["nombre_completo"]

    ya_enviados = set() if args.force else cargar_ya_enviados(campania_nombre)

    ses_client = None
    ClientError = BotoCoreError = None
    if enviar_email and not args.dry_run:
        from botocore.exceptions import ClientError, BotoCoreError
        ses_client = get_ses_client(args.region)

    if not args.dry_run and not args.yes:
        confirm = input(f"\nEnviar mensaje REAL ({', '.join(canales)}) a "
                        f"{etiqueta} ({correo or '-'} / {telefono or '-'})? "
                        f"Escribe ENVIAR para confirmar: ").strip()
        if confirm != "ENVIAR":
            print("Cancelado por el usuario.")
            return

    resumen = {"email_ok": 0, "email_error": 0, "email_omitido": 0,
               "whatsapp_ok": 0, "whatsapp_error": 0, "whatsapp_omitido": 0}

    if enviar_wa:
        if ("whatsapp", telefono) in ya_enviados:
            resumen["whatsapp_omitido"] += 1
            print(f"{etiqueta} ⏭️  WhatsApp ya enviado antes, se omite")
        elif args.dry_run:
            print(f"{etiqueta} (dry-run) WhatsApp a {telefono}")
        else:
            intentos = 0
            while True:
                intentos += 1
                try:
                    wamid = enviar_plantilla_meta(
                        telefono,
                        campania.get("wa_template"),
                        campania.get("wa_language", "es"),
                        body_params=campania.get("wa_body_params"),
                        header_image_url=campania.get("wa_image_url"),
                    )
                    registrar(campania_nombre, "whatsapp", telefono, etiqueta, "enviado", wamid)
                    resumen["whatsapp_ok"] += 1
                    print(f"{etiqueta} ✅ WhatsApp → {telefono}")
                    break
                except MetaWhatsAppError as e:
                    codigo = e.payload.get("error", {}).get("code")
                    if (codigo in WA_CODIGOS_RATE_LIMIT or codigo == "NETWORK") and intentos <= 5:
                        espera = 2 ** intentos
                        if codigo == "NETWORK":
                            espera = max(espera, 3)
                        print(f"{etiqueta} ⏳ WhatsApp: error transitorio, reintentando en {espera}s...")
                        time.sleep(espera)
                        continue
                    registrar(campania_nombre, "whatsapp", telefono, etiqueta, "error", str(e))
                    resumen["whatsapp_error"] += 1
                    print(f"{etiqueta} ❌ WhatsApp: {e}")
                    break

    if enviar_email:
        if ("email", correo) in ya_enviados:
            resumen["email_omitido"] += 1
            print(f"{etiqueta} ⏭️  Correo ya enviado antes, se omite")
        elif args.dry_run:
            print(f"{etiqueta} (dry-run) Correo a {correo}")
        else:
            intentos = 0
            while True:
                intentos += 1
                msg = construir_mensaje_email(correo, contacto,
                                              args.subject or campania["asunto"],
                                              args.sender, campania["plantilla"])
                try:
                    mid = enviar_ses(ses_client, args.sender, correo, msg)
                    registrar(campania_nombre, "email", correo, etiqueta, "enviado", mid)
                    resumen["email_ok"] += 1
                    print(f"{etiqueta} ✅ Correo → {correo}")
                    break
                except ClientError as e:
                    codigo = e.response.get("Error", {}).get("Code", "")
                    if codigo == "Throttling" and intentos <= 5:
                        espera = 2 ** intentos
                        print(f"{etiqueta} ⏳ Correo: throttling, reintentando en {espera}s...")
                        time.sleep(espera)
                        continue
                    registrar(campania_nombre, "email", correo, etiqueta, "error", str(e))
                    resumen["email_error"] += 1
                    print(f"{etiqueta} ❌ Correo: {e}")
                    break
                except BotoCoreError as e:
                    registrar(campania_nombre, "email", correo, etiqueta, "error", str(e))
                    resumen["email_error"] += 1
                    print(f"{etiqueta} ❌ Correo: {e}")
                    break

    print(f"\nResumen: correo enviado={resumen['email_ok']} error={resumen['email_error']} "
          f"omitido={resumen['email_omitido']} | whatsapp enviado={resumen['whatsapp_ok']} "
          f"error={resumen['whatsapp_error']} omitido={resumen['whatsapp_omitido']}")

    if args.dry_run:
        print("(--dry-run) No se envió nada; no se genera informe.")
        return

    detalle_omitidos = {
        "sin_correo": [] if contacto["correo_valido"] else [etiqueta],
        "sin_celular": [] if telefono else [etiqueta],
    }
    ruta = generar_informe(campania_nombre, campania["descripcion"],
                           "(envío individual)", canales, resumen, detalle_omitidos)
    print(f"Informe: {ruta}")


def cmd_informe(config, args):
    campania = obtener_campania(config, args.campaign)
    filas = [f for f in leer_historial() if f.get("campaña") == args.campaign]
    if args.fecha:
        filas = [f for f in filas if (f.get("timestamp") or "").startswith(args.fecha)]
    if not filas:
        print(f"No hay registros en el historial para '{args.campaign}'"
              + (f" en {args.fecha}" if args.fecha else "") + ".")
        return

    resumen = {"email_ok": 0, "email_error": 0, "email_omitido": 0,
               "whatsapp_ok": 0, "whatsapp_error": 0, "whatsapp_omitido": 0}
    for f in filas:
        canal = f.get("canal") or ""
        estado = f.get("estado") or ""
        clave = f"{canal}_{'ok' if estado == 'enviado' else 'error'}"
        if clave in resumen:
            resumen[clave] += 1

    ruta = generar_informe(args.campaign, campania["descripcion"],
                           "(historial)", ["email", "whatsapp"], resumen,
                           {"sin_correo": [], "sin_celular": []})
    print(f"Informe generado: {ruta}")


def cmd_historial(config, args):
    filas = leer_historial()
    if not filas:
        print("El historial está vacío.")
        return
    resumen = {}
    for f in filas:
        clave = (f.get("campaña") or "-", f.get("canal") or "-")
        resumen.setdefault(clave, {"enviado": 0, "error": 0})
        resumen[clave]["enviado" if f.get("estado") == "enviado" else "error"] += 1
    print(f"{'Campaña':<16} {'Canal':<10} {'Enviados':>9} {'Errores':>8}")
    print("-" * 46)
    for (campania, canal), v in sorted(resumen.items()):
        print(f"{campania:<16} {canal:<10} {v['enviado']:>9} {v['error']:>8}")
    total_ok = sum(v["enviado"] for v in resumen.values())
    total_err = sum(v["error"] for v in resumen.values())
    print("-" * 46)
    print(f"{'TOTAL':<16} {'':<10} {total_ok:>9} {total_err:>8}")


def cmd_plantillas(args):
    cargar_env_file()
    if args.guardar:
        plantillas, destino = sincronizar_plantillas_meta()
        print(f"{len(plantillas)} plantillas guardadas en {destino}")
    else:
        plantillas = listar_plantillas_meta()

    if args.json:
        print(json.dumps(plantillas, ensure_ascii=False, indent=2))
        return

    if not plantillas:
        print("No se encontraron plantillas en la cuenta de WhatsApp Business.")
        return

    print(f"Plantillas de WhatsApp Business ({len(plantillas)}):\n")
    for t in plantillas:
        print("• " + descripcion_plantilla(t))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cargar_env_file()
    config = cargar_config()
    defaults = config.get("defaults", {})

    parser = argparse.ArgumentParser(
        description="Notificador unificado — correo (SES) + WhatsApp (Meta).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    def add_common(p):
        p.add_argument("--campaign", required=True, help="Nombre de la campaña en config.json")
        p.add_argument("--excel", default=None, help="Ruta al listado Excel/CSV")
        p.add_argument("--hoja", default=None, help="Nombre de la hoja del Excel")
        p.add_argument("--sender", default=defaults.get("sender"))
        p.add_argument("--subject", default=None, help="Sobreescribe el asunto del correo")
        p.add_argument("--region", default=os.environ.get("AWS_REGION", defaults.get("region", "us-east-1")))
        p.add_argument("--rate", type=float, default=defaults.get("rate", 3.0))
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--yes", action="store_true")

    p_test = sub.add_parser("test", help="Enviar 1 correo + 1 WhatsApp de prueba")
    add_common(p_test)
    p_test.add_argument("--canal", nargs="+", choices=["email", "whatsapp"], default=None)
    p_test.add_argument("--test-email", default=defaults.get("test_email"))
    p_test.add_argument("--test-whatsapp", default=defaults.get("test_whatsapp"))

    p_live = sub.add_parser("live", help="Envío real al listado")
    add_common(p_live)
    p_live.add_argument("--canal", nargs="+", choices=["email", "whatsapp"], default=None)
    p_live.add_argument("--credenciales", default=None, help="Listado adicional para completar usuario/contraseña")
    p_live.add_argument("--limit", type=int, default=None)
    p_live.add_argument("--start-index", type=int, default=0)
    p_live.add_argument("--force", action="store_true", help="Reenviar aunque ya estén en el historial (ignora deduplicación)")

    p_unico = sub.add_parser("unico", help="Envío individual a un solo destinatario (correo y/o WhatsApp)")
    add_common(p_unico)
    p_unico.add_argument("--email", default=None, help="Correo del destinatario")
    p_unico.add_argument("--telefono", default=None, help="Celular del destinatario (cualquier formato de Ecuador)")
    p_unico.add_argument("--nombre", default=None, help="Nombre (si no se autocompleta desde el listado)")
    p_unico.add_argument("--usuario", default=None, help="Usuario Moodle (si no se autocompleta desde el listado)")
    p_unico.add_argument("--password", default=None, help="Contraseña (si no se autocompleta desde el listado)")
    p_unico.add_argument("--canal", nargs="+", choices=["email", "whatsapp"], default=None)
    p_unico.add_argument("--force", action="store_true", help="Reenviar aunque ya esté en el historial (ignora deduplicación)")

    p_informe = sub.add_parser("informe", help="Generar informe desde el historial")
    p_informe.add_argument("--campaign", required=True)
    p_informe.add_argument("--fecha", default=None, help="Filtra por fecha (YYYY-MM-DD)")

    sub.add_parser("historial", help="Resumen del historial acumulado")

    p_plantillas = sub.add_parser("plantillas", help="Listar/sincronizar plantillas de WhatsApp (Meta)")
    p_plantillas.add_argument("--guardar", action="store_true",
                              help="Guarda el catálogo en plantillas_meta.json")
    p_plantillas.add_argument("--json", action="store_true",
                              help="Imprime el JSON crudo en vez del resumen")

    args = parser.parse_args()

    if args.comando == "test":
        cmd_test(config, args.campaign, args)
    elif args.comando == "live":
        cmd_live(config, args.campaign, args)
    elif args.comando == "unico":
        cmd_unico(config, args.campaign, args)
    elif args.comando == "informe":
        cmd_informe(config, args)
    elif args.comando == "historial":
        cmd_historial(config, args)
    elif args.comando == "plantillas":
        cmd_plantillas(args)


if __name__ == "__main__":
    main()
