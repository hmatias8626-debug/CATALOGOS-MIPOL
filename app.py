import os
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Catálogo MIPOL", page_icon="🔎", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def norm(txt: str) -> str:
    txt = str(txt or "").upper()
    txt = txt.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    return re.sub(r"[^A-Z0-9]+", "", txt)


def familia_producto(txt: str) -> str:
    t = str(txt or "").upper().strip()
    t_norm = norm(t)

    reglas = [
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
        ("KIT", ["KIT"]),
        # Familias WEGA
        ("FILTRO DE AIRE", ["AIRE"]),
        ("FILTRO DE ACEITE", ["ACEITE"]),
        ("FILTRO DE COMBUSTIBLE", ["COMBUSTIBLE"]),
        ("FILTRO DE HABITACULO", ["HABITACULO", "HABITACULO"]),
    ]

    for familia, palabras in reglas:
        for palabra in palabras:
            if palabra in t_norm:
                return familia

    return re.sub(r"\s+", " ", t).strip()


def read_csv_if_exists(filename: str, columns: list[str], fuente: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns].copy()
    df["fuente"] = df.get("fuente", fuente).replace("", fuente)
    return df


@st.cache_data(show_spinner="Cargando catálogo...")
def load_data():
    app_cols = ["codigo", "producto", "marca", "modelo", "anio", "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info", "imagen_producto", "url_ficha", "fuente"]
    ficha_cols = ["codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem", "ficha_medidas", "imagen_producto", "url_ficha", "fuente"]

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
            df[col] = df[col].astype(str).fillna("").str.strip()
        if "codigo" in df.columns:
            df["codigo"] = df["codigo"].str.replace(r"\.0$", "", regex=True)
        if "producto" in df.columns:
            df["familia"] = df["producto"].apply(familia_producto)
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


def select_options(df, col):
    if col not in df.columns:
        return []
    vals = sorted(v for v in df[col].dropna().astype(str).str.strip().unique() if v)
    return vals


aplicaciones, fichas = load_data()

st.title("🔎 Catálogo MIPOL")
st.caption("Buscador interno con datos TIPER + WEGA. Usa los mismos filtros y la misma lógica de búsqueda.")

with st.sidebar:
    st.header("Filtros")
    modo = st.radio("Buscar por", ["Aplicaciones", "Fichas/códigos"], horizontal=False)
    q = st.text_input("Búsqueda general", placeholder="Ej: Corsa, Agile, WR110, 30003, bieleta...")
    codigo = st.text_input("Código", placeholder="Ej: 30003, WR-110, FAP2827")
    oem = st.text_input("OEM / referencia", placeholder="Ej: 68105872AA, 90486296")
    producto = st.selectbox("Producto", ["Todos"] + select_options(aplicaciones if modo == "Aplicaciones" else fichas, "familia"))

if modo == "Aplicaciones":
    df = aplicaciones.copy()
    with st.sidebar:
        marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df, "marca"))
        modelo = st.selectbox("Modelo", ["Todos"] + select_options(df[df["marca"].eq(marca)] if marca != "Todas" else df, "modelo"))
    mask = pd.Series(True, index=df.index)
    if q:
        mask &= text_search(df, q, ["codigo", "producto", "familia", "marca", "modelo", "anio", "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info", "fuente"])
    if codigo:
        mask &= contains_norm(df["codigo"], codigo)
    if oem:
        mask &= text_search(df, oem, ["oem", "ficha_oem"])
    if producto != "Todos":
        mask &= df["familia"].eq(producto)
    if marca != "Todas":
        mask &= df["marca"].eq(marca)
    if modelo != "Todos":
        mask &= df["modelo"].eq(modelo)

    res = df[mask].copy()
    st.subheader(f"Resultados: {len(res):,}".replace(",", "."))
    st.dataframe(
        res[[c for c in ["fuente", "codigo", "producto", "marca", "modelo", "anio", "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info", "imagen_producto", "url_ficha"] if c in res.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "imagen_producto": st.column_config.ImageColumn("Imagen", width="small"),
            "url_ficha": st.column_config.LinkColumn("Ficha"),
        },
    )
else:
    df = fichas.copy()
    mask = pd.Series(True, index=df.index)
    if q:
        mask &= text_search(df, q, ["codigo", "producto", "familia", "ficha_anio", "ficha_info", "ficha_oem", "ficha_medidas", "fuente"])
    if codigo:
        mask &= contains_norm(df["codigo"], codigo)
    if oem:
        mask &= contains_norm(df["ficha_oem"], oem)
    if producto != "Todos":
        mask &= df["familia"].eq(producto)
    res = df[mask].copy()
    st.subheader(f"Resultados: {len(res):,}".replace(",", "."))
    st.dataframe(
        res[[c for c in ["fuente", "codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem", "ficha_medidas", "imagen_producto", "url_ficha"] if c in res.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "imagen_producto": st.column_config.ImageColumn("Imagen", width="small"),
            "url_ficha": st.column_config.LinkColumn("Ficha"),
        },
    )

st.divider()
st.markdown("""
**Tip de uso:** la búsqueda ignora espacios, guiones y mayúsculas. Por ejemplo, `WR-110`, `WR110`, `BA 046`, `BA-046` y `BA046` se tratan parecido.
""")
