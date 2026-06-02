import csv
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

BASE_URL = "https://webcateu.dayco.ws/api"
OUT_DIR = Path("dayco_full_out_v3")
OUT_DIR.mkdir(exist_ok=True)

# Para Argentina / autos livianos probamos primero car area2.
# Si querés camiones HD, agregar: {"area":"area6", "sito":"hd", "nombre":"HD"}
SCOPES = [
    {"area": "area2", "sito": "car", "nombre": "CAR"},
]

LANG = "es_es"
SLEEP = 0.35
TIMEOUT = 90
MAX_MARCAS = 0  # 0 = todas. Para probar: 3
MAX_MODELOS_POR_MARCA = 0  # 0 = todos. Para probar: 5

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://www.dayco.com",
    "Referer": "https://www.dayco.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
}

session = requests.Session()
session.headers.update(HEADERS)


def post_api(endpoint: str, payload: Dict[str, Any], retries: int = 5) -> Dict[str, Any]:
    url = f"{BASE_URL}/{endpoint}"
    last_err = None
    for i in range(retries):
        try:
            r = session.post(url, json=payload, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            print(f"[WARN] fallo {endpoint} intento {i+1}/{retries}: {e}")
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"No pude consultar {endpoint}: {last_err}")


def api_vehicle(scope: Dict[str, str], richiesta: str, filter_: str = "") -> List[Dict[str, Any]]:
    payload = {
        "area": scope["area"],
        "sito": scope["sito"],
        "lingua": LANG,
        "filter": filter_ or "",
        "richiesta": richiesta,
    }
    data = post_api("Vettura", payload)
    return data.get("d", {}).get("results", []) or []


def api_prodotti(scope: Dict[str, str], filter_: str) -> List[Dict[str, Any]]:
    payload = {
        "area": scope["area"],
        "sito": scope["sito"],
        "lingua": LANG,
        "filter": filter_,
        "richiesta": "Prodotto",
    }
    data = post_api("Prodotto", payload)
    return data.get("d", {}).get("results", []) or []


def api_detail_by_code(code: str, scope: Dict[str, str]) -> Optional[Dict[str, Any]]:
    # Busca por código exacto Dayco.
    payload = {
        "area": "area2",  # endpoint de producto usa area2 para catálogo productos car/moto
        "sito": "car;moto",
        "lingua": LANG,
        "filter": f"P7CODICE='{code}'",
        "richiesta": "ProdottiByID",
    }
    data = post_api("ProdottiByID", payload)
    results = data.get("d", {}).get("results", []) or []
    return results[0] if results else None


def clean(x: Any) -> str:
    if x is None:
        return ""
    return str(x).replace("\n", " ").replace("\r", " ").strip()


def get_title(obj: Dict[str, Any]) -> str:
    return clean(obj.get("Title") or obj.get("TitleLang") or obj.get("Id") or obj.get("ID"))


def wc(obj: Dict[str, Any]) -> str:
    return clean(obj.get("WhereCondition"))


def lang_title(obj: Any) -> str:
    """Extrae Title de estructuras tipo MarcaLang/ModelloLang/GammaLang de Dayco."""
    if not isinstance(obj, dict):
        return clean(obj)
    # forma simple
    for key in ("Title", "TitleLang", "Id", "ID"):
        val = clean(obj.get(key))
        if val:
            return val
    # forma anidada: {"es_es": {"es_es": "Ford"}}
    lang_obj = obj.get(LANG)
    if isinstance(lang_obj, dict):
        val = clean(lang_obj.get(LANG))
        if val:
            return val
    return ""

def veh_marca_modelo(veh: Dict[str, Any], marca_default: str, modelo_default: str) -> tuple[str, str, str]:
    """En Dayco la navegación a veces devuelve marca/modelo mal desde los nodos previos.
    La respuesta de Vettura trae MarcaLang y ModelloLang correctos; usamos eso como fuente de verdad.
    """
    marca_real = lang_title(veh.get("MarcaLang")) or clean(veh.get("Marca")) or marca_default
    modelo_real = lang_title(veh.get("ModelloLang")) or clean(veh.get("Modello")) or modelo_default
    gamma_real = lang_title(veh.get("GammaLang")) or clean(veh.get("Gamma"))
    return marca_real.upper(), modelo_real.upper(), gamma_real.upper()


def oem_from_detail(detail: Optional[Dict[str, Any]]) -> str:
    if not detail:
        return ""
    oes = detail.get("OesAm") or {}
    arr = oes.get("results") or []
    vals = []
    seen = set()
    for x in arr:
        title = clean(x.get("Title"))
        desc = clean(x.get("Descrizione"))
        if not title:
            continue
        val = f"{title} ({desc})" if desc else title
        key = val.upper()
        if key not in seen:
            vals.append(val)
            seen.add(key)
    return " | ".join(vals)


def img_url(filename: str) -> str:
    filename = clean(filename)
    if not filename or filename.lower() == "noimage.png":
        return ""
    # Base probable. Si no muestra en app, se corrige base URL sin rehacer scrapeo.
    return f"https://webcateu.dayco.ws/img/products/{filename}"


def familia_dayco(prod: Dict[str, Any], detail: Optional[Dict[str, Any]] = None) -> str:
    ref = clean(prod.get("Iref02") or prod.get("IREF02") or (detail or {}).get("Iref02") or (detail or {}).get("IREF02"))
    desc = clean(prod.get("DescrizioneProdotto") or (detail or {}).get("DescrizioneProdotto"))
    base = (ref or desc).upper()
    if "POLY" in base or "6PK" in base:
        return "CORREA POLY-V"
    if "KIT" in base and "WATER" in base:
        return "KIT BOMBA DE AGUA"
    if "KIT" in base:
        return "KIT DISTRIBUCION"
    if "TENSION" in base or "TENSOR" in base:
        return "TENSOR"
    if "PUL" in base or "POLEA" in base:
        return "POLEA"
    if "BOMBA" in base or "WATER" in base:
        return "BOMBA DE AGUA"
    if desc:
        return desc.upper()
    return ref or "DAYCO"


def extract_anio_from_generacion(g: str) -> str:
    # "01/2012 > 01/2018" -> "2012-2018"
    g = clean(g)
    if not g:
        return ""
    import re
    years = re.findall(r"(19\d{2}|20\d{2})", g)
    if len(years) >= 2:
        return f"{years[0]}-{years[-1]}"
    if years:
        return years[0]
    return g


def append_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]):
    if not rows:
        return
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def load_done_codes() -> set:
    path = OUT_DIR / "done_codes.txt"
    if not path.exists():
        return set()
    return set(x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip())


def mark_done_code(code: str):
    with (OUT_DIR / "done_codes.txt").open("a", encoding="utf-8") as f:
        f.write(code + "\n")


def load_done_vehicle() -> set:
    path = OUT_DIR / "done_vehicles.txt"
    if not path.exists():
        return set()
    return set(x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip())


def mark_done_vehicle(key: str):
    with (OUT_DIR / "done_vehicles.txt").open("a", encoding="utf-8") as f:
        f.write(key + "\n")



DEFAULT_MARCAS_CAR = [
    "FORD", "CHEVROLET", "FIAT", "RENAULT", "PEUGEOT", "CITROEN",
    "VOLKSWAGEN", "TOYOTA", "HONDA", "NISSAN", "HYUNDAI", "KIA",
    "MERCEDES-BENZ", "AUDI", "BMW", "SEAT", "SKODA", "ALFA ROMEO",
    "SUZUKI", "MITSUBISHI", "JEEP", "CHERY", "IVECO",
]


def ensure_seed_marcas(scope: Dict[str, str]) -> List[Dict[str, Any]]:
    """Dayco a veces hace timeout si pedimos todas las marcas CAR de golpe.
    Si existe dayco_marcas.csv lo usa. Si no existe, lo crea con marcas comunes.
    Formato: marca,wherecondition
    """
    path = Path("dayco_marcas.csv")
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["marca", "wherecondition"])
            w.writeheader()
            for m in DEFAULT_MARCAS_CAR:
                w.writerow({"marca": m, "wherecondition": f"CASA='{m}'"})
        print(f"[INFO] Creé {path}. Podés editarlo para sumar/quitar marcas antes de volver a correr.")

    rows = []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            marca = clean(row.get("marca"))
            where = clean(row.get("wherecondition")) or (f"CASA='{marca}'" if marca else "")
            if marca and where:
                rows.append({"Title": marca, "WhereCondition": where, "Sito": scope.get("sito", "car")})
    return rows


def safe_api_vehicle(scope: Dict[str, str], richiesta: str, filter_: str = "") -> List[Dict[str, Any]]:
    try:
        return api_vehicle(scope, richiesta, filter_)
    except Exception as e:
        print(f"[WARN] salto {richiesta} filter={filter_[:80]}... -> {e}")
        return []


def safe_api_prodotti(scope: Dict[str, str], filter_: str) -> List[Dict[str, Any]]:
    try:
        return api_prodotti(scope, filter_)
    except Exception as e:
        print(f"[WARN] salto Producto filter={filter_[:80]}... -> {e}")
        return []

APP_FIELDS = [
    "fuente", "codigo", "producto", "familia", "marca", "modelo", "anio", "info", "oem",
    "imagen_producto", "url_ficha", "aplicacion_dayco", "tipo_dayco", "dimension", "motor", "kw", "hp",
]
FICHA_FIELDS = [
    "fuente", "codigo", "producto", "familia", "ficha_anio", "ficha_info", "ficha_oem",
    "ficha_medidas", "imagen_producto", "url_ficha", "aplicacion_dayco", "tipo_dayco", "dimension",
]


def main():
    app_path = OUT_DIR / "dayco_aplicaciones.csv"
    fichas_path = OUT_DIR / "dayco_fichas.csv"
    detail_json_path = OUT_DIR / "detalles_productos.jsonl"

    done_codes = load_done_codes()
    done_vehicles = load_done_vehicle()
    fichas_seen = set(done_codes)

    total_apps = 0
    total_prod = 0

    for scope in SCOPES:
        print(f"\n[INFO] Scope {scope['nombre']} area={scope['area']} sito={scope['sito']}")
        try:
            marcas = api_vehicle(scope, "Marca", "")
        except Exception as e:
            print(f"[WARN] No pude pedir todas las marcas de {scope['nombre']} por timeout/API: {e}")
            marcas = []
        if not marcas and scope["sito"] == "car":
            marcas = ensure_seed_marcas(scope)
        print(f"[INFO] Marcas a procesar: {len(marcas)}")
        if MAX_MARCAS:
            marcas = marcas[:MAX_MARCAS]

        for i_m, marca_obj in enumerate(marcas, 1):
            marca = get_title(marca_obj)
            marca_filter = wc(marca_obj)
            print(f"\n[MARCA {i_m}/{len(marcas)}] {marca}")
            if not marca_filter:
                continue
            time.sleep(SLEEP)

            # En CAR, algunas ramas tienen Marca -> Gamma -> Modello; otras devuelven Modello directo.
            gammas = safe_api_vehicle(scope, "Gamma", marca_filter)
            if not gammas:
                gammas = [marca_obj]
            print(f"  Gamas: {len(gammas)}")

            modelos_total = []
            for gamma_obj in gammas:
                gamma_filter = wc(gamma_obj) or marca_filter
                modelos = safe_api_vehicle(scope, "Modello", gamma_filter)
                if not modelos and gamma_filter != marca_filter:
                    modelos = safe_api_vehicle(scope, "Modello", marca_filter)
                if not modelos:
                    modelos = [gamma_obj]
                modelos_total.extend(modelos)

            # deduplicar modelos por WhereCondition
            seen_mod = set()
            modelos = []
            for m in modelos_total:
                key = wc(m) or get_title(m)
                if key and key not in seen_mod:
                    seen_mod.add(key)
                    modelos.append(m)

            print(f"  Modelos: {len(modelos)}")
            if MAX_MODELOS_POR_MARCA:
                modelos = modelos[:MAX_MODELOS_POR_MARCA]

            for i_mod, mod_obj in enumerate(modelos, 1):
                modelo = get_title(mod_obj)
                mod_filter = wc(mod_obj)
                if not mod_filter:
                    continue
                print(f"  [MODELO {i_mod}/{len(modelos)}] {modelo}")
                time.sleep(SLEEP)

                versiones = safe_api_vehicle(scope, "Versione", mod_filter)
                if not versiones:
                    versiones = [mod_obj]
                print(f"    Versiones: {len(versiones)}")

                for ver_obj in versiones:
                    version = get_title(ver_obj)
                    ver_filter = wc(ver_obj) or mod_filter
                    time.sleep(SLEEP)

                    vehiculos = safe_api_vehicle(scope, "Vettura", ver_filter)
                    if not vehiculos:
                        vehiculos = [ver_obj]
                    print(f"      {version}: vehículos/motores {len(vehiculos)}")

                    for veh in vehiculos:
                        vehicle_filter = wc(veh)
                        if not vehicle_filter:
                            continue
                        veh_key = f"{scope['area']}|{vehicle_filter}"
                        if veh_key in done_vehicles:
                            continue

                        motor_obj = veh.get("Motore") if isinstance(veh.get("Motore"), dict) else {}
                        motor = clean((motor_obj or {}).get("Title") or (motor_obj or {}).get("TitoloCompleto") or veh.get("Motore"))
                        anio = extract_anio_from_generacion(veh.get("Generazione"))
                        kw = clean(veh.get("Kw"))
                        hp = clean(veh.get("Hp"))
                        marca_real, modelo_real, gamma_real = veh_marca_modelo(veh, marca, modelo)

                        time.sleep(SLEEP)
                        productos = safe_api_prodotti(scope, vehicle_filter)
                        if productos:
                            print(f"        Vehículo: {marca_real} {modelo_real} {anio} {motor} -> productos {len(productos)}")
                        if not productos:
                            mark_done_vehicle(veh_key)
                            continue

                        app_rows = []
                        ficha_rows = []

                        for prod in productos:
                            code = clean(prod.get("Title") or prod.get("ID") or prod.get("Id"))
                            if not code:
                                continue
                            total_prod += 1

                            detail = None
                            if code not in done_codes:
                                time.sleep(SLEEP)
                                try:
                                    detail = api_detail_by_code(code, scope)
                                    with detail_json_path.open("a", encoding="utf-8") as f:
                                        f.write(json.dumps({"codigo": code, "detalle": detail}, ensure_ascii=False) + "\n")
                                    mark_done_code(code)
                                    done_codes.add(code)
                                except Exception as e:
                                    print(f"[WARN] detalle falló {code}: {e}")
                            else:
                                # No releemos detalle si ya estaba. OEM no queda en nuevas filas si se reinicia,
                                # pero el detalle queda en JSONL para reprocesar. En corrida completa inicial no afecta.
                                detail = None

                            producto = clean(prod.get("DescrizioneProdotto") or (detail or {}).get("DescrizioneProdotto"))
                            tipo = clean(prod.get("Iref02") or prod.get("IREF02") or (detail or {}).get("Iref02") or (detail or {}).get("IREF02"))
                            dimension = clean(prod.get("Dimensioni") or (detail or {}).get("Dimensioni"))
                            aplicacion = clean(prod.get("ApplicazioneProdotto") or (detail or {}).get("ApplicazioneProdotto"))
                            imagen = img_url(clean(prod.get("ImmagineCalc") or (detail or {}).get("ImmagineCalc")))
                            familia = familia_dayco(prod, detail)
                            oem = oem_from_detail(detail)
                            url_ficha = f"https://www.dayco.com/la-es/catalog/?search={code}"

                            app_rows.append({
                                "fuente": "DAYCO",
                                "codigo": code,
                                "producto": producto,
                                "familia": familia,
                                "marca": marca_real,
                                "modelo": modelo_real,
                                "anio": anio,
                                "info": f"Motor: {motor} | Versión: {version} | Gama: {gamma_real}".strip(" |"),
                                "oem": oem,
                                "imagen_producto": imagen,
                                "url_ficha": url_ficha,
                                "aplicacion_dayco": aplicacion,
                                "tipo_dayco": tipo,
                                "dimension": dimension,
                                "motor": motor,
                                "kw": kw,
                                "hp": hp,
                            })

                            if code not in fichas_seen:
                                ficha_rows.append({
                                    "fuente": "DAYCO",
                                    "codigo": code,
                                    "producto": producto,
                                    "familia": familia,
                                    "ficha_anio": "",
                                    "ficha_info": clean((detail or {}).get("InformazioniTecniche")),
                                    "ficha_oem": oem,
                                    "ficha_medidas": dimension,
                                    "imagen_producto": imagen,
                                    "url_ficha": url_ficha,
                                    "aplicacion_dayco": aplicacion,
                                    "tipo_dayco": tipo,
                                    "dimension": dimension,
                                })
                                fichas_seen.add(code)

                        append_csv(app_path, app_rows, APP_FIELDS)
                        append_csv(fichas_path, ficha_rows, FICHA_FIELDS)
                        total_apps += len(app_rows)
                        mark_done_vehicle(veh_key)
                        print(f"        +{len(app_rows)} aplicaciones | acumulado {total_apps}")

    print("\n[OK] Scrapeo terminado")
    print(f"Aplicaciones: {app_path}")
    print(f"Fichas: {fichas_path}")
    try:
        apps = pd.read_csv(app_path, dtype=str).fillna("") if app_path.exists() else pd.DataFrame()
        fichas = pd.read_csv(fichas_path, dtype=str).fillna("") if fichas_path.exists() else pd.DataFrame()
        with pd.ExcelWriter(OUT_DIR / "dayco_productos.xlsx", engine="openpyxl") as writer:
            apps.to_excel(writer, index=False, sheet_name="aplicaciones")
            fichas.to_excel(writer, index=False, sheet_name="fichas")
        print(f"Excel: {OUT_DIR / 'dayco_productos.xlsx'}")
    except Exception as e:
        print(f"[WARN] No pude crear Excel: {e}")


if __name__ == "__main__":
    main()
