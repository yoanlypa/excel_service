from fastapi import FastAPI, UploadFile, File, HTTPException
from .bot import start, handle_doc
from .config import settings
import threading
import uvicorn
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

app = FastAPI()

# Endpoint para subir desde la UI
@app.post('/upload_excel')
async def upload_excel(file: UploadFile = File(...)):
    content = await file.read()
    from .parser import parse_excel
    from .client import ApiClient
    try:
        pedidos = parse_excel(content)
        api = ApiClient()
        return await api.post_pedidos(pedidos)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Arranca el bot en segundo plano
def run_bot():
    application = ApplicationBuilder().token(settings.tg_token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    application.run_polling()

@app.on_event('startup')
def startup_event():
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)
