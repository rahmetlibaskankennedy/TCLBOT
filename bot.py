import os
import json
import time
import asyncio
import gspread
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# =============================================
# HTTP Sunucusu — Render için
# =============================================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args):
        pass

Thread(target=lambda: HTTPServer(("0.0.0.0", 10000), Handler).serve_forever(), daemon=True).start()

# =============================================
# AYARLAR
# =============================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TABLO_ADI      = os.environ.get("TABLO_ADI", "bilgi_tabani")

SCOPES        = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
hesap_bilgisi = json.loads(os.environ["GOOGLE_CREDENTIALS"])
kimlik        = Credentials.from_service_account_info(hesap_bilgisi, scopes=SCOPES)
gc            = gspread.authorize(kimlik)

# =============================================
# Cache
# =============================================
_cache = {"veri": {}, "zaman": 0}
CACHE_SURE = 60

def tabloyu_oku():
    simdi = time.time()
    if simdi - _cache["zaman"] > CACHE_SURE:
        sayfa = gc.open(TABLO_ADI).sheet1
        satirlar = sayfa.get_all_values()
        _cache["veri"] = {
            satir[0].strip().lower(): satir[1].strip()
            for satir in satirlar
            if len(satir) >= 2 and satir[0].strip()
        }
        _cache["zaman"] = simdi
        print("✅ Tablo güncellendi.")
    return _cache["veri"]

# =============================================
# Mesaj işleyici
# =============================================
async def mesaj_isle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = update.message.text or ""
    kelimeler = mesaj.split()
    etiketler = [k.lower() for k in kelimeler if k.startswith("#")]

    if not etiketler:
        return

    try:
        tablo = tabloyu_oku()
    except Exception as e:
        print(f"Tablo okuma hatası: {e}")
        return

    for etiket in etiketler:
        if etiket in tablo:
            await update.message.reply_text(tablo[etiket])

# =============================================
# /guncelle komutu
# =============================================
async def guncelle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _cache["zaman"] = 0
    try:
        tabloyu_oku()
        await update.message.reply_text("✅ Tablo güncellendi!")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")

# =============================================
# Hata işleyici — NetworkError'ları sessizce geç
# =============================================
async def hata_isle(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, (NetworkError, TimedOut)):
        print(f"⚠️ Bağlantı hatası (otomatik düzelecek): {context.error}")
    else:
        print(f"❌ Beklenmeyen hata: {context.error}")

# =============================================
# Ana döngü
# =============================================
async def main():
    while True:
        try:
            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .connect_timeout(30)
                .read_timeout(30)
                .write_timeout(30)
                .build()
            )
            app.add_handler(CommandHandler("guncelle", guncelle))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isle))
            app.add_error_handler(hata_isle)

            print("✅ Bot çalışıyor...")
            async with app:
                await app.start()
                await app.updater.start_polling(
                    drop_pending_updates=True,
                    allowed_updates=["message"]
                )
                await asyncio.Event().wait()

        except (NetworkError, TimedOut) as e:
            print(f"⚠️ Ağ hatası, 10 saniye sonra yeniden bağlanıyor: {e}")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"❌ Kritik hata, 10 saniye sonra yeniden başlıyor: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
