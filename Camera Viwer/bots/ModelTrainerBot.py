import os
import uuid
import asyncio
from datetime import datetime
from telegram.request import HTTPXRequest
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes
import telegram.error
import subprocess

#=============================================================================#
# ------------------------------ MAIN VARIABLES -------------------------------- #
TOKEN = "8136922896:AAF2wKvH_Al3emHtPc6g8wSjVXAF53c6ork"
CHAT_ID = 771109895

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORD_FOLDER = os.path.join(os.path.dirname(BASE_DIR), "recordings")
UNVERIFIED_DIR = os.path.join(RECORD_FOLDER, "unverified")

DATA_FOLDER = os.path.join(os.path.dirname(BASE_DIR), "data", "train")
POSITIVE_IMAGES_DIR = os.path.join(DATA_FOLDER, "images", "positive")
NEGATIVE_IMAGES_DIR = os.path.join(DATA_FOLDER, "images", "negative")
POSITIVE_LABELS_DIR = os.path.join(DATA_FOLDER, "labels", "positive")
NEGATIVE_LABELS_DIR = os.path.join(DATA_FOLDER, "labels", "negative")

for directory in [
    UNVERIFIED_DIR,
    POSITIVE_IMAGES_DIR,
    NEGATIVE_IMAGES_DIR,
    POSITIVE_LABELS_DIR,
    NEGATIVE_LABELS_DIR,
]:
    os.makedirs(directory, exist_ok=True)

# ------------------------------ GLOBAL VARIABLES -------------------------------- #
pendingFrames = {}
frameQueue = []  
SEND_DELAY = 3.5 

#=============================================================================#
# ------------------------------ SAFE SEND MESSAGE -------------------------------- #
async def SafeSendMessage(bot: Bot, chat_id: int, text: str):
    try:
        await asyncio.sleep(SEND_DELAY)
        await bot.send_message(chat_id=chat_id, text=text)
    except telegram.error.RetryAfter as e:
        wait_time = int(e.retry_after) + 2
        await asyncio.sleep(wait_time)
        await SafeSendMessage(bot, chat_id, text)
    except telegram.error.TimedOut:
        await asyncio.sleep(3)
        await SafeSendMessage(bot, chat_id, text)
    except Exception:
        await asyncio.sleep(2)
        await SafeSendMessage(bot, chat_id, text)

#=============================================================================#
# ------------------------------ SEND FRAME -------------------------------- #
async def SendNextFrame(context: ContextTypes.DEFAULT_TYPE):
    global frameQueue
    if not frameQueue:
        return

    framePath = frameQueue.pop(0)
    if not os.path.exists(framePath):
        asyncio.create_task(SendNextFrame(context))
        return

    frame_id = uuid.uuid4().hex[:8]
    pendingFrames[frame_id] = framePath

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Человек", callback_data=f"yes|{frame_id}")],
        [InlineKeyboardButton("❌ Нет", callback_data=f"no|{frame_id}")]
    ])

    try:
        await asyncio.sleep(SEND_DELAY)
        with open(framePath, "rb") as photo:
            await context.bot.send_photo(
                chat_id=CHAT_ID,
                photo=photo,
                caption=f"🚨 Есть человек в кадре?\n\nОсталось: {len(frameQueue)}",
                reply_markup=keyboard,
            )
    except (telegram.error.RetryAfter, telegram.error.TimedOut, Exception):
        await asyncio.sleep(SEND_DELAY)
        asyncio.create_task(SendNextFrame(context))

#=============================================================================#
# ------------------------------ HANDLE ANSWER -------------------------------- #
async def HandleAnswer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        answer, frame_id = query.data.split("|")
        imagePath = pendingFrames.get(frame_id)
        if not imagePath:
            await query.delete_message()
            return

        txtName = os.path.splitext(os.path.basename(imagePath))[0] + ".txt"
        txtPath = os.path.join(UNVERIFIED_DIR, txtName)

        if not os.path.exists(imagePath) or not os.path.exists(txtPath):
            await query.delete_message()
            pendingFrames.pop(frame_id, None)
            asyncio.create_task(SendNextFrame(context))
            return

        if answer == "yes":
            target_img_dir = POSITIVE_IMAGES_DIR
            target_label_dir = POSITIVE_LABELS_DIR
        else:
            target_img_dir = NEGATIVE_IMAGES_DIR
            target_label_dir = NEGATIVE_LABELS_DIR

        os.makedirs(target_img_dir, exist_ok=True)
        os.makedirs(target_label_dir, exist_ok=True)

        txtTargetPath = os.path.join(target_label_dir, txtName)
        targetPath = os.path.join(target_img_dir, os.path.basename(imagePath))

        os.replace(imagePath, targetPath)
        os.replace(txtPath, txtTargetPath)

        pendingFrames.pop(frame_id, None)
        await query.delete_message()

        asyncio.create_task(SendNextFrame(context))

    except Exception:
        asyncio.create_task(SendNextFrame(context))

#=============================================================================#
# ------------------------------ AUTO START LABELING -------------------------------- #
async def AutoStartLabeling(bot: Bot, context: ContextTypes.DEFAULT_TYPE):
    global frameQueue
    files = [
        os.path.join(UNVERIFIED_DIR, f)
        for f in os.listdir(UNVERIFIED_DIR)
        if f.lower().endswith(".jpg")
    ]
    if not files:
        await SafeSendMessage(bot, CHAT_ID, "❌ Нет новых изображений для разметки.")
        return

    frameQueue = sorted(files)
    await SafeSendMessage(bot, CHAT_ID, f"🟢 Начинаем разметку. Всего {len(frameQueue)} изображений.")
    asyncio.create_task(SendNextFrame(context))

#=============================================================================#
# ------------------------------ AUTO CHECK NEW FILES -------------------------------- #
async def AutoCheckFolder(context: ContextTypes.DEFAULT_TYPE):
    global frameQueue
    if frameQueue:
        return
    files = [
        os.path.join(UNVERIFIED_DIR, f)
        for f in os.listdir(UNVERIFIED_DIR)
        if f.lower().endswith(".jpg")
    ]
    if files:
        frameQueue = sorted(files)
        asyncio.create_task(SendNextFrame(context))

#=============================================================================#
# ------------------------------ TRAIN MODEL -------------------------------- #
async def StartTrainingModel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    await SafeSendMessage(bot, CHAT_ID, "🚀 Запуск дообучения модели...")


    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    scriptDir = os.path.abspath(os.path.join(BASE_DIR, "..", "utils"))
    subprocess.Popen(
        ["python", os.path.join(scriptDir, "TrainYolo.py")],
        cwd=scriptDir
    )

    await SafeSendMessage(bot, CHAT_ID, "✅ Дообучение запущено.")

#=============================================================================#
# ------------------------------ MAIN -------------------------------- #
def main(args=None):
    req = HTTPXRequest(connect_timeout=60, read_timeout=60, pool_timeout=30, connection_pool_size=20)
    bot = Bot(token=TOKEN, request=req)
    app = ApplicationBuilder().bot(bot).build()

    app.add_handler(CallbackQueryHandler(HandleAnswer))
    app.add_handler(CommandHandler("train", StartTrainingModel))

    async def start_job(context: ContextTypes.DEFAULT_TYPE):
        await AutoStartLabeling(bot, context)

    app.job_queue.run_once(start_job, when=1.0)
    app.job_queue.run_repeating(AutoCheckFolder, interval=60, first=10)

    print("[INFO] Bot запущен. Автоматически начинаем разметку...")
    app.run_polling()

if __name__ == "__main__":
    main()
