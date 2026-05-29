# Actualización Catálogo MIPOL - DAUER

Incluye:

- `app.py` actualizado.
- `data/dauer_aplicaciones.csv`
- `data/dauer_fichas.csv`

Cambios principales:

1. DAUER separado en columnas técnicas:
   - estrias_externas
   - estrias_internas
   - estrias_lado_rueda
   - estrias_lado_caja
   - longitud_semieje
   - longitud_cardan
   - diametro_jh
   - lado
   - abs
   - seguro
   - posicion_seguro
   - etc.

2. Los filtros ya no se mezclan entre proveedores:
   - Primero elegís proveedor: Todos, TIPER, WEGA, VTH o DAUER.
   - Después recién se cargan Producto, Marca y Modelo según ese proveedor.

## Subida a GitHub

- Reemplazar `app.py`.
- Subir los CSV dentro de la carpeta `data`.
- Commit.
- Push.
- Reboot app en Streamlit Cloud.
