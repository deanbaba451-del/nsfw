import os
import threading
import requests
import telebot
from flask import Flask
import cv2

# Yapılandırma
TOKEN = "8680617687:AAEYm5IqL63Ex_I6cJDDQURSemKM2uTcJy0"
SIGHT_USERS = ["713471034", "1773861365", "402404015", "1968951124"]
SIGHT_KEYS = ["FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz", "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"]
THRESHOLD = 0.60

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
key_index = 0

@app.route('/')
def health(): return "1", 200

def scan_content(img_data):
    global key_index
    for _ in range(len(SIGHT_USERS)):
        u = SIGHT_USERS[key_index % len(SIGHT_USERS)]
        k = SIGHT_KEYS[key_index % len(SIGHT_KEYS)]
        try:
            r = requests.post('https://api.sightengine.com/1.0/check.json', 
                             files={'media': img_data}, 
                             data={'models': 'nudity-2.0,wad,violence', 'api_user': u, 'api_secret': k}, 
                             timeout=10)
            res = r.json()
            if res.get("status") == "success":
                nude = res.get("nudity", {})
                scores = [nude.get("sexual_activity", 0), nude.get("sexual_display", 0),
                          nude.get("erotica", 0), res.get("weapon", 0),
                          res.get("drugs", 0), res.get("violence", 0)]
                return max(scores) >= THRESHOLD
            key_index += 1
        except: key_index += 1
    return False

def check_media(message, file_id, is_video=False):
    try:
        f_info = bot.get_file(file_id)
        content = bot.download_file(f_info.file_path)
        frames = []
        
        if is_video:
            fname = f"temp_{file_id}.mp4"
            with open(fname, "wb") as f: f.write(content)
            cap = cv2.VideoCapture(fname)
            fps = cap.get(cv2.CAP_PROP_FPS) or 24
            count = 0
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret or len(frames) > 10: break # Max 10 kare kontrolü (hız için)
                if count % int(fps * 2) == 0:
                    _, buf = cv2.imencode('.jpg', frame)
                    frames.append(buf.tobytes())
                count += 1
            cap.release()
            if os.path.exists(fname): os.remove(fname)
        else:
            frames.append(content)

        for img in frames:
            if scan_content(img):
                bot.delete_message(message.chat.id, message.message_id)
                break
    except: pass

@bot.message_handler(content_types=['photo', 'video', 'sticker', 'animation', 'video_note'])
def handle_incoming(message):
    fid = None
    is_v = False
    if message.photo: fid = message.photo[-1].file_id
    elif message.video: fid, is_v = message.video.file_id, True
    elif message.animation: fid, is_v = message.animation.file_id, True
    elif message.video_note: fid, is_v = message.video_note.file_id, True
    elif message.sticker: fid = message.sticker.thumbnail.file_id if message.sticker.thumbnail else message.sticker.file_id

    if fid:
        threading.Thread(target=check_media, args=(message, fid, is_v)).start()

if __name__ == "__main__":
    p = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=p)).start()
    bot.infinity_polling()
