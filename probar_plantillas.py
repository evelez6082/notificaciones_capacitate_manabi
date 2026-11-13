#!/usr/bin/env python3
"""Prueba de envío de TODAS las plantillas de Meta a un número de prueba.

Uso:
    .venv/bin/python3 probar_plantillas.py [--numero 593982104735]
"""
import argparse
import json
import time
from pathlib import Path

import notificador as noti

BASE = Path(__file__).resolve().parent
CATALOGO = json.loads((BASE / "plantillas_meta.json").read_text(encoding="utf-8"))

IMG = "https://cacicustech.com/capacitate_manabi/assets/694253231_1507359494090065_18027970677343898_n.jpg"
NOMBRE_PRUEBA = "Elvis Josué Vélez Hidalgo"


def variante(nombre):
    """Primera variante de idioma de una plantilla."""
    return CATALOGO[nombre][0]


def header_handle(nombre, formato):
    v = variante(nombre)
    for c in v.get("components", []):
        if c.get("type") == "HEADER" and c.get("format") == formato:
            handles = c.get("example", {}).get("header_handle", [])
            if handles:
                return handles[0]
    return None


def requiere_body_nombre(nombre):
    v = variante(nombre)
    for c in v.get("components", []):
        if c.get("type") == "BODY" and "{{1}}" in c.get("text", ""):
            return True
    return False


def boton_dinamico(nombre):
    """Devuelve (índice, url_base) del botón con variable {{n}}, o (None, None)."""
    v = variante(nombre)
    for c in v.get("components", []):
        if c.get("type") == "BUTTONS":
            for i, b in enumerate(c.get("buttons", [])):
                if "{{" in b.get("url", ""):
                    base = b["url"].split("{{")[0]
                    return i, base
    return None, None


def construir_envio(nombre):
    v = variante(nombre)
    img = None
    video = None
    for c in v.get("components", []):
        if c.get("type") == "HEADER":
            if c.get("format") == "IMAGE":
                img = IMG
            elif c.get("format") == "VIDEO":
                video = header_handle(nombre, "VIDEO")

    body = [NOMBRE_PRUEBA] if requiere_body_nombre(nombre) else None

    button_params = None
    bidx, base = boton_dinamico(nombre)
    if bidx is not None:
        # Sufijo de ejemplo para completar la URL dinámica del botón.
        button_params = [{"index": bidx, "text": "0"}]

    return v["language"], img, video, body, button_params


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numero", default="593982104735", help="Número de prueba (sin +)")
    args = parser.parse_args()

    noti.cargar_env_file()
    orden = list(CATALOGO.keys())
    print(f"Enviando {len(orden)} plantillas a {args.numero} ...\n")

    ok = 0
    errores = 0
    for nombre in orden:
        lang, img, video, body, btns = construir_envio(nombre)
        try:
            wamid = noti.enviar_plantilla_meta(
                args.numero, nombre, language_code=lang,
                body_params=body,
                header_image_url=img,
                header_video_url=video,
                button_params=btns,
            )
            ok += 1
            print(f"OK   {nombre}")
        except Exception as e:
            errores += 1
            print(f"ERR  {nombre}")
            print(f"     {e}")
        time.sleep(2)

    print(f"\nResultado: {ok} OK, {errores} errores.")


if __name__ == "__main__":
    main()
