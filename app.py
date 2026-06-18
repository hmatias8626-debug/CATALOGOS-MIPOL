
import re
import math
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Catálogo MIPOL", page_icon="🔎", layout="wide")

TABLE = "mipol_productos_catalogo"
PAGE_SIZE = 5000
MAX_RESULTS = 300
PAGE_DISPLAY = 50
FILTER_PAGE_SIZE = 1000
FILTER_MAX_ROWS = 300000

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

COLUMNS = [
    "id", "fuente", "codigo", "marca", "modelo", "anio", "producto", "familia",
    "posicion", "lado", "oem", "oem_norm", "descripcion", "info",
    "ficha_oem", "ficha_info", "ficha_medidas", "imagen_producto", "url_ficha",

    # Medidas técnicas rodamientos
    "diametro_int", "diametro_ext", "altura", "abs",
    "diametro_int_filtro", "diametro_ext_filtro", "altura_filtro",

    # Medidas técnicas homocinéticas / semiejes / cardan
    "estrias_externas", "estrias_internas", "estrias_lado_rueda", "estrias_lado_caja",
    "longitud_semieje", "longitud_cardan", "longitud_punta_eje",
    "diametro_asiento", "diametro_asiento_lado_rueda",
    "diametro_jh", "diametro_junta_homocinetica", "diametro_jh_deslizante",
    "altura_jh", "altura_punta_eje", "diametro_circunferencia_agujeros",
    "rosca_agujeros", "diametro_rodamiento", "diametro_menor",
    "seguro", "peso", "dimensiones", "pieza",

    # Medidas técnicas fuelles (SERRAT)
    "boca_chica", "boca_grande", "largo", "categoria"
]

DISPLAY_COLUMNS = [
    "fuente", "codigo", "producto", "familia", "marca", "modelo", "anio",
    "pieza", "posicion", "lado", "oem", "descripcion", "info",

    # Rodamientos
    "diametro_int", "diametro_ext", "altura", "abs",

    # Homocinéticas / semiejes / cardan
    "estrias_externas", "estrias_internas", "estrias_lado_rueda", "estrias_lado_caja",
    "longitud_semieje", "longitud_cardan", "longitud_punta_eje",
    "diametro_asiento", "diametro_asiento_lado_rueda",
    "diametro_jh", "diametro_junta_homocinetica", "diametro_jh_deslizante",
    "altura_jh", "altura_punta_eje", "diametro_circunferencia_agujeros",
    "rosca_agujeros", "diametro_rodamiento", "diametro_menor",
    "seguro", "peso", "dimensiones",

    # Fuelles (SERRAT)
    "categoria", "boca_chica", "boca_grande", "largo",

    "imagen_producto", "url_ficha"
]

def limpiar(txt: str) -> str:
    return re.sub(r"\s+", " ", str(txt or "").replace("﻿", "")).strip()

def norm(txt: str) -> str:
    txt = str(txt or "").upper()
    reemplazos = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "Ä": "A", "Ë": "E", "Ï": "I", "Ö": "O", "Ü": "U",
        "Ñ": "N",
    }
    for a, b in reemplazos.items():
        txt = txt.replace(a, b)
    return re.sub(r"[^A-Z0-9]+", "", txt)

def normalizar_oem_token(txt: str) -> str:
    txt = str(txt or "").upper()
    reemplazos = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "Ä": "A", "Ë": "E", "Ï": "I", "Ö": "O", "Ü": "U",
        "Ñ": "N",
    }
    for a, b in reemplazos.items():
        txt = txt.replace(a, b)
    return re.sub(r"[^A-Z0-9]", "", txt)

def extraer_oem_tokens(txt: str) -> set[str]:
    txt = str(txt or "").upper()
    if not txt.strip():
        return set()

    tokens = set()
    partes = re.split(r"[|,;/\n\r]+", txt)

    for parte in partes:
        parte = re.sub(r"\b(ORIGINAL|OEM|NRO|N°|REF|REFERENCIA|CODIGO|CÓDIGO)\b\s*:?", " ", parte, flags=re.I)
        candidatos = re.findall(r"[A-Z0-9]+(?:[\s\.\-]+[A-Z0-9]+)+|[A-Z0-9]{5,}", parte)
        for c in candidatos:
            n = normalizar_oem_token(c)
            if len(n) < 5:
                continue
            if n.isdigit() and len(n) < 6:
                continue
            if n in {"SOPORTE", "MOTOR", "DERECHO", "IZQUIERDO", "DELANTERO", "TRASERO", "BUJE", "CAJA"}:
                continue
            tokens.add(n)
            if n.isdigit():
                tokens.add(n.lstrip("0") or n)
    return tokens

def headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "count=exact",
    }
    if extra:
        h.update(extra)
    return h

def supabase_ready():
    return bool(SUPABASE_URL and SUPABASE_KEY)

def rest_url():
    return f"{SUPABASE_URL}/rest/v1/{TABLE}"

def supabase_get(params: dict, start: int = 0, end: int = PAGE_SIZE - 1):
    r = requests.get(
        rest_url(),
        headers=headers({"Range": f"{start}-{end}"}),
        params=params,
        timeout=25,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Supabase error {r.status_code}: {r.text[:500]}")
    return r.json(), r.headers.get("content-range", "")

@st.cache_data(ttl=600, show_spinner="Cargando proveedores...")
def load_proveedores_cache():
    """Carga sólo proveedores. Mucho más liviano que traer todos los filtros al iniciar."""
    if not supabase_ready():
        return []

    all_rows = []
    start = 0
    while True:
        data, _ = supabase_get(
            {"select": "fuente", "order": "fuente.asc"},
            start,
            start + FILTER_PAGE_SIZE - 1,
        )
        if not data:
            break
        all_rows.extend(data)
        if len(data) < FILTER_PAGE_SIZE:
            break
        start += FILTER_PAGE_SIZE
        if start >= FILTER_MAX_ROWS:
            break

    vals = [limpiar(r.get("fuente", "")) for r in all_rows if limpiar(r.get("fuente", ""))]
    return sorted(set(vals), key=lambda x: norm(x))


@st.cache_data(ttl=600, show_spinner="Cargando filtros...")
def load_filter_cache(fuente="Todos", producto="Todos", marca="Todas", modelo="Todos"):
    """Carga opciones base para los selectboxes principales (sin columnas técnicas).
    Las columnas técnicas se cargan aparte con load_column_options, que aplica
    los filtros completos y devuelve sets pequeños.
    """
    if not supabase_ready():
        return pd.DataFrame()

    # Solo columnas base: 7 en vez de 21 → ~3x menos datos por request.
    cols = "fuente,marca,modelo,familia,producto,posicion,lado"

    params = {"select": cols, "order": "fuente.asc"}

    if fuente != "Todos":
        params["fuente"] = f"eq.{fuente}"
    if producto != "Todos":
        params["familia"] = f"eq.{producto}"
    if marca != "Todas":
        params["marca"] = f"eq.{marca}"
    if modelo != "Todos":
        params["modelo"] = f"eq.{modelo}"

    # OJO: la versión anterior cortaba en 30.000 filas.
    # Como la tabla estaba ordenada por fuente, si CILBRAKE tenía muchas filas,
    # el cache de filtros se quedaba sólo con CILBRAKE y por eso desaparecían marcas/proveedores.
    all_rows = []
    start = 0
    while True:
        data, _ = supabase_get(params, start, start + FILTER_PAGE_SIZE - 1)
        if not data:
            break
        all_rows.extend(data)
        if len(data) < FILTER_PAGE_SIZE:
            break
        start += FILTER_PAGE_SIZE
        if start >= FILTER_MAX_ROWS:
            break

    df = pd.DataFrame(all_rows).fillna("")
    for c in df.columns:
        df[c] = df[c].astype(str).map(limpiar)
    return df


def select_options(df: pd.DataFrame, col: str) -> list[str]:
    if df.empty or col not in df.columns:
        return []
    vals = [limpiar(v) for v in df[col].dropna().astype(str).unique() if limpiar(v)]
    return sorted(set(vals), key=lambda x: norm(x))

@st.cache_data(ttl=600, show_spinner="Cargando opciones...")
def load_column_options(col: str, fuente="Todos", producto="Todos", marca="Todas", modelo="Todos") -> list[str]:
    """Obtiene valores únicos de una sola columna con filtros aplicados.
    Se usa para filtros técnicos (rodamiento, homocinética, fuelle) donde el
    resultado ya está acotado por familia + proveedor → sets pequeños, 1 request.
    """
    if not supabase_ready():
        return []
    params = {"select": col, "order": f"{col}.asc"}
    if fuente != "Todos":
        params["fuente"] = f"eq.{fuente}"
    if producto != "Todos":
        params["familia"] = f"eq.{producto}"
    if marca != "Todas":
        params["marca"] = f"eq.{marca}"
    if modelo != "Todos":
        params["modelo"] = f"eq.{modelo}"
    data, _ = supabase_get(params, 0, 4999)
    vals = {limpiar(r.get(col, "")) for r in data}
    vals.discard("")
    return sorted(vals, key=lambda x: norm(x))

def build_query_params(
    fuente: str,
    q: str,
    codigo: str,
    oem: str,
    producto: str,
    marca: str,
    modelo: str,
    posicion: str,
    lado: str,
    diametro_int: str = "Todos",
    diametro_ext: str = "Todos",
    altura: str = "Todos",
    abs_sel: str = "Todos",
    estrias_ext: str = "Todos",
    estrias_int: str = "Todos",
    seguro: str = "Todos",
    boca_chica: str = "Todos",
    boca_grande: str = "Todos",
    largo: str = "Todos",
    categoria: str = "Todos",
    limit: int = MAX_RESULTS,
):
    params = {
        "select": ",".join(COLUMNS),
        "limit": str(limit),
        "order": "fuente.asc,codigo.asc",
    }

    and_filters = []

    if fuente != "Todos":
        params["fuente"] = f"eq.{fuente}"

    if producto != "Todos":
        params["familia"] = f"eq.{producto}"

    if marca != "Todas":
        params["marca"] = f"eq.{marca}"

    if modelo != "Todos":
        params["modelo"] = f"eq.{modelo}"

    if posicion != "Todos":
        params["posicion"] = f"eq.{posicion}"

    if lado != "Todos":
        params["lado"] = f"eq.{lado}"

    # Filtros técnicos rodamientos
    if diametro_int != "Todos":
        params["diametro_int_filtro"] = f"eq.{diametro_int}"
    if diametro_ext != "Todos":
        params["diametro_ext_filtro"] = f"eq.{diametro_ext}"
    if altura != "Todos":
        params["altura_filtro"] = f"eq.{altura}"
    if abs_sel != "Todos":
        params["abs"] = f"eq.{abs_sel}"

    # Filtros técnicos homocinéticas / semiejes
    if estrias_ext != "Todos":
        params["estrias_externas"] = f"eq.{estrias_ext}"
    if estrias_int != "Todos":
        params["estrias_internas"] = f"eq.{estrias_int}"
    if seguro != "Todos":
        params["seguro"] = f"eq.{seguro}"

    # Filtros técnicos fuelles
    if boca_chica != "Todos":
        params["boca_chica"] = f"eq.{boca_chica}"
    if boca_grande != "Todos":
        params["boca_grande"] = f"eq.{boca_grande}"
    if largo != "Todos":
        params["largo"] = f"eq.{largo}"
    if categoria != "Todos":
        params["categoria"] = f"eq.{categoria}"

    if codigo:
        params["codigo"] = f"ilike.*{codigo}*"

    # Bug fix: si se usan OEM y búsqueda general juntos, el segundo `or` pisaba al primero.
    # Ahora se combinan con `and` para que ambas condiciones se cumplan a la vez.
    if oem and q:
        oem_n = normalizar_oem_token(oem)
        qsafe = q.replace(",", " ").replace(")", " ").replace("(", " ")
        oem_part = f"or(oem_norm.ilike.*{oem_n}*,oem.ilike.*{oem}*,ficha_oem.ilike.*{oem}*)"
        q_part = (
            f"or(codigo.ilike.*{qsafe}*,marca.ilike.*{qsafe}*,modelo.ilike.*{qsafe}*,"
            f"producto.ilike.*{qsafe}*,familia.ilike.*{qsafe}*,descripcion.ilike.*{qsafe}*,"
            f"info.ilike.*{qsafe}*,oem.ilike.*{qsafe}*,ficha_oem.ilike.*{qsafe}*)"
        )
        params["and"] = f"({oem_part},{q_part})"
    elif oem:
        oem_n = normalizar_oem_token(oem)
        if oem_n:
            params["or"] = f"(oem_norm.ilike.*{oem_n}*,oem.ilike.*{oem}*,ficha_oem.ilike.*{oem}*)"
    elif q:
        qsafe = q.replace(",", " ").replace(")", " ").replace("(", " ")
        params["or"] = (
            f"(codigo.ilike.*{qsafe}*,marca.ilike.*{qsafe}*,modelo.ilike.*{qsafe}*,"
            f"producto.ilike.*{qsafe}*,familia.ilike.*{qsafe}*,descripcion.ilike.*{qsafe}*,"
            f"info.ilike.*{qsafe}*,oem.ilike.*{qsafe}*,ficha_oem.ilike.*{qsafe}*)"
        )

    return params

@st.cache_data(ttl=120, show_spinner=False)
def query_productos_cached(params_tuple):
    params = dict(params_tuple)
    data, _ = supabase_get(params, 0, MAX_RESULTS - 1)
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).map(limpiar)
    return df[COLUMNS]

def query_productos(**kwargs):
    params = build_query_params(**kwargs)
    return query_productos_cached(tuple(sorted(params.items())))



def split_oem_tokens_reales(txt: str) -> set[str]:
    """Extrae sólo OEM reales desde columnas OEM confiables.
    Se usa para columnas: oem, ficha_oem y oem_norm.
    No se usa info ni descripción para evitar falsos positivos.
    """
    txt = str(txt or "")
    out = set()

    basura = {
        "SOPORTE", "SOPORTEDEMOTOR", "SOPORTEMOTOR", "SOPORTEDECAJA", "SOPORTECAJA",
        "SOPORTEAMORTIGUADOR", "BUJE", "BUJEPARRILLA", "BUJEBARRAESTABILIZADORA",
        "MOTOR", "CAJA", "DERECHO", "IZQUIERDO", "DELANTERO", "TRASERO",
        "SUPERIOR", "INFERIOR", "HIDRAULICO", "NOHIDRAULICO", "AMORTIGUADOR",
        "PARRILLA", "BARRA", "ESTABILIZADORA", "CRAPODINA", "TOPE",
        "MODELO", "ORIGINAL", "CODIGO", "PRODUCTO", "FAMILIA"
    }

    for p in re.split(r"[|,;/\n\r]+", txt):
        p = re.sub(r"\b(ORIGINAL|OEM|NRO|N°|REF|REFERENCIA|CODIGO|CÓDIGO)\b\s*:?", " ", p, flags=re.I)
        candidatos = re.findall(r"[A-Z0-9]+(?:[\s\.\-]+[A-Z0-9]+)+|[A-Z0-9]{5,}", p.upper())

        for c in candidatos:
            n = normalizar_oem_token(c)
            if not n or len(n) < 5:
                continue

            if n in basura:
                continue

            if any(x in n for x in [
                "SOPORTE", "BUJE", "MOTOR", "DERECHO", "IZQUIERDO",
                "DELANTERO", "TRASERO", "HIDRAULICO", "AMORTIGUADOR",
                "DURATEC", "TURBO", "DIESEL", "NAFTA", "VALVULAS"
            ]):
                continue

            if re.fullmatch(r"\d{1,2}V", n):
                continue
            if re.fullmatch(r"\d{1,2}(TD|TDI|HDI|MPI|V|I|L)", n):
                continue

            # OEM numérico: mínimo 6 dígitos.
            if n.isdigit():
                if len(n) < 6:
                    continue
                out.add(n)
                out.add(n.lstrip("0") or n)
                continue

            # OEM alfanumérico: letras + números.
            if re.search(r"[A-Z]", n) and re.search(r"\d", n) and len(n) >= 6:
                out.add(n)

    return out

def extraer_oem_tokens_fila(row: pd.Series) -> set[str]:
    """Usa sólo columnas confiables para equivalencias OEM."""
    tokens = set()
    for col in ["oem_norm", "oem", "ficha_oem"]:
        if col in row.index:
            tokens |= split_oem_tokens_reales(row.get(col, ""))
    return tokens




def buscar_equivalencias_oem(res_base: pd.DataFrame, fuente_actual: str) -> pd.DataFrame:
    """Busca equivalencias usando OEM reales del resultado base,
    pero consulta SOLO oem_norm en Supabase para evitar timeout.
    """
    if res_base.empty:
        return pd.DataFrame(columns=COLUMNS + ["match_oem"])

    tokens = set()
    for _, row in res_base.iterrows():
        tokens |= extraer_oem_tokens_fila(row)

    if not tokens:
        return pd.DataFrame(columns=COLUMNS + ["match_oem"])

    # Evitar query enorme.
    tokens = sorted(tokens)[:20]

    # IMPORTANTE:
    # Buscamos sólo en oem_norm. Esa columna está normalizada e indexada.
    # No buscar en oem ni ficha_oem porque provoca statement timeout.
    partes_or = [f"oem_norm.ilike.*{t}*" for t in tokens]

    params = {
        "select": ",".join(COLUMNS),
        "or": "(" + ",".join(partes_or) + ")",
        "limit": "1000",
        "order": "fuente.asc,codigo.asc",
    }

    data, _ = supabase_get(params, 0, 999)
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS + ["match_oem"])

    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).map(limpiar)

    if fuente_actual != "Todos":
        df = df[df["fuente"].map(norm) != norm(fuente_actual)].copy()

    base_keys = set((res_base["fuente"] + "|" + res_base["codigo"] + "|" + res_base["modelo"]).tolist())
    df = df[~(df["fuente"] + "|" + df["codigo"] + "|" + df["modelo"]).isin(base_keys)].copy()

    def row_tokens_from_oem_norm(row):
        return split_oem_tokens_reales(row.get("oem_norm", ""))

    def match_row(row):
        row_tokens = row_tokens_from_oem_norm(row)
        return " | ".join(sorted(row_tokens & set(tokens)))

    df["match_oem"] = df.apply(match_row, axis=1)
    df = df[df["match_oem"].str.strip().ne("")]
    return df.drop_duplicates()


def preparar_columnas(df: pd.DataFrame, equivalencias=False) -> pd.DataFrame:
    if df.empty:
        return df
    cols = DISPLAY_COLUMNS.copy()
    if equivalencias and "match_oem" in df.columns:
        cols.append("match_oem")
    cols = [c for c in cols if c in df.columns and (df[c].astype(str).str.strip().ne("").any() or c in ["fuente", "codigo", "marca", "modelo", "producto"])]
    out = df[cols].copy().drop_duplicates()
    rename = {
        "imagen_producto": "Imagen",
        "url_ficha": "Ficha",
        "match_oem": "Coincidencia OEM",
        "ficha_medidas": "Medidas",
        "diametro_int": "Ø int",
        "diametro_ext": "Ø ext",
        "altura": "Altura",
        "abs": "ABS",
        "estrias_externas": "Estrías externas",
        "estrias_internas": "Estrías internas",
        "estrias_lado_rueda": "Estrías lado rueda",
        "estrias_lado_caja": "Estrías lado caja",
        "longitud_semieje": "Longitud semieje",
        "longitud_cardan": "Longitud cardán",
        "longitud_punta_eje": "Longitud punta eje",
        "diametro_asiento": "Diám. asiento",
        "diametro_asiento_lado_rueda": "Diám. asiento rueda",
        "diametro_jh": "Diám. JH",
        "diametro_junta_homocinetica": "Diám. junta homocinética",
        "diametro_jh_deslizante": "Diám. JH deslizante",
        "altura_jh": "Altura JH",
        "altura_punta_eje": "Altura punta eje",
        "diametro_circunferencia_agujeros": "Diám. circ. agujeros",
        "rosca_agujeros": "Rosca agujeros",
        "diametro_rodamiento": "Diám. rodamiento",
        "diametro_menor": "Diám. menor",
        "seguro": "Seguro",
        "pieza": "Pieza",
        "descripcion": "Descripción",
        "posicion": "Posición",
        "lado": "Lado",
        "anio": "Año",
        "oem": "OEM",
        "categoria": "Categoría fuelle",
        "boca_chica": "Boca chica (mm)",
        "boca_grande": "Boca grande (mm)",
        "largo": "Largo (mm)",
    }
    return out.rename(columns=rename)

def mostrar_bloque(titulo: str, df: pd.DataFrame, equivalencias=False):
    st.markdown(f"### {titulo}")
    total = len(df)
    if df.empty:
        st.info("No hay resultados para esta selección.")
        return

    # Paginación
    safe_key = re.sub(r"[^a-zA-Z0-9]", "_", titulo) + ("_eq" if equivalencias else "")
    page_key = f"pag_{safe_key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 0
    total_pages = max(1, math.ceil(total / PAGE_DISPLAY))
    page = min(st.session_state[page_key], total_pages - 1)
    st.session_state[page_key] = page
    start_idx = page * PAGE_DISPLAY
    end_idx = min(start_idx + PAGE_DISPLAY, total)
    df_page = df.iloc[start_idx:end_idx]

    # Fila de controles: códigos | CSV | navegación
    c1, c2, c3 = st.columns([2, 1, 2])
    with c1:
        codigos = "\n".join(df["codigo"].dropna().astype(str).drop_duplicates().tolist())
        st.caption(f"Resultados: {total:,}".replace(",", "."))
        with st.expander("Copiar códigos", expanded=False):
            st.text_area("Códigos encontrados", codigos, height=100, key=f"cod_{safe_key}")
    with c2:
        csv_bytes = preparar_columnas(df, equivalencias=equivalencias).to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Descargar CSV",
            data=csv_bytes,
            file_name=f"{titulo.replace(' ', '_')}.csv",
            mime="text/csv",
            key=f"csv_{safe_key}",
        )
    with c3:
        if total_pages > 1:
            pc1, pc2, pc3 = st.columns([1, 2, 1])
            with pc1:
                if page > 0 and st.button("← Ant.", key=f"prev_{safe_key}"):
                    st.session_state[page_key] = page - 1
                    st.rerun()
            with pc2:
                st.caption(f"Pág. {page + 1} / {total_pages}  ({start_idx + 1}–{end_idx})")
            with pc3:
                if page < total_pages - 1 and st.button("Sig. →", key=f"next_{safe_key}"):
                    st.session_state[page_key] = page + 1
                    st.rerun()

    st.dataframe(
        preparar_columnas(df_page, equivalencias=equivalencias),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Imagen": st.column_config.ImageColumn("Imagen", width="small"),
            "Ficha": st.column_config.LinkColumn("Ficha"),
        },
    )

if not supabase_ready():
    st.error("Faltan SUPABASE_URL o SUPABASE_KEY en Streamlit Secrets.")
    st.stop()

st.title("🔎 Catálogo MIPOL")
st.caption("Buscador interno conectado a Supabase.")

proveedores_cache = load_proveedores_cache()

with st.sidebar:
    st.header("Filtros")

    col_act, col_lim = st.columns(2)
    with col_act:
        if st.button("Actualizar filtros", help="Usalo después de cargar datos nuevos en Supabase."):
            st.cache_data.clear()
            st.rerun()
    with col_lim:
        if st.button("Limpiar filtros", help="Resetea todos los filtros al estado inicial."):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    proveedores = ["Todos"] + proveedores_cache
    catalogo = st.radio("Proveedor", proveedores, horizontal=False)

    # Textos primero. No disparan búsqueda hasta tocar el botón Buscar.
    q = st.text_input("Búsqueda general", placeholder="Ej: Corsa, Agile, WR110, 30003, semieje...")
    codigo = st.text_input("Código", placeholder="Ej: 4302, WR-110, KWD1072")
    oem = st.text_input("OEM / referencia", placeholder="Ej: 90495169, 22.650.18")

    buscar_oem = st.checkbox(
        "Mostrar equivalencias por OEM en otros proveedores",
        value=False,
        help="Más rápido desactivado. Activarlo sólo cuando ya encontraste el producto base.",
    )

    # Filtros perezosos: se cargan según proveedor/producto/marca/modelo.
    df_opciones = load_filter_cache(catalogo)

    producto = st.selectbox("Producto", ["Todos"] + select_options(df_opciones, "familia"))
    df_opciones = load_filter_cache(catalogo, producto)

    marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df_opciones, "marca"))
    df_opciones = load_filter_cache(catalogo, producto, marca)

    modelo = st.selectbox("Modelo", ["Todos"] + select_options(df_opciones, "modelo"))
    df_opciones = load_filter_cache(catalogo, producto, marca, modelo)

    st.divider()
    posicion = st.selectbox("Posición", ["Todos"] + select_options(df_opciones, "posicion"))
    lado = st.selectbox("Lado", ["Todos"] + select_options(df_opciones, "lado"))

    # Filtros técnicos dinámicos
    # Se activan por producto elegido o por las familias disponibles del proveedor seleccionado.
    prod_norm = norm(producto)
    familias_norm = " ".join(norm(x) for x in select_options(df_opciones, "familia"))
    productos_norm = " ".join(norm(x) for x in select_options(df_opciones, "producto"))
    contexto_tecnico = " ".join([prod_norm, familias_norm, productos_norm, norm(catalogo)])

    es_rodamiento = "RODAMIENTO" in contexto_tecnico
    es_homocinetica = any(x in contexto_tecnico for x in [
        "HOMOCINETICA", "HOMOCINETICAS", "SEMIEJE", "SEMIEJES", "CARDAN", "EJECARDANICO",
        "EJEINTERMEDIO", "JUNTASCARDANICAS"
    ])
    es_fuelle = "FUELLE" in contexto_tecnico

    if es_rodamiento:
        st.divider()
        st.subheader("Medidas rodamiento")
        diametro_int = st.selectbox("Ø interior", ["Todos"] + load_column_options("diametro_int_filtro", catalogo, producto, marca, modelo))
        diametro_ext = st.selectbox("Ø exterior", ["Todos"] + load_column_options("diametro_ext_filtro", catalogo, producto, marca, modelo))
        altura = st.selectbox("Altura", ["Todos"] + load_column_options("altura_filtro", catalogo, producto, marca, modelo))
        abs_sel = st.selectbox("ABS", ["Todos"] + load_column_options("abs", catalogo, producto, marca, modelo))
    else:
        diametro_int = "Todos"
        diametro_ext = "Todos"
        altura = "Todos"
        abs_sel = "Todos"

    if es_homocinetica:
        st.divider()
        st.subheader("Medidas homocinética / semieje")
        estrias_ext = st.selectbox("Estrías externas", ["Todos"] + load_column_options("estrias_externas", catalogo, producto, marca, modelo))
        estrias_int = st.selectbox("Estrías internas", ["Todos"] + load_column_options("estrias_internas", catalogo, producto, marca, modelo))
        seguro = st.selectbox("Seguro", ["Todos"] + load_column_options("seguro", catalogo, producto, marca, modelo))
    else:
        estrias_ext = "Todos"
        estrias_int = "Todos"
        seguro = "Todos"

    if es_fuelle:
        st.divider()
        st.subheader("Medidas fuelle")
        categoria_fuelle = st.selectbox("Categoría", ["Todos"] + load_column_options("categoria", catalogo, producto, marca, modelo))
        boca_chica = st.selectbox("Boca chica (mm)", ["Todos"] + load_column_options("boca_chica", catalogo, producto, marca, modelo))
        boca_grande = st.selectbox("Boca grande (mm)", ["Todos"] + load_column_options("boca_grande", catalogo, producto, marca, modelo))
        largo = st.selectbox("Largo (mm)", ["Todos"] + load_column_options("largo", catalogo, producto, marca, modelo))
    else:
        categoria_fuelle = "Todos"
        boca_chica = "Todos"
        boca_grande = "Todos"
        largo = "Todos"

    buscar = st.button("Buscar", type="primary")

# IMPORTANTE: no buscar automáticamente.
# Streamlit recarga la app con cada cambio de filtro; si consultamos en cada recarga, se pone lenta.
hay_filtro = any([
    q, codigo, oem, catalogo != "Todos", producto != "Todos", marca != "Todas",
    modelo != "Todos", posicion != "Todos", lado != "Todos",
    diametro_int != "Todos", diametro_ext != "Todos", altura != "Todos", abs_sel != "Todos",
    estrias_ext != "Todos", estrias_int != "Todos", seguro != "Todos",
    boca_chica != "Todos", boca_grande != "Todos", largo != "Todos", categoria_fuelle != "Todos",
])

if not buscar:
    st.info("Elegí los filtros y tocá **Buscar**. Así evitamos consultar Supabase en cada tecla o cambio.")
    st.stop()

if not hay_filtro:
    st.info("Elegí un proveedor, código, OEM, marca/modelo o producto para buscar.")
    st.stop()

# Reset paginación cuando cambian los parámetros de búsqueda
_search_sig = f"{catalogo}|{q}|{codigo}|{oem}|{producto}|{marca}|{modelo}|{posicion}|{lado}"
if st.session_state.get("_last_search") != _search_sig:
    for k in [k for k in st.session_state if k.startswith("pag_")]:
        del st.session_state[k]
    st.session_state["_last_search"] = _search_sig

try:
    res = query_productos(
        fuente=catalogo,
        q=q,
        codigo=codigo,
        oem=oem,
        producto=producto,
        marca=marca,
        modelo=modelo,
        posicion=posicion,
        lado=lado,
        diametro_int=diametro_int,
        diametro_ext=diametro_ext,
        altura=altura,
        abs_sel=abs_sel,
        estrias_ext=estrias_ext,
        estrias_int=estrias_int,
        seguro=seguro,
        boca_chica=boca_chica,
        boca_grande=boca_grande,
        largo=largo,
        categoria=categoria_fuelle,
        limit=MAX_RESULTS,
    )
except Exception as e:
    st.error(f"Error consultando Supabase: {e}")
    st.stop()

if len(res) >= MAX_RESULTS:
    st.warning(f"Se muestran los primeros {MAX_RESULTS} resultados. Afiná la búsqueda para ver menos y más rápido.")

if catalogo != "Todos":
    mostrar_bloque(catalogo, res)
else:
    total = len(res)
    st.subheader(f"Resultados totales: {total:,}".replace(",", "."))
    for fuente in select_options(res, "fuente"):
        bloque = res[res["fuente"].eq(fuente)].copy()
        if not bloque.empty:
            mostrar_bloque(fuente, bloque)
            st.divider()

if buscar_oem and catalogo == "Todos":
    st.info("Las equivalencias OEM sólo funcionan cuando elegís un proveedor concreto (no \"Todos\").")

if buscar_oem and catalogo != "Todos" and not res.empty:
    # DAUER técnico no trae OEM real. Si lo dejamos cruzar, toma motores/medidas como falsas equivalencias.
    proveedores_sin_oem_real = {"DAUER"}
    if norm(catalogo) in {norm(x) for x in proveedores_sin_oem_real}:
        eq = pd.DataFrame()
        st.caption("Este proveedor no trae OEM real en los datos cargados, por eso no se buscan equivalencias OEM.")
    else:
        try:
            eq = buscar_equivalencias_oem(res, catalogo)
        except Exception as e:
            st.warning(f"No pude buscar equivalencias OEM: {e}")
            eq = pd.DataFrame()

    if not eq.empty:
        st.divider()
        st.subheader(f"Equivalencias por OEM en otros proveedores: {len(eq):,}".replace(",", "."))
        for fuente in select_options(eq, "fuente"):
            bloque = eq[eq["fuente"].eq(fuente)].copy()
            if not bloque.empty:
                mostrar_bloque(f"Equivalencias {fuente}", bloque, equivalencias=True)
                st.divider()
    else:
        st.caption("No se encontraron equivalencias por OEM en otros proveedores.")

st.divider()
st.markdown("""
**Tip:** para equivalencias OEM, elegí un proveedor concreto y buscá por código.  
Ejemplo: Proveedor **REY GOMA** + Código **1216**.
""")
