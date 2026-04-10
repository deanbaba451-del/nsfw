import telebot
import requests
import io
import os
import tempfile
import subprocess
from PIL import Image
from threading import Thread

TOKEN = "8680617687:AAEYm5IqL63Ex_I6cJDDQURSemKM2uTcJy0"

# api anahtarlari buraya yaz
SIGHT_USERS = ["713471034", "1773861365", "402404015", "1968951124"]
SIGHT_KEYS = ["FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "FjffWWjDqyr9Jz7f44FsXt8ACMwBvFAd", "i7XWhsXdC75RXGZKbq5b5hLuSzqBUkwz", "JvmFQVqSKLsfCC6nmB42UiepYpYFALdB"]

THRESHOLD = 0.60
API_INDEX = 0

bot = telebot.TeleBot(TOKEN)

def get_api_creds():
    global API_INDEX
    user = SIGHT_USERS[API_INDEX % len(SIGHT_USERS)]
    key = SIGHT_KEYS[API_INDEX % len(SIGHT_KEYS)]
    API_INDEX += 1
    return user, key

def scan_content(img_data):
    user, key = get_api_creds()
    params = {
        'models': 'nudity-2.0,wad,offensive,text-content,gore',
        'api_user': user,
        'api_secret': key
    }
    files = {'media': ('file.jpg', img_data)}
    
    try:
        r = requests.post('https://api.sightengine.com/1.0/check.json', 
                         files=files, data=params, timeout=15)
        res = r.json()
        
        if res.get("status") != "success":
            return False, 0

        scores = []
        
        nude = res.get("nudity", {})
        scores.extend([
            nude.get("sexual_activity", 0),
            nude.get("sexual_display", 0),
            nude.get("erotica", 0),
            nude.get("suggestive", 0),
            nude.get("raw", 0),
            nude.get("partial", 0)
        ])
        
        scores.extend([
            res.get("weapon", 0),
            res.get("alcohol", 0),
            res.get("drugs", 0)
        ])
        
        gore = res.get("gore", {})
        scores.extend([
            gore.get("prob", 0),
            gore.get("gore", 0)
        ])
        
        off = res.get("offensive", {})
        scores.append(off.get("prob", 0))
        
        child = res.get("child", {})
        scores.append(child.get("prob", 0))
        
        high_score = max(scores) if scores else 0
        return high_score >= THRESHOLD, high_score
    except:
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
        
        check_points = [0.1, duration/2, duration-0.5] if duration > 2 else [0.1]
        
        for pt in check_points:
            out_frame = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            cmd = ['ffmpeg', '-ss', str(pt), '-i', tmp_path, 
                   '-vframes', '1', '-q:v', '2', out_frame.name, '-y']
            subprocess.run(cmd, capture_output=True)
            
            with open(out_frame.name, 'rb') as f:
                frames.append(f.read())
            os.unlink(out_frame.name)
            
    except:
        pass
    finally:
        os.unlink(tmp_path)
    
    return frames

def process_media(message, file_id, media_type="photo"):
    try:
        file_info = bot.get_file(file_id)
        content = bot.download_file(file_info.file_path)
        
        if media_type == "photo" or media_type == "sticker":
            img = Image.open(io.BytesIO(content))
            if img.mode != 'RGB':
                img = img.convert("RGB")
            out = io.BytesIO()
            img.save(out, format="JPEG")
            processed = out.getvalue()
            
            is_bad, score = scan_content(processed)
            if is_bad:
                Thread(target=delete_silent, args=(message,)).start()
                
        elif media_type in ["video", "animation", "gif"]:
            frames = extract_video_frames(content)
            for frame_data in frames:
                is_bad, score = scan_content(frame_data)
                if is_bad:
                    Thread(target=delete_silent, args=(message,)).start()
                    break
                    
    except:
        pass

def delete_silent(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass

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

if __name__ == "__main__":
    bot.infinity_polling(timeout=30, long_polling_timeout=15)