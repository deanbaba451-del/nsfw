import os
import threading
import requests
import telebot
from flask import Flask
import cv2
import time

# GÜNCEL TOKEN
TOKEN = "8651145622:AAGuj8UpsK5l6re41cEncpiX2HDhC1J_Pis"

# SIGHTENGINE AYARLARI
SIGHT_KEYS = [
    {"user": "713471034", "key": "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd"},
    {"user": "1773861365", "key": "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd"},
    {"user": "402404015", "key": "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz"},
    {"user": "1968951124", "key": "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"}
]
THRESHOLD = 0.60

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
key_index = 0

@app.route('/')
def health(): return "ready to fuck content", 200

# Bot gruba girdiğinde veya yetki aldığında tetiklenir
@bot.my_chat_member_handler()
def on_join(message):
    try:
        if message.new_chat_member.status in ["administrator", "member"]:
            bot.send_message(message.chat.id, "i'm ready to fuck inappropriate content")
    except: pass

def scan_content(img_data):
    global key_index
    for _ in range(len(SIGHT_KEYS)):
        current = SIGHT_KEYS[key_index % len(SIGHT_KEYS)]
        try:
            r = requests.post('https://api.sightengine.com/1.0/check.json', 
                             files={'media': ('img.jpg', img_data)}, 
                             data={'models': 'nudity-2.0,wad,violence', 'api_user': current["user"], 'api_secret': current["key"]}, 
                             timeout=10)
            res = r.json()
            if res.get("status") == "success":
                nude = res.get("nudity", {})
                vals = [
                    nude.get("sexual_activity", 0), 
                    nude.get("sexual_display", 0),
                    nude.get("erotica", 0), 
                    res.get("violence", 0),
                    res.get("weapon", 0)
                ]
                if max(vals) >= THRESHOLD: return True
                return False
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
            # Videonun %20, %50 ve %80'inden kare alıp kontrol et
            for p in [0.2, 0.5, 0.8]:
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
            print(f"Silindi: Chat {message.chat.id} - Msg {message.message_id}")
    except Exception as e:
        print(f"Hata oluştu: {e}")

@bot.message_handler(content_types=['photo', 'video', 'animation', 'video_note', 'sticker'])
def handle_media(message):
    fid = None
    is_v = False
    if message.photo: fid = message.photo[-1].file_id
    elif message.video: fid, is_v = message.video.file_id, True
    elif message.animation: fid, is_v = message.animation.file_id, True
    elif message.video_note: fid, is_v = message.video_note.file_id, True
    elif message.sticker and not message.sticker.is_animated:
        fid = message.sticker.thumbnail.file_id if message.sticker.thumbnail else message.sticker.file_id

    if fid:
        threading.Thread(target=check_and_delete, args=(message, fid, is_v)).start()

if __name__ == "__main__":
    # Flask sunucusunu ayrı kanalda başlat
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, use_reloader=False)).start()
    
    # Konfliktleri (Çakışmaları) kökten temizle
    bot.remove_webhook()
    time.sleep(1) 
    
    print("Bot başlatılıyor...")
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=20)
