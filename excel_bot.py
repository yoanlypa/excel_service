# excel_bot.py  ── versión estable (loop‑safe) 2025‑07‑07
# Recibe .xlsx vía Telegram y los inserta en Django. Compatible con python‑telegram‑bot v21+

import os, tempfile, requests, datetime as dt
import pandas as pd
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, MessageHandler, filters

load_dotenv()
TOKEN       = os.environ["TG_TOKEN"]
DJANGO_URL  = os.environ["DJANGO_URL"].rstrip("/") + "/api/pedidos/bulk/"
API_KEY     = os.getenv("DJANGO_KEY", "")
MAX_SIZE_MB = 5

# ────────────────────────────── parser Excel ─────────────────────────────

def parse_excel(path: str):
    """Devuelve lista de dicts listos para JSON (sin objetos date)."""
    df0 = pd.read_excel(path, engine="openpyxl", header=None)
    header_row = df0.index[df0.iloc[:, 0] == "Sign"]
    if header_row.empty:
        raise ValueError("No encuentro cabecera 'Sign'")
    hr = header_row[0]
    df = pd.read_excel(path, engine="openpyxl", skiprows=hr, header=0, dtype=str)

    rename = {
        df.columns[0]: "grupo",
        df.columns[1]: "excursion",
        df.columns[5]: "hora_inicio",
        df.columns[6]: "ad",
        df.columns[7]: "ch",
    }
    df = df.rename(columns=rename)
    df = df[df["grupo"].notna()]

    meta = pd.read_excel(path, engine="openpyxl", nrows=10, header=None)
    row = meta[meta.iloc[:, 0] == "Service Date"]
    if row.empty:
        raise ValueError("No encuentro 'Service Date'")
    fecha_servicio = pd.to_datetime(row.iloc[0, 1]).date()

    pedidos = []
    for _, r in df.iterrows():
        adultos = int(r.get("ad") or 0)
        ninos   = int(r.get("ch") or 0)
        hora_raw = r.get("hora_inicio")
        try:
            hora_iso = pd.to_datetime(hora_raw).time().isoformat(timespec="minutes") if hora_raw else None
        except Exception:
            hora_iso = None
        pedidos.append({
            "grupo":        str(r["grupo"]).strip(),
            "excursion":    str(r.get("excursion") or "").strip(),
            "fecha_inicio": fecha_servicio.isoformat(),
            "hora_inicio":  hora_iso,
            "pax":          adultos + ninos,
            "emisores":     adultos + ninos,
            "lugar_entrega": None,
            "lugar_recogida": None,
            "fecha_fin":     None,
            "hora_fin":      None,
            "guia":          "",
            "bono":          "",
            "notas":         "",
        })
    if not pedidos:
        raise ValueError("Archivo sin filas de datos")
    return pedidos

# ────────────────────────────── Bot handler ──────────────────────────────

async def handle_doc(update, context):
    doc = update.message.document
    if not doc.file_name.endswith(".xlsx"):
        return
    if doc.file_size > MAX_SIZE_MB * 1024 * 1024:
        await update.message.reply_text("❌ Archivo demasiado grande")
        return
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(custom_path=tmp.name)
        try:
            pedidos = parse_excel(tmp.name)
            headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
            r = requests.post(DJANGO_URL, json=pedidos, headers=headers, timeout=15)
            if r.ok:
                await update.message.reply_text(f"✅ Importados {len(pedidos)} pedidos.")
            else:
                await update.message.reply_text(f"❌ API {r.status_code}: {r.text[:180]}")
        except Exception as e:
            await update.message.reply_text(f"❌ {e}")

# ────────────────────────────── main (bloqueante) ───────────────────────

def main():
    print("Bot Excel → Pedidos arrancando…")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.run_polling()   # bloquea y maneja su propio bucle

if __name__ == "__main__":
    main()
