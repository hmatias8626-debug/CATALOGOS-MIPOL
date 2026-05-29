import os
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Catálogo MIPOL", page_icon="🔎", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


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
    return re.sub(r"\s+", " ", str(txt or "")).strip()


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
    ]

    for familia, palabras in reglas:
        if any(p in tn for p in palabras):
            return familia

    return t


def read_csv_if_exists(filename: str, columns: list[str], fuente: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)

    df = pd.read_csv(path, dtype=str).fillna("")
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
        "imagen_producto", "url_ficha", "fuente"
    ]
    ficha_cols = [
        "codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem",
        "ficha_medidas", "imagen_producto", "url_ficha", "fuente"
    ]

    aplicaciones = pd.concat([
        read_csv_if_exists("aplicaciones.csv", app_cols, "TIPER"),
        read_csv_if_exists("wega_aplicaciones.csv", app_cols, "WEGA"),
    ], ignore_index=True)

    fichas = pd.concat([
        read_csv_if_exists("fichas.csv", ficha_cols, "TIPER"),
        read_csv_if_exists("wega_fichas.csv", ficha_cols, "WEGA"),
    ], ignore_index=True)

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


def select_options(df: pd.DataFrame, col: str) -> list[str]:
    if col not in df.columns:
        return []
    vals = [limpiar(v) for v in df[col].dropna().astype(str).unique() if limpiar(v)]
    return sorted(set(vals), key=lambda x: norm(x))


def filtrar_por_display(df: pd.DataFrame, col: str, value: str, todos: str) -> pd.Series:
    if value == todos or col not in df.columns:
        return pd.Series(True, index=df.index)
    norm_col = f"{col}_norm"
    if norm_col in df.columns:
        return df[norm_col].eq(norm(value))
    return df[col].map(norm).eq(norm(value))


def preparar_columnas(res: pd.DataFrame, modo: str) -> pd.DataFrame:
    if modo == "Aplicaciones":
        cols = [
            "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
            "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info",
            "imagen_producto", "url_ficha"
        ]
    else:
        cols = [
            "fuente", "codigo", "familia", "producto", "ficha_anio",
            "ficha_info", "ficha_oem", "ficha_medidas",
            "imagen_producto", "url_ficha"
        ]

    cols = [c for c in cols if c in res.columns]
    out = res[cols].copy()
    out = out.drop_duplicates()
    return out


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
st.caption("Buscador interno con datos TIPER + WEGA. Mismos filtros, resultados separados por catálogo cuando hace falta.")

with st.sidebar:
    st.header("Filtros")
    modo = st.radio("Buscar por", ["Aplicaciones", "Fichas/códigos"], horizontal=False)

    base_df = aplicaciones if modo == "Aplicaciones" else fichas

    q = st.text_input("Búsqueda general", placeholder="Ej: Corsa, Agile, WR110, 30003, bieleta...")
    codigo = st.text_input("Código", placeholder="Ej: 30003, WR-110, FAP2827")
    oem = st.text_input("OEM / referencia", placeholder="Ej: 68105872AA, 90486296")

    # Cascada simple para que no muestre familias que después no pueden devolver nada.
    df_opciones = base_df.copy()

    producto = st.selectbox("Producto", ["Todos"] + select_options(df_opciones, "familia"))
    if producto != "Todos":
        df_opciones = df_opciones[df_opciones["familia_norm"].eq(norm(producto))]

    if modo == "Aplicaciones":
        marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df_opciones, "marca"))
        if marca != "Todas":
            df_opciones = df_opciones[df_opciones["marca_norm"].eq(norm(marca))]

        modelo = st.selectbox("Modelo", ["Todos"] + select_options(df_opciones, "modelo"))
    else:
        marca = "Todas"
        modelo = "Todos"


df = aplicaciones.copy() if modo == "Aplicaciones" else fichas.copy()

mask = pd.Series(True, index=df.index)

if q:
    if modo == "Aplicaciones":
        mask &= text_search(df, q, [
            "codigo", "producto", "familia", "marca", "modelo", "anio",
            "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info", "fuente"
        ])
    else:
        mask &= text_search(df, q, [
            "codigo", "producto", "familia", "ficha_anio",
            "ficha_info", "ficha_oem", "ficha_medidas", "fuente"
        ])

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

res = df[mask].copy()

st.markdown("#### Catálogo a mostrar")
catalogo = st.radio(
    "Elegí qué resultados querés ver",
    ["Ambos", "TIPER", "WEGA"],
    horizontal=True,
    label_visibility="collapsed",
)

if catalogo == "TIPER":
    res_tiper = res[res["fuente_norm"].eq("TIPER")].copy()
    st.subheader(f"Resultados TIPER: {len(res_tiper):,}".replace(",", "."))
    mostrar_bloque("TIPER", res_tiper, modo)

elif catalogo == "WEGA":
    res_wega = res[res["fuente_norm"].eq("WEGA")].copy()
    st.subheader(f"Resultados WEGA: {len(res_wega):,}".replace(",", "."))
    mostrar_bloque("WEGA", res_wega, modo)

else:
    res_tiper = res[res["fuente_norm"].eq("TIPER")].copy()
    res_wega = res[res["fuente_norm"].eq("WEGA")].copy()

    total = len(res_tiper) + len(res_wega)
    st.subheader(f"Resultados totales: {total:,}".replace(",", "."))
    mostrar_bloque("TIPER", res_tiper, modo)
    st.divider()
    mostrar_bloque("WEGA", res_wega, modo)

st.divider()
st.markdown("""
**Tip de uso:** la búsqueda ignora espacios, guiones y mayúsculas. Por ejemplo,
`WR-110`, `WR110`, `BA 046`, `BA-046` y `BA046` se tratan parecido.
""")