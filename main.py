import os
import threading
import requests
import telebot
from flask import Flask
import cv2
import time
import logging

# LOGLAMA
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "8651145622:AAEmSrGND0ZXi8JDI3LmMxbdFCCowv8hgYU"

# SIGHTENGINE AYARLARI
SIGHT_KEYS = [
    {"user": "713471034", "key": "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd"},
    {"user": "1773861365", "key": "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd"},
    {"user": "402404015", "key": "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz"},
    {"user": "1968951124", "key": "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"}
]
# Hassas içerikler için eşiği 0.50'ye çektim (Daha katı)
THRESHOLD = 0.50

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
key_index = 0

@app.route('/')
def health(): return "media security active", 200

def scan_content(img_data):
    global key_index
    for _ in range(len(SIGHT_KEYS)):
        current = SIGHT_KEYS[key_index % len(SIGHT_KEYS)]
        try:
            # MODELLER: Nudity, Violence, WAD (Silah/Uyuşturucu), Minor (CSAM), Animal Welfare
            r = requests.post('https://api.sightengine.com/1.0/check.json', 
                             files={'media': ('img.jpg', img_data)}, 
                             data={
                                 'models': 'nudity-2.0,wad,violence,minor,animal-welfare', 
                                 'api_user': current["user"], 
                                 'api_secret': current["key"]
                             }, timeout=15)
            res = r.json()
            if res.get("status") == "success":
                scores = []
                
                # 1. Müstehcenlik & Porno
                nude = res.get("nudity", {})
                scores.extend([nude.get("sexual_activity", 0), nude.get("sexual_display", 0), nude.get("erotica", 0)])
                
                # 2. Şiddet, Silahlar, Yasadışı Maddeler (WAD)
                scores.append(res.get("violence", 0))
                scores.append(res.get("weapon", 0))
                scores.append(res.get("drugs", 0))
                
                # 3. CSAM (Çocuk İstismarı tespiti için 'minor' modeli)
                minor = res.get("minor", {})
                scores.append(minor.get("prob", 0))
                
                # 4. Hayvan İstismarı
                animal = res.get("animal-welfare", {})
                scores.append(animal.get("prob", 0))

                max_score = max(scores)
                logger.info(f"Medya Analiz Skoru: {max_score}")
                return max_score >= THRESHOLD
            
            key_index += 1
        except: key_index += 1
    return False

def check_and_delete(message, file_id, is_video=False):
    try:
        f_info = bot.get_file(file_id)
        content = bot.download_file(f_info.file_path)
        should_delete = False
        
        if is_video:
            t_path = f"tmp_{file_id}.mp4"
            with open(t_path, "wb") as f: f.write(content)
            cap = cv2.VideoCapture(t_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            # Videodan 5 farklı kare alarak sızma ihtimalini bitiriyoruz
            for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total_frames * p))
                ret, frame = cap.read()
                if ret:
                    _, buf = cv2.imencode('.jpg', frame)
                    if scan_content(buf.tobytes()):
                        should_delete = True
                        break
            cap.release()
            if os.path.exists(t_path): os.remove(t_path)
        else:
            if scan_content(content): should_delete = True

        if should_delete:
            bot.delete_message(message.chat.id, message.message_id)
            logger.warning(f"KRİTİK İHLAL SİLİNDİ: {message.chat.id}")
    except: pass

# SADECE MEDYA TÜRLERİ (Metin mesajlarını ellemez)
@bot.message_handler(content_types=['photo', 'video', 'animation', 'video_note', 'sticker', 'document'])
def handle_media(message):
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

# Metin mesajlarını görmezden gelmek için handler boş bırakılabilir veya hiç eklenmez.
# Bot bu haliyle sadece yukarıdaki content_types listesine tepki verir.

def run_bot():
    while True:
        try:
            bot.remove_webhook()
            logger.info("Bot Online: Medya koruması devrede.")
            bot.infinity_polling(skip_pending=True, timeout=60)
        except Exception as e:
            logger.error(f"Hata: {e}")
            time.sleep(5)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, use_reloader=False), daemon=True).start()
    run_bot()
