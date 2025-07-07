# bot.py
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters
)
from .parser import parse_excel
from .client import ApiClient
from .config import settings
from .exceptions import ParseError, ApiError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envía un .xlsx con la hoja 'Supplier Confirmation' para crear un pedido."
    )

async def handle_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.xlsx'):
        return
    if doc.file_size > settings.max_size_mb * 1024 * 1024:
        await update.message.reply_text("❌ Archivo demasiado grande.")
        return

    content = await doc.get_file().download_as_bytearray()
    try:
        pedido = parse_excel(content)
        api = ApiClient()
        await api.post_pedido(pedido)
        count = len(pedido['maletas'])
        await update.message.reply_text(f"✅ Pedido registrado con {count} maletas.")
    except ParseError as e:
        await update.message.reply_text(f"❌ Error de parseo: {e}")
        logger.exception(e)
    except ApiError as e:
        await update.message.reply_text(f"❌ Error en API: {e}")
        logger.exception(e)
    except Exception as e:
        await update.message.reply_text("❌ Error inesperado. Consulta logs.")
        logger.exception(e)
