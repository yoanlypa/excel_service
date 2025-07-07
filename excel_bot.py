# excel_bot.py  ── Python 3.10+
"""
Recibe exceles en Telegram, los convierte a JSON y los envía a
/api/pedidos/bulk/ en tu Django.
Estructura de fichero compatible con los ejemplos:
  - Metadatos en las primeras filas (Service Date, Ship…)
  - Cabecera real en la fila donde A = 'Sign'
  - Datos a partir de la fila siguiente
"""

import os, tempfile, requests, datetime as dt
import pandas as pd
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# ─────── Config ──────────────────────────────────────────────────────────
load_dotenv()                                    # lee .env local / Railway
TOKEN       = os.environ["TG_TOKEN"]             # BotFather
DJANGO_URL  = os.environ["VITE_API_URL"].rstrip("/") + "/api/pedidos/bulk/"
API_KEY     = os.getenv("SECRET_KEY", "")        # opcional header auth
MAX_SIZE_MB = 5                                  # si quieres limitar

# ─────── Excel → pedidos (parser robusto) ────────────────────────────────
def parse_excel(path: str):
    """Devuelve lista de dicts listos para POST /pedidos/bulk/"""
    # 1. Lee TODAS las filas para localizar cabecera 'Sign'
    df = pd.read_excel(path, engine="openpyxl", header=None)
    # Localiza fila donde col-0 == 'Sign'
    header_row = df.index[df.iloc[:, 0] == "Sign"]
    if header_row.empty:
        raise ValueError("No encuentro cabecera 'Sign' en la columna A")
    header_idx = header_row[0]
    df = pd.read_excel(
        path,
        engine="openpyxl",
        skiprows=header_idx,
        header=0,
        dtype=str
    )

    # Renombra columnas canónicas
    rename_map = {
        df.columns[0]: "grupo",         # Sign
        df.columns[1]: "excursion",
        df.columns[5]: "hora_inicio",   # Arrival / Meeting time
        df.columns[6]: "ad",            # Adultos
        df.columns[7]: "ch",            # Niños
    }
    df = df.rename(columns=rename_map)

    # Lee la fecha de servicio de las filas superiores
    meta = pd.read_excel(path, engine="openpyxl", nrows=10, header=None)
    service_row = meta[meta.iloc[:, 0] == "Service Date"]
    if service_row.empty:
        raise ValueError("No encuentro 'Service Date'")
    fecha_servicio = service_row.iloc[0, 1]
    if isinstance(fecha_servicio, str):
        fecha_servicio = pd.to_datetime(fecha_servicio).date()
    elif isinstance(fecha_servicio, dt.datetime):
        fecha_servicio = fecha_servicio.date()

    # Limpia filas vacías
    df = df[df["grupo"].notna()]

    # Convierte a formato esperado por tu API
    pedidos = []
    for _, row in df.iterrows():
        adultos = int(row.get("ad") or 0)
        ninos   = int(row.get("ch") or 0)
        pedidos.append({
            "grupo":        str(row["grupo"]).strip(),
            "excursion":    str(row["excursion"]).strip(),
            "fecha_inicio": fecha_servicio,          # YYYY-MM-DD
            "hora_inicio":  row.get("hora_inicio") or None,
            "pax":          adultos + ninos,
            "emisores":     adultos + ninos,         # adaptar si usas otro campo
            # campos opcionales del modelo:
            "lugar_entrega":  None,
            "lugar_recogida": None,
            "fecha_fin":     None,
            "hora_fin":      None,
            "guia":          "",
            "bono":          "",
            "notas":         "",
        })
    if not pedidos:
        raise ValueError("No se encontraron filas de datos")
    return pedidos

# ─────── Bot Telegram (polling) ───────────────────────────────────────────
async def handle_doc(update, context):
    doc = update.message.document
    if not doc.file_name.endswith(".xlsx"):
        return
    if doc.file_size > MAX_SIZE_MB * 1024 * 1024:
        await update.message.reply_text("❌ Archivo demasiado grande")
        return

    # Descarga a fichero temporal
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=tmp.name)
        try:
            pedidos = parse_excel(tmp.name)
            r = requests.post(
                DJANGO_URL,
                json=pedidos,
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
                timeout=15,
            )
            if r.ok:
                await update.message.reply_text(f"✅ Importados {len(pedidos)} pedidos.")
            else:
                await update.message.reply_text(f"❌ Error API: {r.status_code} {r.text[:180]}")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

if __name__ == "__main__":
    print("Bot Excel → Pedidos arrancando...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.run_polling()           # cómodo y gratis para pruebas
