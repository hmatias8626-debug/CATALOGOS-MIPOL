FIX OEM TIMEOUT

Reemplazar app.py.

Qué corrige:
- Las equivalencias OEM ya no escanean info/descripcion/ficha_info.
- Ahora usan sólo la columna oem_norm ya normalizada en Supabase.
- Evita consultas enormes que causaban:
  canceling statement due to statement timeout

Después:
1) Reemplazar app.py
2) Commit
3) Push
4) Reboot Streamlit
5) Probar REY GOMA + código 1216
