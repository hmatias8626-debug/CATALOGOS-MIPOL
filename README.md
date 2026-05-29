# Actualización Catálogo MIPOL - SERRAT Fuelles

Archivos incluidos:

- `app.py`: reemplaza el `app.py` actual.
- `data/serrat_aplicaciones.csv`: agregar dentro de la carpeta `data` del repositorio.
- `data/serrat_fichas.csv`: agregar dentro de la carpeta `data` del repositorio.

Cambios:

- Agrega proveedor `SERRAT`.
- Agrega familia `FUELLE`.
- Normaliza códigos, marca, modelo, OEM y aplicaciones.
- Separa medidas de fuelles en columnas:
  - Boca chica
  - Boca grande
  - Largo
  - Posición
  - Lado
- Cuando se selecciona familia `FUELLE`, aparecen filtros técnicos por medidas.
- La búsqueda general y OEM/referencia buscan también por el RO/OEM de Serrat.

Pasos:

1. Reemplazar `app.py`.
2. Subir `serrat_aplicaciones.csv` y `serrat_fichas.csv` dentro de `data`.
3. Commit.
4. Push.
5. Reboot app en Streamlit Cloud.
