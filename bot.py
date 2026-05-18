import os
import json
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =============================================
# AYARLAR — Render Environment Variables'dan okunur
# =============================================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
hesap_bilgisi = json.loads(os.environ["GOOGLE_CREDENTIALS"])
kimlik = Credentials.from_service_account_info(hesap_bilgisi, scopes=SCOPES)
gc = gspread.authorize(kimlik)

TABLO_ADI = os.environ.get("TABLO_ADI", "bilgi_tabani")

# =============================================
# Basit cache — her 60 saniyede bir taze okur
# =============================================
import time
_cache = {"veri": {}, "zaman": 0}
CACHE_SURE = 60  # saniye

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
# /guncelle komutu — cache'i sıfırlar
# =============================================
from telegram.ext import CommandHandler

async def guncelle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _cache["zaman"] = 0
    try:
        tabloyu_oku()
        await update.message.reply_text("✅ Tablo güncellendi!")
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")

# =============================================
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("guncelle", guncelle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mesaj_isle))
    print("✅ Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
