import os
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Catálogo MIPOL", page_icon="🔎", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

FUENTES = {
    "TIPER": ("aplicaciones.csv", "fichas.csv"),
    "WEGA": ("wega_aplicaciones.csv", "wega_fichas.csv"),
    "VTH": ("vth_aplicaciones.csv", "vth_fichas.csv"),
    "DAUER": ("dauer_aplicaciones.csv", "dauer_fichas.csv"),
}

TECNICAS = [
    "estrias_externas", "estrias_internas", "estrias_lado_rueda", "estrias_lado_caja",
    "longitud_semieje", "longitud_cardan", "longitud_punta_eje",
    "diametro_asiento", "diametro_asiento_lado_rueda",
    "diametro_jh", "diametro_junta_homocinetica", "diametro_jh_deslizante",
    "altura_jh", "altura_punta_eje",
    "diametro_circunferencia_agujeros", "rosca_agujeros",
    "diametro_rodamiento", "diametro_menor",
    "abs", "posicion_seguro", "seguro", "lado", "peso", "dimensiones",
]

NOMBRES_TECNICAS = {
    "estrias_externas": "Estrías externas",
    "estrias_internas": "Estrías internas",
    "estrias_lado_rueda": "Estrías lado rueda",
    "estrias_lado_caja": "Estrías lado caja",
    "longitud_semieje": "Longitud semieje",
    "longitud_cardan": "Longitud cardan",
    "longitud_punta_eje": "Longitud punta eje",
    "diametro_asiento": "Diám. asiento",
    "diametro_asiento_lado_rueda": "Diám. asiento lado rueda",
    "diametro_jh": "Diám. JH",
    "diametro_junta_homocinetica": "Diám. junta homocinética",
    "diametro_jh_deslizante": "Diám. JH deslizante",
    "altura_jh": "Altura JH",
    "altura_punta_eje": "Altura punta eje",
    "diametro_circunferencia_agujeros": "Diám. circ. agujeros",
    "rosca_agujeros": "Rosca agujeros",
    "diametro_rodamiento": "Diám. rodamiento",
    "diametro_menor": "Diám. menor",
    "abs": "ABS",
    "posicion_seguro": "Posición seguro",
    "seguro": "Seguro",
    "lado": "Lado",
    "peso": "Peso",
    "dimensiones": "Dimensiones",
}

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

def limpiar(txt: str) -> str:
    return re.sub(r"\s+", " ", str(txt or "").replace("\ufeff", "")).strip()

def familia_producto(txt: str) -> str:
    t = limpiar(txt).upper()
    tn = norm(t)

    reglas = [
        # TIPER / suspensión
        ("ROTULA DE SUSPENSION", ["ROTULA"]),
        ("PRECAP", ["PRECAP"]),
        ("BIELETA", ["BIELETA"]),
        ("EXTREMO", ["EXTREMO"]),
        ("AXIAL", ["AXIAL"]),
        ("PARRILLA", ["PARRILLA", "BANDEJA"]),
        ("BUJE", ["BUJE"]),
        ("BRAZO", ["BRAZO"]),
        ("SOPORTE", ["SOPORTE"]),
        ("CAZOLETA", ["CAZOLETA"]),
        ("CRAPODINA", ["CRAPODINA"]),
        ("AMORTIGUADOR", ["AMORTIGUADOR"]),
        ("ESPIRAL", ["ESPIRAL"]),

        # WEGA / filtros
        ("FILTRO DE AIRE", ["FILTRODEAIRE", "AIRE"]),
        ("FILTRO DE ACEITE", ["FILTRODEACEITE", "ACEITE"]),
        ("FILTRO DE COMBUSTIBLE", ["FILTRODECOMBUSTIBLE", "COMBUSTIBLE"]),
        ("FILTRO DE HABITACULO", ["FILTRODEHABITACULO", "HABITACULO", "CABINA"]),
        ("TRAMPA DE AGUA", ["TRAMPADEAGUA"]),
        ("HIDRAULICO", ["HIDRAULICO"]),
        ("CAJA AUTOMATICA", ["CAJAAUTOMATICA", "CAJAAUTOMÁTICA"]),
        ("ACCESORIOS", ["ACCESORIOS"]),
        ("KITS", ["KITS", "KIT"]),

        # DAUER / transmisión
        ("EJE CARDANICO", ["EJECARDANICO", "CARDAN"]),
        ("SEMIEJE", ["SEMIEJE"]),
        ("JUNTA HOMOCINETICA", ["JUNTAHOMOCINETICA", "HOMOCINETICA"]),
        ("JUNTA DESLIZANTE", ["JUNTADESLIZANTE", "DESLIZANTE"]),
        ("PUNTA DE EJE", ["PUNTADEEJE"]),
        ("TRICETA", ["TRICETA"]),
    ]

    for familia, palabras in reglas:
        if any(p in tn for p in palabras):
            return familia

    return t

def read_csv_any(path: str) -> pd.DataFrame:
    """Lee CSV normal; si viene separado por ; también lo detecta."""
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return pd.read_csv(path, dtype=str, sep=";").fillna("")

def read_csv_if_exists(filename: str, columns: list[str], fuente: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)

    df = read_csv_any(path)
    for col in columns:
        if col not in df.columns:
            df[col] = ""

    df = df[columns].copy()
    df["fuente"] = df["fuente"].replace("", fuente)
    df.loc[df["fuente"].eq(""), "fuente"] = fuente
    return df

@st.cache_data(show_spinner="Cargando catálogo MIPOL...")
def load_data():
    app_cols = [
        "codigo", "producto", "marca", "modelo", "anio", "info", "oem",
        "ficha_medidas", "ficha_oem", "ficha_info",
        "imagen_producto", "url_ficha", "fuente", "titulo", "categoria",
    ] + TECNICAS

    ficha_cols = [
        "codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem",
        "ficha_medidas", "imagen_producto", "url_ficha", "fuente", "titulo", "categoria",
    ] + TECNICAS

    aplicaciones_lista = []
    fichas_lista = []
    for fuente, (archivo_app, archivo_ficha) in FUENTES.items():
        aplicaciones_lista.append(read_csv_if_exists(archivo_app, app_cols, fuente))
        fichas_lista.append(read_csv_if_exists(archivo_ficha, ficha_cols, fuente))

    aplicaciones = pd.concat(aplicaciones_lista, ignore_index=True)
    fichas = pd.concat(fichas_lista, ignore_index=True)

    for df in (aplicaciones, fichas):
        for col in df.columns:
            df[col] = df[col].astype(str).fillna("").map(limpiar)

        if "codigo" in df.columns:
            df["codigo"] = df["codigo"].str.replace(r"\.0$", "", regex=True)

        if "producto" in df.columns:
            df["familia"] = df["producto"].apply(familia_producto)

        for col in ["fuente", "familia", "marca", "modelo", "codigo"]:
            if col in df.columns:
                df[f"{col}_norm"] = df[col].map(norm)

    return aplicaciones, fichas

def contains_norm(series: pd.Series, term: str) -> pd.Series:
    t = norm(term)
    if not t:
        return pd.Series(True, index=series.index)
    return series.astype(str).map(norm).str.contains(t, na=False)

def text_search(df: pd.DataFrame, query: str, cols: list[str]) -> pd.Series:
    q = norm(query)
    if not q:
        return pd.Series(True, index=df.index)

    available_cols = [c for c in cols if c in df.columns]
    if not available_cols:
        return pd.Series(False, index=df.index)

    joined = df[available_cols].astype(str).agg(" ".join, axis=1).map(norm)
    return joined.str.contains(q, na=False)

def sort_valor_tecnico(x: str):
    x = limpiar(x)
    try:
        return (0, float(x.replace(",", ".")))
    except Exception:
        return (1, norm(x))

def select_options(df: pd.DataFrame, col: str) -> list[str]:
    if col not in df.columns:
        return []
    vals = [limpiar(v) for v in df[col].dropna().astype(str).unique() if limpiar(v)]
    return sorted(set(vals), key=lambda x: norm(x))

def select_options_tecnico(df: pd.DataFrame, col: str) -> list[str]:
    if col not in df.columns:
        return []
    vals = [limpiar(v) for v in df[col].dropna().astype(str).unique() if limpiar(v)]
    return sorted(set(vals), key=sort_valor_tecnico)

def filtrar_tecnico(df: pd.DataFrame, col: str, value: str) -> pd.Series:
    if value in ["Todos", "Todas", ""] or col not in df.columns:
        return pd.Series(True, index=df.index)
    return df[col].astype(str).map(limpiar).map(norm).eq(norm(value))

def filtrar_por_display(df: pd.DataFrame, col: str, value: str, todos: str) -> pd.Series:
    if value == todos or col not in df.columns:
        return pd.Series(True, index=df.index)
    norm_col = f"{col}_norm"
    if norm_col in df.columns:
        return df[norm_col].eq(norm(value))
    return df[col].map(norm).eq(norm(value))

def filtrar_fuente(df: pd.DataFrame, catalogo: str) -> pd.DataFrame:
    if catalogo in ["Todos", "Ambos"]:
        return df
    return df[df["fuente_norm"].eq(norm(catalogo))].copy()

def fuentes_disponibles(df: pd.DataFrame) -> list[str]:
    vals = select_options(df, "fuente")
    orden = ["TIPER", "WEGA", "VTH", "DAUER"]
    return [x for x in orden if x in vals] + [x for x in vals if x not in orden]

def preparar_columnas(res: pd.DataFrame, modo: str) -> pd.DataFrame:
    es_dauer = False
    if not res.empty and "fuente_norm" in res.columns:
        fuentes = set(res["fuente_norm"].dropna().astype(str).unique())
        es_dauer = fuentes == {"DAUER"}

    if modo == "Aplicaciones":
        if es_dauer:
            cols = [
                "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
                "info", "oem",
            ] + TECNICAS + ["imagen_producto", "url_ficha"]
        else:
            cols = [
                "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
                "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info",
            ] + TECNICAS + ["imagen_producto", "url_ficha"]
    else:
        if es_dauer:
            cols = [
                "fuente", "codigo", "familia", "producto", "ficha_anio",
            ] + TECNICAS + ["imagen_producto", "url_ficha"]
        else:
            cols = [
                "fuente", "codigo", "familia", "producto", "ficha_anio",
                "ficha_info", "ficha_oem", "ficha_medidas",
            ] + TECNICAS + ["imagen_producto", "url_ficha"]

    cols = [c for c in cols if c in res.columns and (res[c].astype(str).str.strip().ne("").any() or c in ["fuente", "codigo", "familia", "producto", "marca", "modelo"])]
    out = res[cols].copy().drop_duplicates()

    rename = {c: NOMBRES_TECNICAS[c] for c in TECNICAS if c in out.columns}
    return out.rename(columns=rename)

def mostrar_bloque(titulo: str, df: pd.DataFrame, modo: str):
    st.markdown(f"### {titulo}")
    st.caption(f"Resultados: {len(df):,}".replace(",", "."))

    if df.empty:
        st.info("No hay resultados para esta selección.")
        return

    codigos = "\n".join(df["codigo"].dropna().astype(str).drop_duplicates().tolist())
    with st.expander("Copiar códigos", expanded=False):
        st.text_area(
            "Códigos encontrados",
            codigos,
            height=120,
            key=f"codigos_{titulo}_{modo}",
        )

    st.dataframe(
        preparar_columnas(df, modo),
        use_container_width=True,
        hide_index=True,
        column_config={
            "imagen_producto": st.column_config.ImageColumn("Imagen", width="small"),
            "url_ficha": st.column_config.LinkColumn("Ficha"),
        },
    )

aplicaciones, fichas = load_data()

st.title("🔎 Catálogo MIPOL")
st.caption("Buscador interno con datos por proveedor. Los filtros se ajustan al catálogo seleccionado.")

with st.sidebar:
    st.header("Filtros")
    modo = st.radio("Buscar por", ["Aplicaciones", "Fichas/códigos"], horizontal=False)

    base_df = aplicaciones if modo == "Aplicaciones" else fichas
    disponibles = fuentes_disponibles(base_df)
    opciones_catalogo = ["Todos"] + disponibles

    # IMPORTANTE: primero se elige proveedor; después recién se arman productos/marcas/modelos.
    catalogo = st.radio(
        "Proveedor",
        opciones_catalogo,
        horizontal=False,
        help="Si elegís TIPER, solo aparecen productos/marcas/modelos de TIPER. No se mezclan filtros con WEGA, VTH o DAUER.",
    )

    base_filtrada = filtrar_fuente(base_df, catalogo)

    q = st.text_input("Búsqueda general", placeholder="Ej: Corsa, Agile, WR110, 30003, semieje, 22 estrías...")
    codigo = st.text_input("Código", placeholder="Ej: 30003, WR-110, ECA-AD0001")
    oem = st.text_input("OEM / referencia", placeholder="Ej: 68105872AA, 90486296")

    df_opciones = base_filtrada.copy()

    producto = st.selectbox("Producto", ["Todos"] + select_options(df_opciones, "familia"))
    if producto != "Todos":
        df_opciones = df_opciones[df_opciones["familia_norm"].eq(norm(producto))]

    if modo == "Aplicaciones":
        marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df_opciones, "marca"))
        if marca != "Todas":
            df_opciones = df_opciones[df_opciones["marca_norm"].eq(norm(marca))]

        modelo = st.selectbox("Modelo", ["Todos"] + select_options(df_opciones, "modelo"))
        if modelo != "Todos":
            df_opciones = df_opciones[df_opciones["modelo_norm"].eq(norm(modelo))]
    else:
        marca = "Todas"
        modelo = "Todos"

    # Filtros técnicos exclusivos de DAUER.
    # No aparecen en TIPER/WEGA/VTH para no mezclar proveedores ni ensuciar la búsqueda.
    if catalogo == "DAUER":
        st.divider()
        st.subheader("Medidas DAUER")
        estrias_externas_sel = st.selectbox(
            "Estrías externas",
            ["Todos"] + select_options_tecnico(df_opciones, "estrias_externas"),
        )
        estrias_internas_sel = st.selectbox(
            "Estrías internas",
            ["Todos"] + select_options_tecnico(df_opciones, "estrias_internas"),
        )
        seguro_sel = st.selectbox(
            "Seguro / traba",
            ["Todos"] + select_options_tecnico(df_opciones, "seguro"),
            help="Filtra valores como Externo, Interno o Medio si DAUER los trae.",
        )
        posicion_seguro_sel = st.selectbox(
            "Posición seguro / traba",
            ["Todos"] + select_options_tecnico(df_opciones, "posicion_seguro"),
        )
        lado_sel = st.selectbox(
            "Lado",
            ["Todos"] + select_options_tecnico(df_opciones, "lado"),
        )
    else:
        estrias_externas_sel = "Todos"
        estrias_internas_sel = "Todos"
        seguro_sel = "Todos"
        posicion_seguro_sel = "Todos"
        lado_sel = "Todos"

df = aplicaciones.copy() if modo == "Aplicaciones" else fichas.copy()
df = filtrar_fuente(df, catalogo)

mask = pd.Series(True, index=df.index)

search_cols_tecnicas = TECNICAS + ["titulo", "categoria"]

if q:
    if modo == "Aplicaciones":
        mask &= text_search(df, q, [
            "codigo", "producto", "familia", "marca", "modelo", "anio",
            "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info", "fuente",
        ] + search_cols_tecnicas)
    else:
        mask &= text_search(df, q, [
            "codigo", "producto", "familia", "ficha_anio",
            "ficha_info", "ficha_oem", "ficha_medidas", "fuente",
        ] + search_cols_tecnicas)

if codigo:
    mask &= contains_norm(df["codigo"], codigo)

if oem:
    if modo == "Aplicaciones":
        mask &= text_search(df, oem, ["oem", "ficha_oem"])
    else:
        mask &= contains_norm(df["ficha_oem"], oem)

if producto != "Todos":
    mask &= filtrar_por_display(df, "familia", producto, "Todos")

if modo == "Aplicaciones":
    if marca != "Todas":
        mask &= filtrar_por_display(df, "marca", marca, "Todas")
    if modelo != "Todos":
        mask &= filtrar_por_display(df, "modelo", modelo, "Todos")

if catalogo == "DAUER":
    mask &= filtrar_tecnico(df, "estrias_externas", estrias_externas_sel)
    mask &= filtrar_tecnico(df, "estrias_internas", estrias_internas_sel)
    mask &= filtrar_tecnico(df, "seguro", seguro_sel)
    mask &= filtrar_tecnico(df, "posicion_seguro", posicion_seguro_sel)
    mask &= filtrar_tecnico(df, "lado", lado_sel)

res = df[mask].copy()

if catalogo != "Todos":
    st.subheader(f"Resultados {catalogo}: {len(res):,}".replace(",", "."))
    mostrar_bloque(catalogo, res, modo)
else:
    total = len(res)
    st.subheader(f"Resultados totales: {total:,}".replace(",", "."))
    for fuente in disponibles:
        bloque = res[res["fuente_norm"].eq(norm(fuente))].copy()
        if not bloque.empty:
            mostrar_bloque(fuente, bloque, modo)
            st.divider()

st.divider()
st.markdown("""
**Tip de uso:** la búsqueda ignora espacios, guiones y mayúsculas. Si elegís DAUER, aparecen filtros técnicos propios: estrías internas/externas, seguro/traba, posición del seguro y lado.
""")
