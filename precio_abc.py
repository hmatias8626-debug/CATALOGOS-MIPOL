#!/usr/bin/env python3
"""
Consulta precios de ABC (abc-sa.com.ar) y los guarda en Supabase (tabla mipol_precios).

Configuración — creá un archivo .env en la misma carpeta:
    ABC_USUARIO=54097
    ABC_PASSWORD=tu_contraseña
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_KEY=tu_service_role_key

Uso:
    python precio_abc.py                          # todos los códigos de Supabase
    python precio_abc.py --codigos KTB901,SKD232  # códigos puntuales
    python precio_abc.py --salida precios.csv     # también guarda CSV local
"""

import os
import sys
import time
import argparse
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

# ── Configuración ──────────────────────────────────────────────
ABC_API   = "https://api.abc-sa.com.ar/v1"
ABC_WEB   = "https://www.abc-sa.com.ar"
TABLE_CAT = "mipol_productos_catalogo"
TABLE_PRC = "mipol_precios"

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ABC_USUARIO  = os.environ.get("ABC_USUARIO",  "")
ABC_PASSWORD = os.environ.get("ABC_PASSWORD", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HEADERS_BASE = {
    "accept":       "application/json",
    "content-type": "application/json",
    "referer":      f"{ABC_WEB}/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ── Login ────────────────────────────────────────────────────────
def login_abc(usuario: str, password: str) -> str:
    url = f"{ABC_API}/users/login"
    body = {
        "username":          usuario,
        "password":          password,
        "username_customer": "",
        "source":            "WEB",
    }
    r = requests.post(url, json=body, headers=HEADERS_BASE, timeout=15)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Login fallido ({r.status_code}): {r.text[:300]}")

    data = r.json()
    token = (
        data.get("token")
        or data.get("access_token")
        or data.get("accessToken")
        or (data.get("data") or {}).get("token")
        or (data.get("data") or {}).get("access_token")
    )
    if not token:
        raise RuntimeError(f"Login OK pero no se encontró token:\n{data}")

    print(f"✓ Login exitoso como usuario {usuario}")
    return token

# ── Consulta de artículo ───────────────────────────────────────────────
def consultar_precio(codigo: str, token: str) -> dict | None:
    headers = {**HEADERS_BASE, "x-access-token": token}
    try:
        r = requests.get(
            f"{ABC_API}/articles/{codigo}",
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code == 401:
            return "TOKEN_EXPIRADO"
        return None
    except requests.Timeout:
        return None
    except Exception as e:
        print(f"\n⚠  Error consultando {codigo}: {e}")
        return None

# ── Parseo de respuesta ────────────────────────────────────────────────
def extraer_filas(data, codigo_busqueda: str) -> list[dict]:
    if not data or data == "TOKEN_EXPIRADO":
        return []
    items = data if isinstance(data, list) else [data]
    filas = []
    for item in items:
        marca = item.get("brand") or {}
        if isinstance(marca, dict):
            marca = marca.get("name", "")

        stock_raw = item.get("stock") or item.get("in_stock") or item.get("inStock") or ""
        if isinstance(stock_raw, bool):
            stock = "Sí" if stock_raw else "No"
        elif isinstance(stock_raw, (int, float)):
            stock = str(int(stock_raw))
        else:
            stock = str(stock_raw)

        filas.append({
            "codigo":                codigo_busqueda,
            "proveedor":             "ABC",
            "precio_neto":           item.get("price") or item.get("net_price") or item.get("netPrice"),
            "precio_iva":            item.get("suggested_price") or item.get("suggestedPrice") or item.get("price_with_tax"),
            "stock":                 stock,
            "descripcion_proveedor": item.get("name") or item.get("description", ""),
            "marca_proveedor":       str(marca),
            "actualizado_en":        datetime.utcnow().isoformat(),
        })
    return filas

# ── Supabase: leer códigos ───────────────────────────────────────────────
def get_codigos_supabase(fuente: str = "") -> list[str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    params = {"select": "codigo", "order": "codigo.asc"}
    if fuente:
        params["fuente"] = f"eq.{fuente}"

    codigos: set[str] = set()
    start = 0
    while True:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE_CAT}",
            headers={**headers, "Range": f"{start}-{start + 999}"},
            params=params,
            timeout=30,
        )
        if r.status_code >= 400 or not r.json():
            break
        batch = [row["codigo"] for row in r.json() if row.get("codigo")]
        codigos.update(batch)
        if len(batch) < 1000:
            break
        start += 1000
    return sorted(codigos)

# ── Supabase: guardar precios (upsert) ─────────────────────────────────────────
def guardar_en_supabase(filas: list[dict]) -> bool:
    if not filas or not SUPABASE_URL or not SUPABASE_KEY:
        return False
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{TABLE_PRC}",
        headers={
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type":  "application/json",
            "Prefer":        "resolution=merge-duplicates",
        },
        json=filas,
        timeout=30,
    )
    return r.status_code in (200, 201)

# ── Main ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Descarga precios de ABC → Supabase")
    parser.add_argument("--codigos", help="Códigos separados por coma: KTB901,SKD232")
    parser.add_argument("--fuente",  help="Filtrar por fuente en Supabase (ej: DAYCO)")
    parser.add_argument("--salida",  help="También guardar en CSV local (ej: precios.csv)")
    parser.add_argument("--delay",   type=float, default=0.3, help="Segundos entre requests")
    args = parser.parse_args()

    usuario  = ABC_USUARIO  or input("Usuario ABC: ").strip()
    password = ABC_PASSWORD or input("Contraseña ABC: ").strip()

    try:
        token = login_abc(usuario, password)
    except RuntimeError as e:
        print(f"✗ {e}")
        sys.exit(1)

    if args.codigos:
        codigos = [c.strip().upper() for c in args.codigos.split(",") if c.strip()]
    else:
        print("Cargando códigos desde Supabase...")
        codigos = get_codigos_supabase(args.fuente or "")
        if not codigos:
            print("No se encontraron códigos. Usá --codigos KTB901,SKD232 para probar.")
            sys.exit(1)

    total = len(codigos)
    print(f"Consultando {total} código{'s' if total != 1 else ''} en ABC...\n")

    todos_resultados: list[dict] = []
    no_encontrados:   list[str]  = []
    lote_supabase:    list[dict] = []
    LOTE = 50

    for i, codigo in enumerate(codigos, 1):
        print(f"  [{i:>4}/{total}] {codigo:<20}", end="", flush=True)

        data = consultar_precio(codigo, token)

        if data == "TOKEN_EXPIRADO":
            print(" ⚠ token expirado, renovando...", end="", flush=True)
            try:
                token = login_abc(usuario, password)
                data = consultar_precio(codigo, token)
            except RuntimeError:
                print("✗ No se pudo renovar el token.")
                break

        filas = extraer_filas(data, codigo)

        if filas:
            todos_resultados.extend(filas)
            lote_supabase.extend(filas)
            precios = [
                f"${f['precio_neto']:>10,.2f}".replace(",", ".")
                for f in filas if f.get("precio_neto")
            ]
            print(f"✓  {' / '.join(precios) if precios else 'sin precio'}")
        else:
            no_encontrados.append(codigo)
            print("—  no encontrado")

        if len(lote_supabase) >= LOTE:
            ok = guardar_en_supabase(lote_supabase)
            print(f"       → {'✓ Guardado en Supabase' if ok else '⚠ Error guardando'} ({len(lote_supabase)} registros)")
            lote_supabase = []

        time.sleep(args.delay)

    if lote_supabase:
        ok = guardar_en_supabase(lote_supabase)
        print(f"\n→ {'✓ Guardado en Supabase' if ok else '⚠ Error guardando'} ({len(lote_supabase)} registros)")

    print(f"\n{'─'*60}")
    print(f"Encontrados   : {len(todos_resultados)} registros para {total - len(no_encontrados)} códigos")
    print(f"No encontrados: {len(no_encontrados)}")

    if args.salida and todos_resultados:
        df = pd.DataFrame(todos_resultados)
        df.to_csv(args.salida, index=False, encoding="utf-8-sig")
        print(f"✓ CSV guardado en: {args.salida}")

    if no_encontrados:
        nf = Path(args.salida or "precios_abc").stem + "_no_encontrados.txt"
        Path(nf).write_text("\n".join(no_encontrados), encoding="utf-8")
        print(f"✓ No encontrados: {nf}")

if __name__ == "__main__":
    main()
