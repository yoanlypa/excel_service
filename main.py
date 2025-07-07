# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from .bot import start, handle_doc
from .config import settings
import threading
import uvicorn

app = FastAPI()

# 1) Endpoint para carga desde tu UI
@app.post('/upload_excel')
async def upload_excel(file: UploadFile = File(...)):
    content = await file.read()
    from .parser import parse_excel
    from .client import ApiClient
    try:
        pedido = parse_excel(content)
        api = ApiClient()
        return await api.post_pedido(pedido)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 2) Bot Telegram en background
from telegram.ext import ApplicationBuilder

def run_bot():
    application = ApplicationBuilder().token(settings.tg_token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    application.run_polling()

@app.on_event('startup')
def startup_event():
    threading.Thread(target=run_bot, daemon=True).start()

# 3) Si lo arrancas local:
if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)
