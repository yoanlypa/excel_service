# excel_bot.py  — Bot Telegram para importar Excel como pedidos en Django
# Versión definitiva y loop-safe para python-telegram-bot v21+

import os
import tempfile
import requests
import pandas as pd
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# Carga variables de entorno desde .env o Railway
load_dotenv()
TOKEN       = os.environ["TG_TOKEN"]
DJANGO_URL  = os.environ["DJANGO_URL"].rstrip("/") + "/api/pedidos/bulk/"
API_KEY     = os.getenv("DJANGO_KEY", "")
MAX_SIZE_MB = 5  # límite en MB para cada Excel


def parse_excel(path: str):
    """Lee el Excel, localiza la cabecera 'Sign', extrae Service Date y devuelve pedidos como lista de dicts."""
    # Lee sin header para encontrar 'Sign'
    df0 = pd.read_excel(path, engine="openpyxl", header=None)
    header_row = df0.index[df0.iloc[:, 0] == "Sign"]
    if header_row.empty:
        raise ValueError("No encuentro cabecera 'Sign' en la columna A")
    hr = header_row[0]
    # Re-lee a partir de la cabecera
    df = pd.read_excel(
        path,
        engine="openpyxl",
        skiprows=hr,
        header=0,
        dtype=str
    )
    # Renombra a campos canónicos según posiciones
    # Ajusta índices si cambian las columnas en futuros templates
    rename_map = {
        df.columns[0]: "grupo",
        df.columns[1]: "excursion",
        df.columns[5]: "hora_inicio",
        df.columns[6]: "ad",
        df.columns[7]: "ch",
    }
    df = df.rename(columns=rename_map)
    df = df[df["grupo"].notna()]

    # Extrae Service Date de las primeras 10 filas
    meta = pd.read_excel(path, engine="openpyxl", nrows=10, header=None)
    sr = meta[meta.iloc[:, 0] == "Service Date"]
    if sr.empty:
        raise ValueError("No encuentro 'Service Date' en las filas superiores")
    service = sr.iloc[0, 1]
    # Normaliza a date
    service_date = pd.to_datetime(service).date() if not isinstance(service, str) else pd.to_datetime(service).date()

    # Construye lista de pedidos
    pedidos = []
    for _, row in df.iterrows():
        adultos = int(row.get("ad") or 0)
        ninos   = int(row.get("ch") or 0)
        # Procesa hora en ISO o None
        raw = row.get("hora_inicio")
        try:
            hora_iso = pd.to_datetime(raw).time().isoformat(timespec="minutes") if raw else None
        except Exception:
            hora_iso = None

        pedidos.append({
            "grupo": str(row.get("grupo","")).strip(),
            "excursion": str(row.get("excursion","")).strip(),
            "fecha_inicio": service_date.isoformat(),
            "hora_inicio": hora_iso,
            "pax": adultos + ninos,
            "emisores": adultos + ninos,
            # Campos opcionales de tu modelo:
            "lugar_entrega": None,
            "lugar_recogida": None,
            "fecha_fin": None,
            "hora_fin": None,
            "guia": "",
            "bono": "",
            "notas": "",
        })
    if not pedidos:
        raise ValueError("Archivo sin filas de datos después de cabecera")
    return pedidos


async def handle_doc(update, context):
    """Maneja cada documento recibido en Telegram."""
    doc = update.message.document
    # Solo .xlsx
    if not doc.file_name.lower().endswith(".xlsx"):
        return
    # Tamaño máximo
    if doc.file_size > MAX_SIZE_MB * 1024 * 1024:
        await update.message.reply_text("❌ Archivo demasiado grande")
        return

    # Descarga a fichero temporal
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=tmp.name)

    try:
        pedidos = parse_excel(tmp.name)
        headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
        resp = requests.post(DJANGO_URL, json=pedidos, headers=headers, timeout=20)
        if resp.ok:
            await update.message.reply_text(f"✅ Importados {len(pedidos)} pedidos.")
        else:
            await update.message.reply_text(f"❌ API {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


if __name__ == "__main__":
    print("Bot Excel → Pedidos arrancando…")

    # Inicializa aplicación Telegram
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    # Limpia cualquier update antiguo y arranca polling
    app.run_polling(drop_pending_updates=True)
    print("Bot listo para recibir documentos.")