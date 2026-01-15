import cv2
import os
import time
import threading
from collections import deque

from main import writeLog, FolderCleaner
from utils.CameraMotionDetector import CameraMotionDetector as Detector

PREBUFFER_FRAMES = 30 
# =============================================================================
# ----------------------------- EVENT RECORDER -------------------------------
def EventRecorder(config):
    threads = []
    CAMERAS = config.get_cameras()
    settings = config.get_settings()
    for cam in CAMERAS:
        t = threading.Thread(target=startCameraEvent, args=(cam, settings), daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

# =============================================================================
# ----------------------------- PROCESS CAMERA EVENTS -------------------------------
def startCameraEvent(cam, settings):
    url = cam["stream_record"]
    event_duration = cam["event_duration_seconds"]

    detector = Detector(
        roi=cam["roi"],
        threshold=cam["threshold"],
        minWeight=cam["minWeight"],
        model_name=settings["modelName"],
        searchObjectList=cam["searchObjectList"],
        min_motion_frames = 3,
        max_rois=3 ,
        min_motion_area = 500,
    )

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    while True:
        if not cap.isOpened():
            writeLog(f"Камера недоступна, повтор через 3 сек", cam["name"])
            time.sleep(3)
            continue
        else:
            writeLog(f"Начат поиск обьекта", cam["name"])
            break
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    buffer_frames = deque(maxlen=PREBUFFER_FRAMES)

    while not cam.get("stop", False):
        ret, frame = cap.read()
        if not ret:
            writeLog(f"Камера отключилась, пересоздаю поток"), cam["name"]
            cap.release()
            time.sleep(3)
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            continue

        buffer_frames.append(frame)

        if detector.detect_people(frame):
            writeLog("Обнаружен объект! Начало записи события", cam["name"])
            save_event_video(cam, list(buffer_frames), fps, event_duration)
            buffer_frames.clear()

    if cap:
        cap.release()

# =============================================================================
# ----------------------------- SAVE EVENT VIDEO -------------------------------
def save_event_video(cam, frames_before, fps, event_duration):
    event_dir = os.path.join("recordings", "events")
    os.makedirs(event_dir, exist_ok=True)

    filepath = os.path.join(event_dir, "event.mp4")
    height, width = frames_before[-1].shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    for frame in frames_before:
        out.write(frame)

    cap = cv2.VideoCapture(cam["stream_view"], cv2.CAP_FFMPEG)
    start = time.time()
    while time.time() - start < event_duration:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)

    cap.release()
    out.release()
    writeLog(f"Событие сохранено: {filepath}", cam["name"])

    FolderCleaner(event_dir, 20)
