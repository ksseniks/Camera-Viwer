import os
import cv2
import time
import shutil
import threading
from datetime import datetime

# =============================================================================
# ----------------------------- LOGGING ---------------------------------------
def writeLog(message: str, cameraName: str):
    str = f"[{datetime.now().strftime('%H:%M:%S')}] "
    if cameraName:
        str = str + f"[{cameraName}] "

    str = str + message
    print(str)

# =============================================================================
# ----------------------------- FOLDER CLEANER --------------------------------
def FolderCleaner(folderPath, counter):
    if not os.path.exists(folderPath):
        return

    files = [f for f in os.listdir(folderPath)
             if os.path.exists(os.path.join(folderPath, f))]

    if not files:
        return
    
    files.sort(key=lambda f: os.path.getctime(os.path.join(folderPath, f)))

    if len(files) > counter:
        to_delete = files[:len(files) - counter]

        for item in to_delete:
            item_path = os.path.join(folderPath, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    writeLog(f"Удалена папка: {item_path}", None)
                elif os.path.isfile(item_path):
                    os.remove(item_path)
                    writeLog(f"Удален файл: {item_path}", None)
            except Exception as e:
                writeLog(f"Ошибка удаления {item_path}: {e}", None)

# =============================================================================
# ----------------------------- BACKGROUND TASKS ------------------------------
def start_background_tasks(config):
    from utils.EventRecorder import EventRecorder
    from utils.VideoRecorder import StartRecordingCameras
    from bots.CameraAlertBot import main as RunCameraAlert

    threading.Thread(
        target=StartRecordingCameras,
        args=(config,),
        daemon=True
    ).start()

    threading.Thread(
        target=RunCameraAlert,
        args=(config,),
        daemon=True
    ).start()

    threading.Thread(
        target=EventRecorder,
        args=(config,),
        daemon=True
    ).start()

# =============================================================================
# ----------------------------- START CAMERA ------------------------------
def start_camera(cam, config):

    from utils.EventRecorder import startCameraEvent
    from utils.VideoRecorder import StartRecordCamera

    from queue import Queue
    if "frameQueue" not in cam:
        cam["frameQueue"] = Queue()

    threading.Thread(
        target=camera_reader,
        args=(cam,),
        daemon=True
    ).start()

    threading.Thread(
        target=StartRecordCamera,
        args=(cam,),
        daemon=True
    ).start()

    settings = config.get_settings()
    threading.Thread(
        target=startCameraEvent,
        args=(cam, settings),
        daemon=True
    ).start()

# =============================================================================
# ----------------------------- FLASK STARTER ---------------------------------
def camera_reader(cam):
    cap = None
    while not cam.get("stop", False):
        if cap is None:
            cap = cv2.VideoCapture(cam["stream_view"])
            if not cap.isOpened():
                writeLog(f"Не удалось открыть поток {cam['name']}, повтор через 3 сек", None)
                time.sleep(3)
                cap.release()
                cap = None
                continue

        ok, frame = cap.read()

        if not ok:
            writeLog(f"Поток потерян, переподключение...", cam['name'])
            cap.release()
            cap = None
            time.sleep(1)
            continue

        if cam["frameQueue"].qsize() > 10:
            cam["frameQueue"].get()

        cam["frameQueue"].put(frame)

    if cap:
        cap.release()


def start_flask(config):
    for cam in config.get_cameras():
        t = threading.Thread(target=camera_reader, args=(cam,), daemon=True)
        t.start()

    from server.app import run_app
    run_app(config)

# =============================================================================
# ----------------------------- MAIN ------------------------------------------
if __name__ == "__main__":
    from utils.CameraConfig import CameraConfig
    config = CameraConfig()
    config.load()

    start_background_tasks(config)
    start_flask(config)

    while True:
        time.sleep(1)
