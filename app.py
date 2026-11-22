import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask
from gradio_client import Client, handle_file

# --- 1. SOZLAMALAR VA KO'P TOKENLAR ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
raw_tokens = os.environ.get("HF_TOKENS", "")
HF_TOKEN_LIST = [t.strip() for t in raw_tokens.split(",") if t.strip()]

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
user_modes = {}

# --- 2. 24/7 SERVER UCHUN FLASK ---
@app.route('/')
def home():
    return "Super AI Bot 24/7 ishlayapti!"

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

# --- 3. TUGMALAR MENYUSI ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🤖 AI Suhbat"),
        types.KeyboardButton("🇬🇧 Tarjimon (UZ <-> EN)"),
        types.KeyboardButton("🎬 Rasmni jonlantirish")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_modes[message.chat.id] = 'chat'
    bot.send_message(
        message.chat.id,
        "👋 Salom! Men **Super AI Bot**man.\n\nQuyidagi bo'limlardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# --- 4. REJIMLAR ---
@bot.message_handler(func=lambda msg: msg.text in ["🤖 AI Suhbat", "🇬🇧 Tarjimon (UZ <-> EN)", "🎬 Rasmni jonlantirish"])
def switch_mode(message):
    chat_id = message.chat.id
    if message.text == "🤖 AI Suhbat":
        user_modes[chat_id] = 'chat'
        bot.send_message(chat_id, "🤖 **AI Suhbat rejimi yoqildi.** Savolingizni yozing:", parse_mode="Markdown")
    elif message.text == "🇬🇧 Tarjimon (UZ <-> EN)":
        user_modes[chat_id] = 'translate'
        bot.send_message(chat_id, "🇬🇧 **Tarjimon rejimi yoqildi.** Matn yuboring:", parse_mode="Markdown")
    elif message.text == "🎬 Rasmni jonlantirish":
        user_modes[chat_id] = 'animate'
        bot.send_message(chat_id, "🎬 **Rasm jonlantirish rejimi.** Rasm yuboring va tagiga harakatni yozing:", parse_mode="Markdown")

# --- 5. BEPUL MATNLI AI ---
def ask_free_ai(prompt):
    try:
        url = f"https://pollinations.ai{requests.utils.quote(prompt)}"
        res = requests.get(url, timeout=30)
        if res.status_code == 200:
            return res.text
        return "⚠️ AI serverida vaqtinchalik uzilish."
    except Exception as e:
        return f"⚠️ Xatolik: {str(e)}"

# --- 6. RASM JONLANTIRISH (KO'P TOKEN + ZAXIRA SPACE) ---
VIDEO_SPACES = [
    "Wan-AI/Wan2.1",
    "Lightricks/LTX-Video",
    "ByteDance/AnimateDiff-Lightning"
]

def animate_image_safe(image_path, prompt_text):
    last_error = "Tokenlar kiritilmagan"
    tokens_to_try = HF_TOKEN_LIST if HF_TOKEN_LIST else [None]
    
    for token in tokens_to_try:
        for space_id in VIDEO_SPACES:
            try:
                client = Client(space_id, hf_token=token)
                result = client.predict(
                    image=handle_file(image_path),
                    prompt=prompt_text,
                    api_name="/predict"
                )
                if isinstance(result, (list, tuple)):
                    return result, None
                elif isinstance(result, dict) and 'video' in result:
                    return result['video'], None
                return result, None
            except Exception as e:
                last_error = str(e)
                continue
    return None, last_error

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    caption = message.caption if message.caption else "Animate this image naturally, keep face clear"
    wait_msg = bot.reply_to(message, "⏳ Rasm qabul qilindi. Jonlantirilmoqda, 30-60 soniya kuting...")
    
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_img = f"temp_{chat_id}.jpg"
        with open(temp_img, 'wb') as f:
            f.write(downloaded_file)
            
        video_path, error = animate_image_safe(temp_img, caption)
        
        if video_path and os.path.exists(str(video_path)):
            with open(video_path, 'rb') as video:
                bot.send_video(chat_id, video, caption=f"🎬 Tayyor: Rasm jonlantirildi!\n📝 Izoh: {caption}")
            bot.delete_message(chat_id, wait_msg.message_id)
        else:
            bot.edit_message_text(
                f"❌ Barcha GPU tokenlar/serverlar band yoki limit tugagan.\n\nXato: {error[:150]}",
                chat_id, wait_msg.message_id
            )
        if os.path.exists(temp_img):
            os.remove(temp_img)
    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik: {str(e)}", chat_id, wait_msg.message_id)

# --- 7. MATNLI XABARLAR ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    mode = user_modes.get(chat_id, 'chat')
    bot.send_chat_action(chat_id, 'typing')
    
    if mode == 'translate':
        prompt = f"Translate accurately between Uzbek and English. Only return the translation:\n\n{message.text}"
        reply = ask_free_ai(prompt)
        bot.reply_to(message, f"🇬🇧 **Tarjima:**\n\n{reply}", parse_mode="Markdown")
    else:
        prompt = f"Answer clearly and helpfully in Uzbek language:\n\n{message.text}"
        reply = ask_free_ai(prompt)
        bot.reply_to(message, reply)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
                  
