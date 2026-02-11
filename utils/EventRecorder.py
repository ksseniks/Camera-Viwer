import cv2
import os
import time
import threading
from datetime import datetime
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
    detector = Detector(
        model_name=settings["modelName"],
    )
    while not cam.get("stop", False):
        if (cam['eventQueue'].qsize() > int(cam["event_duration_seconds"] * cam["fps"] * 2 - 1)):
            frame = cam["eventQueue"].get()
            if detector.detectPeople(frame, cam):
                writeLog("Обнаружен объект! Начало записи события", cam["name"])
                save_event_video(cam, cam["fps"], settings)

# =============================================================================
# ----------------------------- SAVE EVENT VIDEO -------------------------------
def save_event_video(cam, fps, settings):
    event_dir = os.path.join("recordings", "events")
    os.makedirs(event_dir, exist_ok=True)

    cameraName = cam["name"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S") 
    filepath = os.path.join(event_dir, f"{cameraName}_event_{timestamp}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    all_frames = []
    while not cam["eventQueue"].empty():
        try:
            frame = cam["eventQueue"].get(False)
            all_frames.append(frame)
        except:
            break
    
    needed_frames = int(cam["event_duration_seconds"] * fps + fps * 2)
    frames_batch = all_frames[-needed_frames:] if len(all_frames) >= needed_frames else all_frames
    
    if frames_batch:
        height, width = frames_batch[0].shape[:2]
        out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
        
        for frame in frames_batch:
            out.write(frame)
        
        out.release()
        writeLog(f"Событие сохранено: {filepath}", cam["name"])
        FolderCleaner(event_dir, settings["countEventVideo"])
