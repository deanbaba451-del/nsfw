import os
import threading
import requests
import telebot
from flask import Flask
import cv2
import io

# Yeni Token ve Mevcut API Anahtarları
TOKEN = "8651145622:AAEzKO_9XJmNHr1Qm03JzhFkXzz3u-rx3Bw"
SIGHT_USERS = ["713471034", "1773861365", "402404015", "1968951124"]
SIGHT_KEYS = ["FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz", "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"]
THRESHOLD = 0.60

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
key_index = 0

@app.route('/')
def health(): return "bot active", 200

# Bot gruba eklendiğinde veya yetki aldığında mesaj atar
@bot.my_chat_member_handler()
def on_join(message):
    if message.new_chat_member.status in ["administrator", "member"]:
        bot.send_message(message.chat.id, "i'm ready to fuck inappropriate content")

def scan_content(img_data):
    global key_index
    for _ in range(len(SIGHT_USERS)):
        u = SIGHT_USERS[key_index % len(SIGHT_USERS)]
        k = SIGHT_KEYS[key_index % len(SIGHT_KEYS)]
        try:
            r = requests.post('https://api.sightengine.com/1.0/check.json', 
                             files={'media': ('image.jpg', img_data)}, 
                             data={'models': 'nudity-2.0,wad,violence', 'api_user': u, 'api_secret': k}, 
                             timeout=12)
            res = r.json()
            if res.get("status") == "success":
                nude = res.get("nudity", {})
                scores = [
                    nude.get("sexual_activity", 0), nude.get("sexual_display", 0),
                    nude.get("erotica", 0), res.get("weapon", 0),
                    res.get("drugs", 0), res.get("violence", 0)
                ]
                if max(scores) >= THRESHOLD:
                    return True
                return False
            key_index += 1
        except: 
            key_index += 1
    return False

def process_media(message, file_id, is_video=False):
    try:
        f_info = bot.get_file(file_id)
        content = bot.download_file(f_info.file_path)
        
        if is_video:
            t_name = f"v_{file_id}.mp4"
            with open(t_name, "wb") as f: f.write(content)
            cap = cv2.VideoCapture(t_name)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for p in [0.2, 0.5, 0.8]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * p))
                ret, frame = cap.read()
                if ret:
                    _, buf = cv2.imencode('.jpg', frame)
                    if scan_content(buf.tobytes()):
                        bot.delete_message(message.chat.id, message.message_id)
                        break
            cap.release()
            if os.path.exists(t_name): os.remove(t_name)
        else:
            if scan_content(content):
                bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"Hata detayı: {e}")

@bot.message_handler(content_types=['photo', 'video', 'sticker', 'animation', 'video_note'])
def handle_all(message):
    fid = None
    is_v = False
    if message.photo: fid = message.photo[-1].file_id
    elif message.video: fid, is_v = message.video.file_id, True
    elif message.animation: fid, is_v = message.animation.file_id, True
    elif message.video_note: fid, is_v = message.video_note.file_id, True
    elif message.sticker: 
        fid = message.sticker.thumbnail.file_id if message.sticker.thumbnail else message.sticker.file_id

    if fid:
        threading.Thread(target=process_media, args=(message, fid, is_v)).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, use_reloader=False)).start()
    bot.infinity_polling(skip_pending=True, timeout=60)
