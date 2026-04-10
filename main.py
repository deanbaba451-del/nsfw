import telebot
import requests
import io
import os
import tempfile
import subprocess
from PIL import Image
from threading import Thread
from flask import Flask

TOKEN = "8680617687:AAEYm5IqL63Ex_I6cJDDQURSemKM2uTcJy0"

# api anahtarlari
SIGHT_USERS = ["713471034", "1773861365", "402404015", "1968951124"]
SIGHT_KEYS = ["FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz", "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"]

THRESHOLD = 0.40  # düşürüldü
API_INDEX = 0

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "bot calisiyor"

def get_api_creds():
    global API_INDEX
    user = SIGHT_USERS[API_INDEX % len(SIGHT_USERS)]
    key = SIGHT_KEYS[API_INDEX % len(SIGHT_KEYS)]
    API_INDEX += 1
    return user, key

def scan_content(img_data):
    user, key = get_api_creds()
    params = {
        'models': 'nudity-2.1,weapon,alcohol,drugs,offensive,gore,child',
        'api_user': user,
        'api_secret': key
    }
    files = {'media': ('file.jpg', img_data)}
    
    try:
        r = requests.post('https://api.sightengine.com/1.0/check.json', 
                         files=files, data=params, timeout=10)
        res = r.json()
        
        if res.get("status") != "success":
            return False, 0

        scores = []
        
        # nudity
        nude = res.get("nudity", {})
        scores.extend([
            nude.get("sexual_activity", 0),
            nude.get("sexual_display", 0),
            nude.get("erotica", 0),
            nude.get("suggestive", 0),
            nude.get("raw", 0),
            nude.get("partial", 0)
        ])
        
        # weapon
        weapon = res.get("weapon", {})
        scores.append(weapon.get("classes", {}).get("firearm", 0))
        scores.append(weapon.get("classes", {}).get("knife", 0))
        scores.append(weapon.get("prob", 0))
        
        # alcohol
        alcohol = res.get("alcohol", {})
        scores.append(alcohol.get("prob", 0))
        
        # drugs
        drugs = res.get("drugs", {})
        scores.append(drugs.get("prob", 0))
        
        # gore
        gore = res.get("gore", {})
        scores.append(gore.get("prob", 0))
        
        # offensive
        off = res.get("offensive", {})
        scores.append(off.get("prob", 0))
        
        # child
        child = res.get("child", {})
        scores.append(child.get("prob", 0))
        
        # scam
        scam = res.get("scam", {})
        scores.append(scam.get("prob", 0))
        
        high_score = max(scores) if scores else 0
        print(f"skor: {high_score} - kategoriler: {res.keys()}")  # debug
        return high_score >= THRESHOLD, high_score
    except Exception as e:
        print(f"api hatasi: {e}")
        return False, 0

def extract_video_frames(video_data):
    frames = []
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
        tmp.write(video_data)
        tmp_path = tmp.name
    
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
               '-of', 'default=noprint_wrappers=1:nokey=1', tmp_path]
        duration = float(subprocess.check_output(cmd).decode().strip())
        
        # 5 farklı noktadan frame al (daha kapsamlı)
        check_points = [0.1, duration*0.25, duration*0.5, duration*0.75, duration-0.5]
        check_points = [p for p in check_points if p < duration]
        
        for pt in check_points:
            out_frame = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            cmd = ['ffmpeg', '-ss', str(pt), '-i', tmp_path, 
                   '-vframes', '1', '-q:v', '2', out_frame.name, '-y']
            subprocess.run(cmd, capture_output=True, timeout=5)
            
            if os.path.getsize(out_frame.name) > 0:
                with open(out_frame.name, 'rb') as f:
                    frames.append(f.read())
            os.unlink(out_frame.name)
            
    except Exception as e:
        print(f"frame hatasi: {e}")
    finally:
        os.unlink(tmp_path)
    
    return frames

def process_media(message, file_id, media_type="photo"):
    try:
        file_info = bot.get_file(file_id)
        content = bot.download_file(file_info.file_path)
        
        if media_type in ["photo", "sticker"]:
            img = Image.open(io.BytesIO(content))
            if img.mode != 'RGB':
                img = img.convert("RGB")
            # kaliteyi düşürüp boyutu küçült (hızlı upload)
            img.thumbnail((800, 800))
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=70)
            processed = out.getvalue()
            
            is_bad, score = scan_content(processed)
            if is_bad:
                delete_silent(message)
                
        elif media_type in ["video", "animation", "gif"]:
            frames = extract_video_frames(content)
            for frame_data in frames:
                is_bad, score = scan_content(frame_data)
                if is_bad:
                    delete_silent(message)
                    break
                    
    except Exception as e:
        print(f"islem hatasi: {e}")

def delete_silent(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
        print(f"silindi: {message.chat.id}")
    except Exception as e:
        print(f"silme hatasi: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.type != 'private':
        text = "sildiklerim:\n"
        text += "- ciplaklik/porno\n"
        text += "- siddet/vahset/gore\n"
        text += "- silah/uyusturucu/alkol\n"
        text += "- cocuk/hayvan istismari\n"
        text += "- telegram tos ihlalleri"
        bot.reply_to(message, text)
    else:
        markup = telebot.types.InlineKeyboardMarkup()
        btn = telebot.types.InlineKeyboardButton(
            "beni gruba ekle", 
            url=f"https://t.me/{bot.get_me().username}?startgroup=true"
        )
        markup.add(btn)
        text = "sildiklerim:\n"
        text += "- ciplaklik/porno\n"
        text += "- siddet/vahset/gore\n"
        text += "- silah/uyusturucu/alkol\n"
        text += "- cocuk/hayvan istismari\n"
        text += "- telegram tos ihlalleri"
        bot.reply_to(message, text, reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    Thread(target=process_media, args=(message, message.photo[-1].file_id, "photo")).start()

@bot.message_handler(content_types=['video'])
def handle_video(message):
    Thread(target=process_media, args=(message, message.video.file_id, "video")).start()

@bot.message_handler(content_types=['animation'])
def handle_animation(message):
    Thread(target=process_media, args=(message, message.animation.file_id, "animation")).start()

@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    fid = message.sticker.thumbnail.file_id if message.sticker.thumbnail else message.sticker.file_id
    Thread(target=process_media, args=(message, fid, "sticker")).start()

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if message.document.mime_type and any(t in message.document.mime_type for t in ['image', 'video', 'gif']):
        Thread(target=process_media, args=(message, message.document.file_id, "photo")).start()

def run_flask():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.infinity_polling(timeout=30, long_polling_timeout=15)