
import re
import math
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Catálogo MIPOL", page_icon="🔎", layout="wide")

TABLE = "mipol_productos_catalogo"
PAGE_SIZE = 1000
MAX_RESULTS = 1000

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
    "posicion_seguro", "seguro", "peso", "dimensiones", "pieza"
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
    "posicion_seguro", "seguro", "peso", "dimensiones",

    "ficha_medidas", "imagen_producto", "url_ficha"
]

def limpiar(txt: str) -> str:
    return re.sub(r"\s+", " ", str(txt or "").replace("\ufeff", "")).strip()

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
        timeout=45,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Supabase error {r.status_code}: {r.text[:500]}")
    return r.json(), r.headers.get("content-range", "")

@st.cache_data(ttl=3600, show_spinner="Cargando filtros desde Supabase...")
def load_filter_cache():
    """Carga columnas livianas para armar filtros. No carga imágenes ni textos largos."""
    if not supabase_ready():
        return pd.DataFrame()

    cols = "fuente,marca,modelo,familia,producto,posicion,lado,diametro_int_filtro,diametro_ext_filtro,altura_filtro,abs,estrias_externas,estrias_internas,estrias_lado_rueda,estrias_lado_caja,seguro,posicion_seguro"
    all_rows = []
    start = 0
    while True:
        data, cr = supabase_get({"select": cols, "order": "fuente.asc"}, start, start + PAGE_SIZE - 1)
        if not data:
            break
        all_rows.extend(data)
        if len(data) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        if start > 100000:
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

    if codigo:
        params["codigo"] = f"ilike.*{codigo}*"

    if oem:
        oem_norm = normalizar_oem_token(oem)
        if oem_norm:
            params["or"] = f"(oem_norm.ilike.*{oem_norm}*,oem.ilike.*{oem}*,ficha_oem.ilike.*{oem}*)"

    if q:
        qsafe = q.replace(",", " ").replace(")", " ").replace("(", " ")
        # búsqueda general en columnas principales
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


def split_oem_norm_cell(txt: str) -> set[str]:
    """Toma oem_norm, pero descarta basura generada desde descripción/info.
    Ej válido:
      '90495169 | 93201397' -> {'90495169', '93201397'}
    Ej inválido:
      'SOPORTEDEMOTOR' -> descartado
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
        n = normalizar_oem_token(p)
        if not n:
            continue

        # Descartar palabras de producto o ubicación.
        if n in basura:
            continue

        # Descartar tokens compuestos de palabras comunes.
        if any(b in n for b in [
            "SOPORTE", "BUJE", "MOTOR", "DERECHO", "IZQUIERDO",
            "DELANTERO", "TRASERO", "HIDRAULICO", "AMORTIGUADOR"
        ]):
            continue

        # OEM numérico: mínimo 6 dígitos.
        if n.isdigit():
            if len(n) < 6:
                continue
            out.add(n)
            out.add(n.lstrip("0") or n)
            continue

        # OEM alfanumérico: debe tener números y letras.
        # Ej: 96FX3290AA, 25C63280LB.
        # Evitamos motores/versiones como 20DURATEC, 16V, 18TD, etc.
        if any(x in n for x in ["DURATEC", "TURBO", "DIESEL", "NAFTA", "MOTOR", "VALVULAS"]):
            continue
        if re.fullmatch(r"\d{1,2}V", n):
            continue
        if re.fullmatch(r"\d{1,2}(TD|TDI|HDI|MPI|V|I|L)", n):
            continue
        tiene_letra = bool(re.search(r"[A-Z]", n))
        tiene_numero = bool(re.search(r"\d", n))
        if tiene_letra and tiene_numero and len(n) >= 6:
            out.add(n)

    return out

def buscar_equivalencias_oem(res_base: pd.DataFrame, fuente_actual: str) -> pd.DataFrame:
    """Busca equivalencias usando SOLO oem_norm, para evitar timeout.
    Ya no escanea descripción/info porque eso genera consultas enormes.
    """
    if res_base.empty or "oem_norm" not in res_base.columns:
        return pd.DataFrame(columns=COLUMNS + ["match_oem"])

    tokens = set()
    for _, row in res_base.iterrows():
        tokens |= split_oem_norm_cell(row.get("oem_norm", ""))

    if not tokens:
        return pd.DataFrame(columns=COLUMNS + ["match_oem"])

    # Máximo razonable para evitar consultas REST gigantes
    tokens = sorted(tokens)[:20]

    # Como oem_norm puede contener "90495169 | 93201397", usamos ilike por token,
    # pero sólo sobre oem_norm y con pocos tokens.
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

    # quitar resultados ya presentes
    base_keys = set((res_base["fuente"] + "|" + res_base["codigo"] + "|" + res_base["modelo"]).tolist())
    df = df[~(df["fuente"] + "|" + df["codigo"] + "|" + df["modelo"]).isin(base_keys)].copy()

    def match_row(row):
        row_tokens = split_oem_norm_cell(row.get("oem_norm", ""))
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
        "posicion_seguro": "Posición seguro",
        "seguro": "Seguro",
        "pieza": "Pieza",
        "descripcion": "Descripción",
        "posicion": "Posición",
        "lado": "Lado",
        "anio": "Año",
        "oem": "OEM",
    }
    return out.rename(columns=rename)

def mostrar_bloque(titulo: str, df: pd.DataFrame, equivalencias=False):
    st.markdown(f"### {titulo}")
    st.caption(f"Resultados: {len(df):,}".replace(",", "."))
    if df.empty:
        st.info("No hay resultados para esta selección.")
        return

    codigos = "\n".join(df["codigo"].dropna().astype(str).drop_duplicates().tolist())
    with st.expander("Copiar códigos", expanded=False):
        st.text_area("Códigos encontrados", codigos, height=120, key=f"codigos_{titulo}_{equivalencias}")

    st.dataframe(
        preparar_columnas(df, equivalencias=equivalencias),
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

filtros_df = load_filter_cache()

with st.sidebar:
    st.header("Filtros")

    proveedores = ["Todos"] + select_options(filtros_df, "fuente")
    catalogo = st.radio("Proveedor", proveedores, horizontal=False)

    df_opciones = filtros_df.copy()
    if catalogo != "Todos":
        df_opciones = df_opciones[df_opciones["fuente"].eq(catalogo)].copy()

    q = st.text_input("Búsqueda general", placeholder="Ej: Corsa, Agile, WR110, 30003, semieje...")
    codigo = st.text_input("Código", placeholder="Ej: 4302, WR-110, KWD1072")
    oem = st.text_input("OEM / referencia", placeholder="Ej: 90495169, 22.650.18")

    buscar_oem = st.checkbox(
        "Mostrar equivalencias por OEM en otros proveedores",
        value=True,
        help="Funciona mejor eligiendo un proveedor concreto. Normaliza 2265018 = 22.650.18 = 22 65 01 8.",
    )

    producto = st.selectbox("Producto", ["Todos"] + select_options(df_opciones, "familia"))
    if producto != "Todos":
        df_opciones = df_opciones[df_opciones["familia"].eq(producto)].copy()

    marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df_opciones, "marca"))
    if marca != "Todas":
        df_opciones = df_opciones[df_opciones["marca"].eq(marca)].copy()

    modelo = st.selectbox("Modelo", ["Todos"] + select_options(df_opciones, "modelo"))
    if modelo != "Todos":
        df_opciones = df_opciones[df_opciones["modelo"].eq(modelo)].copy()

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

    if es_rodamiento:
        st.divider()
        st.subheader("Medidas rodamiento")
        diametro_int = st.selectbox("Ø interior", ["Todos"] + select_options(df_opciones, "diametro_int_filtro"))
        diametro_ext = st.selectbox("Ø exterior", ["Todos"] + select_options(df_opciones, "diametro_ext_filtro"))
        altura = st.selectbox("Altura", ["Todos"] + select_options(df_opciones, "altura_filtro"))
        abs_sel = st.selectbox("ABS", ["Todos"] + select_options(df_opciones, "abs"))
    else:
        diametro_int = "Todos"
        diametro_ext = "Todos"
        altura = "Todos"
        abs_sel = "Todos"

    if es_homocinetica:
        st.divider()
        st.subheader("Medidas homocinética / semieje")
        estrias_ext = st.selectbox("Estrías externas", ["Todos"] + select_options(df_opciones, "estrias_externas"))
        estrias_int = st.selectbox("Estrías internas", ["Todos"] + select_options(df_opciones, "estrias_internas"))
        seguro = st.selectbox("Seguro", ["Todos"] + select_options(df_opciones, "seguro"))
    else:
        estrias_ext = "Todos"
        estrias_int = "Todos"
        seguro = "Todos"

    buscar = st.button("Buscar", type="primary")

# Ejecuta automáticamente si hay algún filtro usado, o si presionan buscar.
hay_filtro = any([
    q, codigo, oem, catalogo != "Todos", producto != "Todos", marca != "Todas",
    modelo != "Todos", posicion != "Todos", lado != "Todos",
    diametro_int != "Todos", diametro_ext != "Todos", altura != "Todos", abs_sel != "Todos",
    estrias_ext != "Todos", estrias_int != "Todos", seguro != "Todos"
])

if not hay_filtro and not buscar:
    st.info("Elegí un proveedor, código, OEM, marca/modelo o producto para buscar.")
    st.stop()

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
        limit=MAX_RESULTS,
    )
except Exception as e:
    st.error(f"Error consultando Supabase: {e}")
    st.stop()

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
