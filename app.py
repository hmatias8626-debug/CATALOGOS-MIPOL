
import os
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Catálogo TIPER", page_icon="🔎", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

@st.cache_data(show_spinner="Cargando catálogo TIPER...")
def load_data():
    aplicaciones = pd.read_csv(os.path.join(DATA_DIR, "aplicaciones.csv"), dtype=str).fillna("")
    fichas = pd.read_csv(os.path.join(DATA_DIR, "fichas.csv"), dtype=str).fillna("")
    for df in (aplicaciones, fichas):
        for col in df.columns:
            df[col] = df[col].astype(str).fillna("").str.strip()
        if "codigo" in df.columns:
            df["codigo"] = df["codigo"].str.replace(r"\.0$", "", regex=True)
    return aplicaciones, fichas

def norm(txt: str) -> str:
    txt = str(txt or "").upper()
    txt = txt.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    return re.sub(r"[^A-Z0-9]+", "", txt)

def contains_norm(series: pd.Series, term: str) -> pd.Series:
    t = norm(term)
    if not t:
        return pd.Series(True, index=series.index)
    return series.astype(str).map(norm).str.contains(t, na=False)

def text_search(df: pd.DataFrame, query: str, cols: list[str]) -> pd.Series:
    q = norm(query)
    if not q:
        return pd.Series(True, index=df.index)
    joined = df[cols].astype(str).agg(" ".join, axis=1).map(norm)
    return joined.str.contains(q, na=False)

def select_options(df, col):
    if col not in df.columns:
        return []
    vals = sorted(v for v in df[col].dropna().astype(str).str.strip().unique() if v)
    return vals

aplicaciones, fichas = load_data()

st.title("🔎 Catálogo TIPER")
st.caption("Buscador interno creado desde el catálogo scrapeado. Pensado para reemplazar la web cuando no funciona.")

with st.sidebar:
    st.header("Filtros")
    modo = st.radio("Buscar por", ["Aplicaciones", "Fichas/códigos"], horizontal=False)
    q = st.text_input("Búsqueda general", placeholder="Ej: Ecosport, 30003, 52128517AA, bieleta...")
    codigo = st.text_input("Código TIPER", placeholder="Ej: 30003")
    oem = st.text_input("OEM / referencia", placeholder="Ej: 68105872AA")
    producto = st.selectbox("Producto", ["Todos"] + select_options(aplicaciones if modo == "Aplicaciones" else fichas, "producto"))

if modo == "Aplicaciones":
    df = aplicaciones.copy()
    with st.sidebar:
        marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df, "marca"))
        modelo = st.selectbox("Modelo", ["Todos"] + select_options(df[df["marca"].eq(marca)] if marca != "Todas" else df, "modelo"))
    mask = pd.Series(True, index=df.index)
    if q:
        mask &= text_search(df, q, ["codigo", "producto", "marca", "modelo", "anio", "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info"])
    if codigo:
        mask &= contains_norm(df["codigo"], codigo)
    if oem:
        mask &= text_search(df, oem, ["oem", "ficha_oem"])
    if producto != "Todos":
        mask &= df["producto"].eq(producto)
    if marca != "Todas":
        mask &= df["marca"].eq(marca)
    if modelo != "Todos":
        mask &= df["modelo"].eq(modelo)

    res = df[mask].copy()
    st.subheader(f"Resultados: {len(res):,}".replace(",", "."))
    st.dataframe(
        res[[c for c in ["codigo", "producto", "marca", "modelo", "anio", "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info", "imagen_producto", "url_ficha"] if c in res.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "imagen_producto": st.column_config.ImageColumn("Imagen", width="small"),
            "url_ficha": st.column_config.LinkColumn("Ficha TIPER"),
        },
    )
else:
    df = fichas.copy()
    mask = pd.Series(True, index=df.index)
    if q:
        mask &= text_search(df, q, ["codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem", "ficha_medidas"])
    if codigo:
        mask &= contains_norm(df["codigo"], codigo)
    if oem:
        mask &= contains_norm(df["ficha_oem"], oem)
    if producto != "Todos":
        mask &= df["producto"].eq(producto)
    res = df[mask].copy()
    st.subheader(f"Resultados: {len(res):,}".replace(",", "."))
    st.dataframe(
        res[[c for c in ["codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem", "ficha_medidas", "imagen_producto", "url_ficha"] if c in res.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "imagen_producto": st.column_config.ImageColumn("Imagen", width="small"),
            "url_ficha": st.column_config.LinkColumn("Ficha TIPER"),
        },
    )

st.divider()
st.markdown("""
**Tip de uso:** la búsqueda ignora espacios, guiones y mayúsculas. Por ejemplo, `BA 046`, `BA-046` y `BA046` se tratan parecido.
""")
