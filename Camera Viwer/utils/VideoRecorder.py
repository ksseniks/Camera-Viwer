import os
import cv2
import time
import threading
import subprocess
from threading import Thread
from datetime import datetime
from utils.FolderManager import FolderCleaner
from utils.MotionDetector import CameraMotionDetector

# Folder name
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_RECORDINGS_FOLDER = os.path.join(os.path.dirname(BASE_DIR), "recordings")
TIMELAPSE_FOLDER = os.path.join(BASE_RECORDINGS_FOLDER, "timelapse")
EVENTS_FOLDER = os.path.join(BASE_RECORDINGS_FOLDER, "events")

#=============================================================================#
#------------------------------ GET FILE NAME --------------------------------#
def GetVideoSavePath(name, startTime, folder=None):
    # Create event folder
    if folder == EVENTS_FOLDER:
        return os.path.join(folder, f"{name}_{startTime.strftime('%Y%m%d_%H%M%S')}.mp4")
    
    # Create timelapse folder
    elif folder == TIMELAPSE_FOLDER:
        datedFolder = os.path.join(folder, startTime.strftime("%Y-%m-%d"))
        os.makedirs(datedFolder, exist_ok=True)

        cameraFolder = os.path.join(datedFolder, name)
        os.makedirs(cameraFolder, exist_ok=True) 

        return os.path.join(cameraFolder, f"{startTime.strftime('%H%M%S')}.avi")

#=============================================================================#
#------------------------------ BUFFER EVENT --------------------------------#
bufferData = {}
def BufferEvent(cam_name, is_recording, frame=None, EventRecord=None):
    if cam_name not in bufferData:
        bufferData[cam_name] = {
            "buffer": [],
        }

    cam_buffer = bufferData[cam_name]

    if is_recording:
        if frame is not None:
            cam_buffer["buffer"].append(frame)
    else:
        if cam_buffer["buffer"]:
            if EventRecord is not None:
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Камера "{cam_name}": передача кадров в основной поток.')
                Thread(target=EventRecord, args=(cam_buffer["buffer"],), daemon=True).start()
            cam_buffer["buffer"].clear()

        cam_buffer["isRecording"] = False

#=============================================================================#
#------------------------------ RECORD CAMERA MOTION --------------------------------#
def PeopleDetection(detector, EventRecord, cam):
    lastEventTime = 0
    while True:
        item = cam["frameQueue"].get()
        if item is None:
            break
        frame = item
        cam_name = cam["name"]
        
        currentTime = time.time()
        if currentTime - lastEventTime > cam["event_duration_seconds"]:
            BufferEvent(cam_name, True, frame)
            if detector.DetectPeopleInFrame(frame):
                lastEventTime = currentTime
                BufferEvent(cam_name, False, None, EventRecord)
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Обнаружен человек на камере "{cam_name}"')
            else:
                BufferEvent(cam_name, False)

#=============================================================================#
#------------------------------ RECORD CAMERA MOTION --------------------------------#
def RecordCameraMotion(cam):
    while True:
        #=============================================================================#
        #------------------------------ FUNCTION OPEN STREAM --------------------------------#
        def OpenStream():
            capture = cv2.VideoCapture(cam["stream_record"])
            if not capture.isOpened():
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Не удалось открыть поток записи на камере "{cam['name']}"')
                return None
            return capture

        #=============================================================================#
        #------------------------------ EVENT RECORD --------------------------------#
        def EventRecord(frames):
            # Cleaning folder
            FolderCleaner(EVENTS_FOLDER, 15)

            # Open event stream
            os.makedirs('recordings/events', exist_ok=True)
            eventCapture = OpenStream()
            if eventCapture is None:
                print(f'[{datetime.now().strftime("%H:%M:%S")}Не удалось открыть поток для записи события на камере "{cam['name']}".')
                return

            eventFileName = GetVideoSavePath(cam["name"], datetime.now(), folder=EVENTS_FOLDER)
            print(f'[{datetime.now().strftime("%H:%M:%S")}]  Начата запись события камеры "{cam['name']}" в: {eventFileName}')

            # Get configuration event stream
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            width = int(eventCapture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(eventCapture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            event = cv2.VideoWriter(eventFileName, fourcc, 15, (width, height))

            # Add frame to the buffer
            for frame in frames:
                event.write(frame)

            # Checking recorded frames
            recorded_frames = 0
            while recorded_frames < cam["event_duration_seconds"] * 15: # 15 framerate
                ret, frame = eventCapture.read()
                if not ret:
                    print(f'[{datetime.now().strftime("%H:%M:%S")}] Ошибка чтения кадра при записи события на камере "{cam['name']}"')
                    break
                event.write(frame)
                recorded_frames += 1

            eventCapture.release()
            event.release()

            # Signal for telegram bot
            with open(f"{eventFileName}.ready", "w") as f_ready:
                f_ready.write(eventFileName)
            print(f'[{datetime.now().strftime("%H:%M:%S")}] ✅ Событие записано с камеры "{cam['name']}" по пути : {eventFileName}')

        #=============================================================================#
        #------------------------------ OPEN TIMELAPSE STREAM --------------------------------#
        timelapseCapture = OpenStream()
        if timelapseCapture is None:
            return
        FolderCleaner(TIMELAPSE_FOLDER, 3)

        # Get configuraton timelapse stream
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        width = int(timelapseCapture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(timelapseCapture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Configurate timelapse stream
        timelapseFrameSkip = 5  
        timelapseFrameCount = 0
        timelapseSegmentDuration = cam.get("record_duration_minutes", 60) * 60
        timelapseRecordingStart = datetime.now()
        timelapseFileName = GetVideoSavePath(cam["name"], timelapseRecordingStart, folder=TIMELAPSE_FOLDER)

        # Start timelapse stream
        timelapse = cv2.VideoWriter(timelapseFileName, fourcc, 20, (width, height))
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Началась основаная запись камеры "{cam["name"]}" в: {timelapseFileName}')

        # For events
        detector = CameraMotionDetector(threshold = cam["threshold"], consecutiveFrames = cam["consecutiveFrames"], minWeight = cam["minWeight"])

        #=============================================================================#
        #------------------------------ TIMELAPSE RECORD --------------------------------#
        while True:
            # Lost signal
            ret, frame = timelapseCapture.read()
            if not ret:
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Камера "{cam['name']}" потеряля сигнал. Переподключение через 5 секунд...')
                timelapseCapture.release()
                time.sleep(5)
                break 

            if timelapseFrameCount % timelapseFrameSkip == 0:
                timelapse.write(frame)

            timelapseFrameCount  += 1
                
            # Create new timelapse
            elapsed = (datetime.now() - timelapseRecordingStart).total_seconds()
            if elapsed >= timelapseSegmentDuration:
                # Cleaning folder
                FolderCleaner(TIMELAPSE_FOLDER, 7)

                timelapse.release()

                prev = -1
                while True:
                    size = os.path.getsize(timelapseFileName)
                    if size == prev:
                        break
                    prev = size
                    time.sleep(0.5)

                threading.Thread(target=compressVideo, args=(timelapseFileName,), daemon=True).start()

                timelapseRecordingStart = datetime.now()
                timelapseFileName = GetVideoSavePath(cam["name"], timelapseRecordingStart, folder=TIMELAPSE_FOLDER)
                timelapse = cv2.VideoWriter(timelapseFileName, fourcc, 20, (width, height))
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Началась новая запись камеры "{cam["name"]}" в: {timelapseFileName}')

            # Detect motion in frame
            detector.SetRoi(cam.get("roi"))
            if detector.DetectMotionInFrame(frame):

                print(f'[{datetime.now().strftime("%H:%M:%S")}] Обнаружено движение на камере "{cam['name']}"')

                # Add frame in list of Detect people
                if not cam.get("peopleDetectStart", False):
                    detectionThread = threading.Thread(target=PeopleDetection, args=(detector, EventRecord, cam), daemon=True)
                    detectionThread.start()
                    cam["peopleDetectStart"] = True

                cam["frameQueue"].put(frame.copy())

#=============================================================================#
#------------------------------ START COMPRESS VIDEO --------------------------------#
def compressVideo(src, fps=20):
    compressedFileName = src.replace(".avi", ".mp4")
    print(f'[{datetime.now().strftime("%H:%M:%S")}] Начато сжатие: {compressedFileName}')

    with open("ffmpeg_errors.log", "a") as log:
        subprocess.run([
            "ffmpeg",
            "-y",
            "-fflags", "+genpts",
            "-i", src,
            "-vcodec", "libx264",
            "-crf", "23",
            "-r", str(fps),
            "-movflags", "+faststart",
            "-loglevel", "error",
            compressedFileName
        ], stdout=subprocess.DEVNULL, stderr=log)

    if os.path.exists(compressedFileName):
        os.remove(src)
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Сжатие завершено: {compressedFileName}')
    else:
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Ошибка: не удалось создать {compressedFileName}')

#=============================================================================#
#------------------------------ START RECORD CAMERAS --------------------------------#
def StartRecordingCameras(cameras):
    threads = []
    for cam in cameras:
        t = Thread(target=RecordCameraMotion, args=(cam,), daemon=True)
        t.start()
        threads.append(t)
    return threads