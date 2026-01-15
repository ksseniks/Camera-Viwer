import os
import asyncio
from datetime import datetime
from telegram.ext import Application
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ------------------------------ MAIN VARIABLES --------------------------------#
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
TOKEN = '8006408853:AAHsjAim2SGRcL3yGnPtV9iQj88RAjZwRd0'
SUBSCRIBED_USERS = [771109895, 1078694398]

# ------------------------------ VIDEO HANDLER --------------------------------#
class VideoHandler(FileSystemEventHandler):
    def __init__(self, application, loop):
        self.application = application
        self.loop = loop

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith('.mp4'):
            return

        asyncio.run_coroutine_threadsafe(self.handle_video(event.src_path), self.loop)

    async def handle_video(self, video_path):
        try:
            for chat_id in SUBSCRIBED_USERS:
                try:
                    await self.application.bot.send_video(chat_id, video_path, timeout=120)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Отправлено {video_path} пользователю {chat_id}")
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка отправки пользователю {chat_id}: {e}")

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка при обработке видео {video_path}: {e}")

# ------------------------------ MAIN --------------------------------#
def main(args=None):
    application = Application.builder().token(TOKEN).build()

    watchFolder = os.path.join(os.path.dirname(BASE_DIR), "recordings", "events")
    os.makedirs(watchFolder, exist_ok=True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    event_handler = VideoHandler(application, loop)
    observer = Observer()
    observer.schedule(event_handler, watchFolder, recursive=True)
    observer.start()

    try:
        application.run_polling()
    finally:
        observer.stop()
        observer.join()

if __name__ == '__main__':
    main()
