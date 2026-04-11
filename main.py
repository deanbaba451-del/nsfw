import os
import threading
import requests
import telebot
from flask import Flask
import cv2
import time
import logging

# Logları en detaylı hale getirdik
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "8651145622:AAEmSrGND0ZXi8JDI3LmMxbdFCCowv8hgYU"

SIGHT_KEYS = [
    {"user": "713471034", "key": "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd"},
    {"user": "1773861365", "key": "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd"},
    {"user": "402404015", "key": "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz"},
    {"user": "1968951124", "key": "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"}
]
THRESHOLD = 0.50

# Threading desteği ile botu başlatıyoruz
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=4)
app = Flask(__name__)
key_index = 0

@app.route('/')
def health(): return "System Online", 200

def scan_content(img_data):
    global key_index
    for _ in range(len(SIGHT_KEYS)):
        current = SIGHT_KEYS[key_index % len(SIGHT_KEYS)]
        try:
            r = requests.post('https://api.sightengine.com/1.0/check.json', 
                             files={'media': ('img.jpg', img_data)}, 
                             data={'models': 'nudity-2.0,wad,violence,minor,animal-welfare', 
                                   'api_user': current["user"], 'api_secret': current["key"]}, 
                             timeout=15)
            res = r.json()
            if res.get("status") == "success":
                nude = res.get("nudity", {})
                vals = [nude.get("sexual_activity", 0), nude.get("sexual_display", 0), nude.get("erotica", 0),
                        res.get("violence", 0), res.get("weapon", 0), res.get("drugs", 0),
                        res.get("minor", {}).get("prob", 0), res.get("animal-welfare", {}).get("prob", 0)]
                max_score = max(vals)
                logger.info(f"--- ANALİZ SONUCU: {max_score} ---")
                return max_score >= THRESHOLD
            key_index += 1
        except Exception as e:
            logger.error(f"API Hatası: {e}")
            key_index += 1
    return False

def check_and_delete(message, file_id, is_video=False):
    try:
        logger.info(f"Medya indiriliyor (ID: {file_id})...")
        f_info = bot.get_file(file_id)
        content = bot.download_file(f_info.file_path)
        
        should_delete = False
        if is_video:
            t_path = f"tmp_{file_id}.mp4"
            with open(t_path, "wb") as f: f.write(content)
            cap = cv2.VideoCapture(t_path)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # Videodan 4 farklı kare alıp tarıyoruz
            for p in [0.2, 0.4, 0.6, 0.8]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * p))
                ret, frame = cap.read()
                if ret:
                    _, buf = cv2.imencode('.jpg', frame)
                    if scan_content(buf.tobytes()):
                        should_delete = True; break
            cap.release()
            if os.path.exists(t_path): os.remove(t_path)
        else:
            if scan_content(content): should_delete = True

        if should_delete:
            bot.delete_message(message.chat.id, message.message_id)
            logger.info(f"YASAKLI MEDYA SİLİNDİ (Mesaj ID: {message.message_id})")
    except Exception as e:
        logger.error(f"İşlem Hatası: {e}")

# Tüm medya tiplerini dinliyoruz
@bot.message_handler(content_types=['photo', 'video', 'animation', 'video_note', 'sticker', 'document'])
def handle_all_media(message):
    logger.info(f"!!! MEDYA GELDİ !!! Tip: {message.content_type}")
    fid = None
    is_v = False
    if message.photo: fid = message.photo[-1].file_id
    elif message.video: fid, is_v = message.video.file_id, True
    elif message.animation: fid, is_v = message.animation.file_id, True
    elif message.video_note: fid, is_v = message.video_note.file_id, True
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('video'):
        fid, is_v = message.document.file_id, True
    
    if fid:
        threading.Thread(target=check_and_delete, args=(message, fid, is_v)).start()

def run_bot():
    while True:
        try:
            bot.remove_webhook()
            logger.info("Bot Polling Modu Başlatıldı...")
            # Tüm mesajları çekmesi için allowed_updates ekliyoruz
            bot.infinity_polling(skip_pending=True, timeout=90, allowed_updates=['message', 'edited_message'])
        except Exception as e:
            logger.error(f"Bağlantı Hatası, 5sn sonra tekrar: {e}")
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # Flask web sunucusunu arka planda başlatıyoruz
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, use_reloader=False), daemon=True).start()
    run_bot()
