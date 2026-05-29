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
    "CILBRAKE": ("cilbrake_aplicaciones.csv", "cilbrake_fichas.csv"),
    "SERRAT": ("serrat_aplicaciones.csv", "serrat_fichas.csv"),
}

TECNICAS = [
    "estrias_externas", "estrias_internas", "estrias_lado_rueda", "estrias_lado_caja",
    "longitud_semieje", "longitud_cardan", "longitud_punta_eje",
    "diametro_asiento", "diametro_asiento_lado_rueda",
    "diametro_jh", "diametro_junta_homocinetica", "diametro_jh_deslizante",
    "altura_jh", "altura_punta_eje",
    "diametro_circunferencia_agujeros", "rosca_agujeros",
    "diametro_rodamiento", "diametro_menor",
    "pieza", "posicion", "diametro_int", "diametro_ext", "altura",
    "abs", "posicion_seguro", "lado", "boca_chica", "boca_grande", "largo", "peso", "dimensiones",
]

AUX_TECNICAS = [
    "diametro_int_filtro", "diametro_ext_filtro", "altura_filtro",
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
    "pieza": "Pieza",
    "posicion": "Posición",
    "diametro_int": "Ø int real",
    "diametro_ext": "Ø ext real",
    "altura": "Altura real",
    "abs": "ABS",
    "posicion_seguro": "Seguro",
    "lado": "Lado",
    "boca_chica": "Boca chica",
    "boca_grande": "Boca grande",
    "largo": "Largo",
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

def extraer_motor_desde_info(txt: str) -> str:
    """Para CILBRAKE: deja en la columna info solamente el motor.
    Ej: 'Motor: 1.3 | Pieza: RUEDA' -> '1.3'.
    Si no hay motor, queda vacío porque pieza/posición/lado ya tienen columnas propias.
    """
    t = limpiar(txt)
    m = re.search(r"Motor\s*:\s*(.*?)(?:\s*\||$)", t, flags=re.IGNORECASE)
    return limpiar(m.group(1)) if m else ""

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
        ("FUELLE", ["FUELLE"]),
    ]

    for familia, palabras in reglas:
        if any(p in tn for p in palabras):
            return familia

    return t

def read_csv_any(path: str) -> pd.DataFrame:
    """Lee CSV detectando separador (, o ;) y tolerando columnas extra."""
    try:
        df = pd.read_csv(path, dtype=str, sep=None, engine="python").fillna("")
    except Exception:
        try:
            df = pd.read_csv(path, dtype=str, sep=";").fillna("")
        except Exception:
            df = pd.read_csv(path, dtype=str, sep=",").fillna("")

    # Limpia columnas basura típicas de Excel/CSV y fusiona duplicadas tipo ficha_info.1
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]].copy()
    for col in list(df.columns):
        m = re.match(r"^(.*)\.\d+$", str(col))
        if m:
            base = m.group(1)
            if base in df.columns:
                df[base] = df[base].where(df[base].astype(str).str.strip().ne(""), df[col])
                df = df.drop(columns=[col])
            else:
                df = df.rename(columns={col: base})
    return df

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
    ] + TECNICAS + AUX_TECNICAS

    ficha_cols = [
        "codigo", "producto", "ficha_anio", "ficha_info", "ficha_oem",
        "ficha_medidas", "imagen_producto", "url_ficha", "fuente", "titulo", "categoria",
    ] + TECNICAS + AUX_TECNICAS

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

        # CILBRAKE: en info dejamos únicamente el motor.
        # Pieza, posición, lado, medidas y ABS ya se muestran en columnas técnicas.
        if "fuente" in df.columns and "info" in df.columns:
            mask_cilbrake = df["fuente"].map(norm).eq("CILBRAKE")
            df.loc[mask_cilbrake, "info"] = df.loc[mask_cilbrake, "info"].apply(extraer_motor_desde_info)

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
    orden = ["TIPER", "WEGA", "VTH", "DAUER", "CILBRAKE", "SERRAT"]
    return [x for x in orden if x in vals] + [x for x in vals if x not in orden]

def preparar_columnas(res: pd.DataFrame, modo: str) -> pd.DataFrame:
    es_dauer = False
    es_cilbrake = False
    es_serrat = False
    if not res.empty and "fuente_norm" in res.columns:
        fuentes = set(res["fuente_norm"].dropna().astype(str).unique())
        es_dauer = fuentes == {"DAUER"}
        es_cilbrake = fuentes == {"CILBRAKE"}
        es_serrat = fuentes == {"SERRAT"}

    if modo == "Aplicaciones":
        if es_cilbrake:
            cols = [
                "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
                "info",
            ] + TECNICAS + ["imagen_producto", "url_ficha", "oem"]
        elif es_dauer:
            cols = [
                "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
                "info",
            ] + TECNICAS + ["imagen_producto", "url_ficha", "oem"]
        elif es_serrat:
            cols = [
                "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
                "info", "boca_chica", "boca_grande", "largo", "posicion", "lado",
                "imagen_producto", "url_ficha", "oem"
            ]
        else:
            cols = [
                "fuente", "codigo", "familia", "producto", "marca", "modelo", "anio",
                "info", "oem", "ficha_medidas", "ficha_oem", "ficha_info",
            ] + TECNICAS + ["imagen_producto", "url_ficha"]
    else:
        if es_dauer or es_cilbrake or es_serrat:
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
    if es_cilbrake and "info" in out.columns:
        rename["info"] = "Motor"
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
    disponibles = [f for f in FUENTES.keys()]
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

    producto = st.selectbox("Producto", ["Todos"] + select_options(df_opciones, "familia"), key=f"producto_{modo}_{catalogo}")
    if producto != "Todos":
        df_opciones = df_opciones[df_opciones["familia_norm"].eq(norm(producto))]

    if modo == "Aplicaciones":
        marca = st.selectbox("Marca vehículo", ["Todas"] + select_options(df_opciones, "marca"), key=f"marca_{modo}_{catalogo}_{producto}")
        if marca != "Todas":
            df_opciones = df_opciones[df_opciones["marca_norm"].eq(norm(marca))]

        modelo = st.selectbox("Modelo", ["Todos"] + select_options(df_opciones, "modelo"), key=f"modelo_{modo}_{catalogo}_{producto}_{marca}")
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
        posicion_seguro_sel = st.selectbox(
            "Seguro",
            ["Todos"] + select_options_tecnico(df_opciones, "posicion_seguro"),
        )
        lado_sel = st.selectbox(
            "Lado",
            ["Todos"] + select_options_tecnico(df_opciones, "lado"),
        )
    else:
        estrias_externas_sel = "Todos"
        estrias_internas_sel = "Todos"
        posicion_seguro_sel = "Todos"
        lado_sel = "Todos"

    # Filtros técnicos de rodamientos. Aparecen para cualquier proveedor
    # cuando la familia seleccionada es RODAMIENTO.
    if producto == "RODAMIENTO":
        st.divider()
        st.subheader("Medidas rodamiento")
        diametro_int_sel = st.selectbox(
            "Ø interior",
            ["Todos"] + select_options_tecnico(df_opciones, "diametro_int_filtro"),
            help="El filtro muestra el número entero. Ej: 17 incluye valores reales como 17.462.",
        )
        diametro_ext_sel = st.selectbox(
            "Ø exterior",
            ["Todos"] + select_options_tecnico(df_opciones, "diametro_ext_filtro"),
        )
        altura_sel = st.selectbox(
            "Altura",
            ["Todos"] + select_options_tecnico(df_opciones, "altura_filtro"),
        )
        abs_sel = st.selectbox(
            "ABS",
            ["Todos"] + select_options_tecnico(df_opciones, "abs"),
        )
        rod_posicion_sel = st.selectbox(
            "Posición",
            ["Todos"] + select_options_tecnico(df_opciones, "posicion"),
        )
        rod_lado_sel = st.selectbox(
            "Lado rodamiento",
            ["Todos"] + select_options_tecnico(df_opciones, "lado"),
        )
    else:
        diametro_int_sel = "Todos"
        diametro_ext_sel = "Todos"
        altura_sel = "Todos"
        abs_sel = "Todos"
        rod_posicion_sel = "Todos"
        rod_lado_sel = "Todos"

    # Filtros técnicos de fuelles. Aparecen para cualquier proveedor
    # cuando la familia seleccionada es FUELLE.
    if producto == "FUELLE":
        st.divider()
        st.subheader("Medidas fuelle")
        boca_chica_sel = st.selectbox(
            "Boca chica",
            ["Todos"] + select_options_tecnico(df_opciones, "boca_chica"),
        )
        boca_grande_sel = st.selectbox(
            "Boca grande",
            ["Todos"] + select_options_tecnico(df_opciones, "boca_grande"),
        )
        largo_sel = st.selectbox(
            "Largo",
            ["Todos"] + select_options_tecnico(df_opciones, "largo"),
        )
        fuelle_posicion_sel = st.selectbox(
            "Posición",
            ["Todos"] + select_options_tecnico(df_opciones, "posicion"),
        )
        fuelle_lado_sel = st.selectbox(
            "Lado",
            ["Todos"] + select_options_tecnico(df_opciones, "lado"),
        )
    else:
        boca_chica_sel = "Todos"
        boca_grande_sel = "Todos"
        largo_sel = "Todos"
        fuelle_posicion_sel = "Todos"
        fuelle_lado_sel = "Todos"

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
    mask &= filtrar_tecnico(df, "posicion_seguro", posicion_seguro_sel)
    mask &= filtrar_tecnico(df, "lado", lado_sel)

if producto == "RODAMIENTO":
    mask &= filtrar_tecnico(df, "diametro_int_filtro", diametro_int_sel)
    mask &= filtrar_tecnico(df, "diametro_ext_filtro", diametro_ext_sel)
    mask &= filtrar_tecnico(df, "altura_filtro", altura_sel)
    mask &= filtrar_tecnico(df, "abs", abs_sel)
    mask &= filtrar_tecnico(df, "posicion", rod_posicion_sel)
    mask &= filtrar_tecnico(df, "lado", rod_lado_sel)

if producto == "FUELLE":
    mask &= filtrar_tecnico(df, "boca_chica", boca_chica_sel)
    mask &= filtrar_tecnico(df, "boca_grande", boca_grande_sel)
    mask &= filtrar_tecnico(df, "largo", largo_sel)
    mask &= filtrar_tecnico(df, "posicion", fuelle_posicion_sel)
    mask &= filtrar_tecnico(df, "lado", fuelle_lado_sel)

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
**Tip de uso:** la búsqueda ignora espacios, guiones y mayúsculas. Los cross/equivalencias se buscan desde Búsqueda general u OEM/referencia. Si elegís una familia técnica como RODAMIENTO o FUELLE, aparecen filtros por medidas.
""")
