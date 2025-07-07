# excel_bot.py  — Bot Telegram para importar Excel como pedidos en Django
# Versión definitiva para python-telegram-bot v21+, loop-safe y con toda la lógica

import os
import tempfile
import requests
import pandas as pd
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

# Carga variables de entorno desde .env (local) o Railway
load_dotenv()
TOKEN       = os.environ["TG_TOKEN"]                     # Token de BotFather
DJANGO_URL  = os.environ.get("DJANGO_URL", "").rstrip("/") + "/api/pedidos/bulk/"  # URL de tu API Django
API_KEY     = os.getenv("DJANGO_KEY", "")             # Token de acceso (Bearer JWT o TokenAuth)
MAX_SIZE_MB = int(os.getenv("MAX_SIZE_MB", 5))          # Tamaño máximo de Excel en MB

# ──────────────────────────────── parse_excel ───────────────────────────────

def parse_excel(path: str):
    """
    Lee el archivo .xlsx en 'path' y devuelve una lista de diccionarios "pedidos".
    Asume:
      - La fila donde la columna A es 'Sign' marca el inicio de la cabecera real.
      - Metadatos en primeras 10 filas, con clave 'Service Date' y valor fecha.
      - Columnas de datos se renombrarán a los campos esperados por tu API.
      - Convierte fechas y horas a strings ISO.
    """
    # 1. Leer sin encabezado para hallar fila 'Sign'
    df0 = pd.read_excel(path, engine="openpyxl", header=None)
    header_rows = df0.index[df0.iloc[:, 0] == "Sign"]
    if header_rows.empty:
        raise ValueError("No se encontró la cabecera 'Sign' en columna A")
    hr = header_rows[0]

    # 2. Leer datos a partir de esa fila (skiprows=hr, header=0)
    df = pd.read_excel(
        path,
        engine="openpyxl",
        skiprows=hr,
        header=0,
        dtype=str,      # todo como str para sanitizar luego
    )

    # 3. Renombrar columnas canónicas según posición esperada
    rename_map = {
        df.columns[0]: "grupo",         # Sign
        df.columns[1]: "excursion",    # Excursión
        df.columns[2]: "lugar_entrega",
        df.columns[3]: "lugar_recogida",
        df.columns[4]: "fecha_inicio",
        df.columns[5]: "hora_inicio",
        df.columns[6]: "fecha_fin",
        df.columns[7]: "hora_fin",
        df.columns[8]: "guia",
        df.columns[9]: "pax",
        df.columns[10]: "emisores",
        # Asume que resto (bono, notas) están tras estas columnas
    }
    df = df.rename(columns=rename_map)

    # Filtra filas sin grupo
    df = df[df["grupo"].notna()]
    if df.empty:
        raise ValueError("El Excel no contiene filas de datos con 'grupo'")

    # 4. Leer metadatos (Service Date)
    meta = pd.read_excel(path, engine="openpyxl", nrows=10, header=None)
    svc = meta[meta.iloc[:, 0] == "Service Date"]
    if svc.empty:
        raise ValueError("No se encontró 'Service Date' en metadatos")
    raw_date = svc.iloc[0, 1]
    fecha_servicio = pd.to_datetime(raw_date).date().isoformat()

    # 5. Construir lista de pedidos
    pedidos = []
    for _, row in df.iterrows():
        # parseo seguro de horas
        hora_iso = None
        if row.get("hora_inicio"):
            try:
                tiempo = pd.to_datetime(row["hora_inicio"]).time()
                hora_iso = tiempo.isoformat(timespec="minutes")
            except:
                hora_iso = None

        # parseo de enteros
        pax = int(float(row.get("pax") or 0))
        emisores = int(float(row.get("emisores") or pax))

        pedidos.append({
            "grupo":         str(row.get("grupo", "")).strip(),
            "excursion":     str(row.get("excursion", "")).strip(),
            "lugar_entrega": row.get("lugar_entrega") or None,
            "lugar_recogida":row.get("lugar_recogida") or None,
            "fecha_inicio":  fecha_servicio,
            "hora_inicio":   hora_iso,
            "fecha_fin":     None,
            "hora_fin":      None,
            "guia":          row.get("guia") or "",
            "pax":           pax,
            "emisores":      emisores,
            "bono":          row.get("bono") or "",
            "notas":         row.get("notas") or "",
        })

    return pedidos

# ────────────────────────────── handle_doc ────────────────────────────────

async def handle_doc(update, context):
    """
    Handler para archivos recibidos en Telegram. Valida extensión y tamaño,
    descarga a un temporal, parsea y envía al backend.
    """
    doc = update.message.document
    if not doc.file_name.lower().endswith(".xlsx"):
        return  # solo procesar archivos xlsx

    if doc.file_size and doc.file_size > MAX_SIZE_MB * 1024 * 1024:
        await update.message.reply_text("❌ Archivo demasiado grande (límite %d MB)" % MAX_SIZE_MB)
        return

    # Descarga a tmp
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmpf:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=tmpf.name)
        path = tmpf.name

    # Procesa Excel y manda al backend
    try:
        pedidos = parse_excel(path)
        headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
        resp = requests.post(DJANGO_URL, json=pedidos, headers=headers, timeout=20)
        if resp.ok:
            await update.message.reply_text(f"✅ Importados {len(pedidos)} pedidos.")
        else:
            await update.message.reply_text(f"❌ API {resp.status_code}: {resp.text[:180]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Bot Excel → Pedidos arrancando…")

    # Construye la app y limpia updates previos
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .drop_pending_updates(True)
        .build()
    )
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    # Inicia polling (método síncrono)
    app.run_polling()
    print("Bot Excel → Pedidos listo.")