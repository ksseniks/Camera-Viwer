import cv2
import os
import sys
import time
import signal
import threading
from datetime import datetime
from main import writeLog, FolderCleaner
# =============================================================================
# ----------------------------- START RECORDINGS CAMERAS-------------------------------
def StartRecordingCameras(config):
    threads = []

    for cam in config.get_cameras():
        t = threading.Thread(
            target=record_camera,
            args=(cam,),
            daemon=True
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

# =============================================================================
# ----------------------------- START RECORDINGS CAMERA-------------------------------
def StartRecordCamera(camera):
    t = threading.Thread(
        target=record_camera,
        args=(camera,),
        daemon=True
    )
    t.start()
    t.join()

# =============================================================================
# ----------------------------- EXTRA SAVE RECORDS-------------------------------
open_writers = []

def register_writer(writer):
    open_writers.append(writer)

def safe_exit(*args):
    for w in open_writers:
        try:
            w.release()
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, safe_exit)
signal.signal(signal.SIGTERM, safe_exit)

class SafeVideoWriter:
    def __init__(self, path, fps, frame_size):
        self.lock = threading.Lock()
        self.writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, frame_size)

    def write(self, frame):
        with self.lock:
            if self.writer is not None:
                self.writer.write(frame)

    def release(self):
        with self.lock:
            if self.writer is not None:
                self.writer.release()
                self.writer = None

# =============================================================================
# ----------------------------- RECORD CAMERA-------------------------------
def record_camera(cam):
    url = cam["stream_record"]
    writeLog(f"Старт постоянной записи → {url}", cam["name"])

    cap = None
    while not cam.get("stop", False):
        try:
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    writeLog(f"Камера недоступна, повтор через 3 сек", cam["name"])
                    time.sleep(3)
                    continue

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps < 1:
                fps = 25

            width = int(cap.get(3))
            height = int(cap.get(4))

            today = datetime.now().strftime("%Y-%m-%d")
            save_dir = os.path.join("recordings", "records", today, cam["name"])
            os.makedirs(save_dir, exist_ok=True)
            
            filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".mp4"
            filepath = os.path.join(save_dir, filename)

            out = SafeVideoWriter(filepath, fps, (width, height))
            register_writer(out)

            writeLog(f"Начата запись файла: {filename}", cam["name"])
            start_time = time.time()

            while not cam.get("stop", False):
                ret, frame = cap.read()
                if not ret:
                    writeLog(f"Пропал сигнал — пересоздаю поток", cam["name"])
                    cap.release()
                    cap = None
                    break

                out.write(frame)

                if time.time() - start_time >= int(cam["record_duration_minutes"]) * 60:
                    writeLog(f"Сегмент завершен: {filename}", cam["name"])
                    break
                
                if url != cam["stream_record"]:
                    break

            out.release()
            FolderCleaner(save_dir, 30)

            if url != cam["stream_record"]:
                StartRecordCamera(cam)
                if cap is not None:
                    cap.release()
                break

        except KeyboardInterrupt:
            writeLog(f"Прерывание пользователем, закрываем файл...", cam["name"])
            if cap is not None:
                cap.release()
            out.release()
            break

        except Exception as e:
            writeLog(f"Ошибка записи: {e}", cam["name"])
            if cap is not None:
                cap.release()
            out.release()
            time.sleep(3)

    if cap:
        writeLog(f"Пототок записии удален камеры ", cam["name"])
        cap.release()