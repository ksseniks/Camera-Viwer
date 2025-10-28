import os
import sys
import cv2
import math
import queue
import threading
from datetime import datetime
from utils.VideoRecorder import StartRecordingCameras
from bots.CameraAlertBot import main as RunCameraAlert
from bots.ModelTrainerBot import main as RunTrainerBot
from flask import Flask, render_template, Response, request, jsonify

#=========================================================================#
#------------------------ BASE DIR & FLASK --------------------------------#
BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

CAMERAS = [
    {
        "name": "Береза",
        "stream_view": "rtsp://pb.kvant:pb.kvant@192.168.0.107:554/stream2",
        "stream_record": "rtsp://pb.kvant:pb.kvant@192.168.0.107:554/stream1",
        "record_duration_minutes": 60,
        "event_duration_seconds": 5,
        "consecutiveFrames": 60, 
        "threshold": 1000,
        "minWeight": 0.5,
        "frameQueue": queue.Queue(),
    },
    {
        "name": "Окно",
        "stream_view": "rtsp://pb.kvant:pb.kvant@192.168.0.144:554/stream2",
        "stream_record": "rtsp://pb.kvant:pb.kvant@192.168.0.144:554/stream1",
        "record_duration_minutes": 60,
        "event_duration_seconds": 5,
        "consecutiveFrames": 60, 
        "threshold": 1000,
        "minWeight": 0.1,
        "frameQueue": queue.Queue(),
    }
    
]

#=============================================================================#
#------------------------------ RENDER INDEX --------------------------------#
@app.route('/')
def index():
    countCameras = len(CAMERAS)
    if countCameras <= 2:
        size = 2
    else:
        size = int(math.ceil(math.sqrt(countCameras)))

    return render_template('index.html', cameras=CAMERAS, rows=size, cols=size)

#=============================================================================#
#------------------------------ GET STREAM --------------------------------#
@app.route('/video/<int:cam_id>')
def video(cam_id):
    rtsp_url = CAMERAS[cam_id]["stream_view"]
    capture = cv2.VideoCapture(rtsp_url)

    if not capture .isOpened():
        print(f"[{datetime.now().strftime("%H:%M:%S")}] Не удалось открыть поток: {rtsp_url}")
        return "Поток не доступен", 500

    def generate():
        while True:
            success, frame = capture.read()
            if not success:
                break
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


#=============================================================================#
#------------------------------ SET ROI --------------------------------#
@app.route('/setroi/<camera_name>', methods=['POST'])
def setroi(camera_name):
    print(camera_name)
    cam_id = next((i for i, cam in enumerate(CAMERAS) if cam["name"] == camera_name), None)
    if cam_id is None:
        return jsonify({"error": "Камера не найдена"}), 404

    data = request.json
    if not data:
        return jsonify({"error": "Нет данных"}), 400

    required_fields = ['x', 'y', 'width', 'height']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Отсутствуют поля ROI"}), 400

    try:
        roi = {
            "x": int(data['x']),
            "y": int(data['y']),
            "width": int(data['width']),
            "height": int(data['height'])
        }
    except ValueError:
        return jsonify({"error": "Неверные типы данных"}), 400

    CAMERAS[cam_id]['roi'] = roi
    print(f"[{datetime.now().strftime("%H:%M:%S")}] Обновлен ROI для камеры {camera_name}: {roi}")

    return jsonify({"message": "ROI обновлен", "roi": roi})


#=============================================================================#
#------------------------------ MAIN --------------------------------#
if __name__ == "__main__":
    camera_thread = threading.Thread(target=StartRecordingCameras, args=(CAMERAS,), daemon=True)
    camera_thread.start()

    cameraAlert_thread = threading.Thread(target=RunCameraAlert, args=(CAMERAS,), daemon=True)
    cameraAlert_thread.start()

    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()

    RunTrainerBot()
