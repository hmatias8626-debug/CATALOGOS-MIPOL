# MIPOL Catálogo conectado a Supabase

## Archivos

- app.py
- requirements.txt

## Streamlit Secrets necesarios

En Streamlit Cloud > App > Settings > Secrets:

```toml
SUPABASE_URL = "https://qfabxmgglcesdqouqgss.supabase.co"
SUPABASE_KEY = "TU_ANON_PUBLIC_KEY"
```

## Importante

Esta versión ya no lee CSV locales. Consulta la tabla:

```text
mipol_productos_catalogo
```

## Pruebas

1. Proveedor: REY GOMA
2. Código: 1216
3. Checkbox OEM marcado
4. Debería mostrar equivalencias en GACRI/VTH si coinciden los OEM.

## Notas

- Limita resultados a 1000 para evitar que Streamlit se caiga.
- Carga filtros livianos desde Supabase y los cachea 1 hora.
