# Actualización Catálogo MIPOL - CILBRAKE Rodamientos

Incluye:

- `app.py` actualizado.
- `data/cilbrake_aplicaciones.csv`
- `data/cilbrake_fichas.csv`

Cambios principales:

- Agrega proveedor **CILBRAKE**.
- Agrega familia **RODAMIENTO**.
- Para rodamientos aparecen filtros técnicos:
  - Ø interior
  - Ø exterior
  - Altura
  - ABS
  - Posición
  - Lado
- Los filtros de medidas muestran valores enteros. Ejemplo: si el dato real es `17.462`, el filtro muestra `17`, pero la tabla conserva el valor real.
- Los precios del Excel original fueron ignorados: no se cargan ni se muestran.
- Los cross/equivalencias se cargan en `oem` para que se puedan buscar desde Búsqueda general u OEM/referencia.
- En DAUER se eliminó el filtro/columna redundante `Seguro / traba` y se conserva `Seguro` basado en `posicion_seguro`.

Para subir:

1. Reemplazar `app.py` en GitHub.
2. Subir `cilbrake_aplicaciones.csv` y `cilbrake_fichas.csv` dentro de `data/`.
3. Commit -> Push.
4. Reboot app en Streamlit Cloud.
