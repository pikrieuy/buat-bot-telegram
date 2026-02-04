import logging
import csv
import os
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import time, timedelta, datetime
import google.generativeai as genai
from PIL import Image 

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, 
    MessageHandler, filters, ConversationHandler, CallbackQueryHandler
)

# ==========================================
# KONFIGURASI (JANGAN LUPA ISI!)
# ==========================================
TOKEN_TELEGRAM = '8492614548:AAEsKj2WyiMNcghb6m3TOZtmTMpHGgpaz2k'
API_KEY_GEMINI = 'AIzaSyAq-Mv9xjMpULeCGbzTUnGbGRMmOTeuDQE'
CSV_FILENAME = 'jurnal_harian.csv'

genai.configure(api_key=API_KEY_GEMINI)
# Gemini Flash support audio input!
model = genai.GenerativeModel("gemini-flash-latest")

STORY, MOOD_INPUT = range(2)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# FITUR LEVEL 7: VOICE LISTENER 🎙️
# ==========================================
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fungsi ini jalan kalau user kirim VOICE NOTE
    """
    # 1. Kasih tau user bot lagi 'dengerin'
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='record_voice')
    await update.message.reply_text("Dengerin VN kamu dulu ya... 🎧")

    try:
        # 2. Ambil file audio dari Telegram
        voice_file = await update.message.voice.get_file()
        
        # 3. Download ke memori (ByteIO)
        # Kita namain 'voice.ogg' karena Gemini butuh path atau mime_type yang jelas
        voice_byte_arr = io.BytesIO()
        await voice_file.download_to_memory(voice_byte_arr)
        voice_byte_arr.seek(0)
        
        # Trik: Simpan file sementara karena Upload File Gemini butuh file fisik kadang lebih stabil
        # (Versi simple: upload bytes langsung via Gemini API terbaru)
        temp_filename = "temp_voice.ogg"
        with open(temp_filename, "wb") as f:
            f.write(voice_byte_arr.getbuffer())

        # 4. Upload Audio ke Gemini
        # Gemini butuh file ini di-upload ke server mereka dulu sebentar
        myfile = genai.upload_file(temp_filename)

        # 5. Prompt ke AI
        prompt = (
            "Dengarkan rekaman suara ini (ini adalah curhatan user). "
            "1. Transkripkan apa yang dia omongin secara ringkas. "
            "2. Berikan respon empatik dan gaul menanggapi cerita itu."
            "Format jawabannya: [TRANSKRIP]: ... \n [RESPON]: ..."
        )

        # Generate (Audio + Teks Prompt)
        response = model.generate_content([prompt, myfile])
        ai_reply = response.text
        
        # Bersihkan file temp biar ga nyampah di laptop
        os.remove(temp_filename)
        
        # 6. Simpan hasil transkrip sebagai 'Cerita User'
        # Kita ambil bagian transkripnya aja buat CSV (simple logic)
        context.user_data['story'] = f"[VOICE] {ai_reply}"
        
        await update.message.reply_text(ai_reply)

        # Lanjut minta Mood
        keyboard = [[InlineKeyboardButton("😁 Happy (3)", callback_data='3'), InlineKeyboardButton("😐 Neutral (2)", callback_data='2')],
                    [InlineKeyboardButton("😭 Sad (1)", callback_data='1'), InlineKeyboardButton("😡 Angry (0)", callback_data='0')]]
        await update.message.reply_text("Abis curhat lisan, mood gimana?", reply_markup=InlineKeyboardMarkup(keyboard))
        
        return MOOD_INPUT

    except Exception as e:
        await update.message.reply_text(f"Kupingku budeg (Error Audio): {e}")
        if os.path.exists("temp_voice.ogg"): os.remove("temp_voice.ogg")
        return ConversationHandler.END

# ==========================================
# CORE LOGIC (Foto + Teks + Konsul + Report)
# ==========================================
# (Fungsi-fungsi di bawah ini SAMA PERSIS kayak V6, cuma aku singkat biar gak kepanjangan scrollnya)

async def consult_psychologist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_q = " ".join(context.args)
    if not user_q: return await update.message.reply_text("Contoh: /konsul Kenapa aku sedih?")
    if not os.path.exists(CSV_FILENAME): return await update.message.reply_text("Data kosong.")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try:
        df = pd.read_csv(CSV_FILENAME).tail(10)
        ctx = ""
        for i, r in df.iterrows(): ctx += f"- {r['Tanggal']} ({r['Mood_Label']}): {r['Cerita']}\n"
        prompt = f"Data jurnal:\n{ctx}\nUser tanya: '{user_q}'. Analisa pola & jawab sebagai psikolog gaul."
        res = model.generate_content(prompt)
        await update.message.reply_text(f"🤖 **Analisa:**\n{res.text}", parse_mode='Markdown')
    except Exception as e: await update.message.reply_text(f"Error: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')
    await update.message.reply_text("Liat foto dulu... 🧐")
    f = await update.message.photo[-1].get_file()
    b = io.BytesIO(); await f.download_to_memory(b); b.seek(0)
    img = Image.open(b)
    try:
        res = model.generate_content(["Deskripsi foto ini 1 kalimat sbg jurnal, lalu komen seru.", img])
        context.user_data['story'] = f"[FOTO] {res.text}"
        await update.message.reply_text(f"📸 {res.text}")
        kb = [[InlineKeyboardButton("😁", callback_data='3'), InlineKeyboardButton("😐", callback_data='2')],
              [InlineKeyboardButton("😭", callback_data='1'), InlineKeyboardButton("😡", callback_data='0')]]
        await update.message.reply_text("Mood?", reply_markup=InlineKeyboardMarkup(kb))
        return MOOD_INPUT
    except Exception as e: await update.message.reply_text(f"Error: {e}"); return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    await update.message.reply_text(f"Halo! Bot V7 (Voice Edition) 🎙️\nBisa Teks, Foto, dan VOICE NOTE!\nCoba kirim VN sekarang.")
    context.job_queue.run_daily(daily_reminder, time=time(22, 00), chat_id=cid)

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id, text="🌙 Jurnal time! Kirim Teks/Foto/VN ya.")

async def manual_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌙 (Mode Test) Kirim Teks/Foto/VN!")
    return STORY

async def receive_story_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    context.user_data['story'] = txt
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    try: await update.message.reply_text(model.generate_content(f"Respon curhat ini: {txt}").text)
    except: pass
    kb = [[InlineKeyboardButton("😁", callback_data='3'), InlineKeyboardButton("😐", callback_data='2')],
          [InlineKeyboardButton("😭", callback_data='1'), InlineKeyboardButton("😡", callback_data='0')]]
    await update.message.reply_text("Rate mood:", reply_markup=InlineKeyboardMarkup(kb))
    return MOOD_INPUT

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sc = q.data; lbl = {'3':"Happy",'2':"Neutral",'1':"Sad",'0':"Angry"}.get(sc,"Unknown")
    sty = context.user_data.get('story')
    now = datetime.now()
    with open(CSV_FILENAME, 'a', newline='', encoding='utf-8-sig') as f:
        wr = csv.writer(f)
        if not os.path.isfile(CSV_FILENAME): wr.writerow(['Tanggal','Jam','Cerita','Mood_Label','Mood_Score'])
        wr.writerow([now.strftime("%d-%m-%Y"), now.strftime("%H:%M"), sty, lbl, sc])
    await q.edit_message_text("✅ Tersimpan! Good night.")
    return ConversationHandler.END

async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(CSV_FILENAME): return await update.message.reply_text("Kosong.")
    try:
        df = pd.read_csv(CSV_FILENAME)
        if len(df)<2: return await update.message.reply_text("Min 2 data.")
        plt.figure(figsize=(10,5)); plt.plot(df['Tanggal'], df['Mood_Score'], marker='o'); plt.grid(True)
        b = io.BytesIO(); plt.savefig(b, format='png'); b.seek(0); plt.close()
        await update.message.reply_photo(photo=b, caption="📈 Grafik")
    except: await update.message.reply_text("Error grafik.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Batal."); return ConversationHandler.END

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN_TELEGRAM).build()
    
    # HANDLER UTAMA
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & (~filters.COMMAND), receive_story_text),
            MessageHandler(filters.PHOTO, handle_photo),
            MessageHandler(filters.VOICE, handle_voice), # <--- INI HANDLER BARU BUAT VN
            CommandHandler('test', manual_test)
        ],
        states={
            STORY: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), receive_story_text),
                MessageHandler(filters.PHOTO, handle_photo),
                MessageHandler(filters.VOICE, handle_voice) # Di mode Story juga bisa VN
            ],
            MOOD_INPUT: [CallbackQueryHandler(button_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(CommandHandler('konsul', consult_psychologist))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('report', generate_report))
    app.add_handler(conv_handler)
    print("Bot V7 (Voice Edition) is running... 🎙️")
    app.run_polling()