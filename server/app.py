from flask import Flask, render_template, Response, request, jsonify, redirect
import math
import cv2
import queue

import socket
import ipaddress
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed


app = Flask(__name__)
CONFIG = None

# =============================================================================
# ---------------------- RENDER INDEX ------------------------------------
@app.route('/')
def index():
    cameras = CONFIG.get_cameras()
    count = len(cameras)
    size = 2 if count <= 2 else int(math.ceil(math.sqrt(count)))
    return render_template('index.html', cameras=cameras, rows=size, cols=size)

# =============================================================================
# --------------------- RTSP SCANNER FUNCTIONS -------------------------------
# =============================================================================
RTSP_PATHS = [
    "h264/ch1/main/av_stream",
    "stream1",
    "stream2", 
    "Streaming/Channels/101",
    "Streaming/Channels/102",
    "live/ch0",
    "live/ch1",
    "onvif1",
    "cam/realmonitor?channel=1&subtype=0",
    "axis-media/media.amp",
    "videoMain",
    "videoSub"
]

def check_rtsp_device(ip, port=554):

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect((ip, port))
        sock.send(b"OPTIONS rtsp:// RTSP/1.0\r\nCSeq: 1\r\n\r\n")
        resp = sock.recv(1024).decode(errors='ignore')
        sock.close()
        if "200 OK" in resp or "401 Unauthorized" in resp:
            return True
    except:
        pass
    return False

def find_rtsp_streams(ip, login="", password="", port=554):
    """Находит все доступные RTSP потоки на камере"""
    working_streams = []
    
    for path in RTSP_PATHS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((ip, port))
            
            if login and password:
                auth = base64.b64encode(f"{login}:{password}".encode()).decode()
                url = f"rtsp://{ip}:{port}/{path}"
                request = f"DESCRIBE {url} RTSP/1.0\r\nCSeq: 1\r\nAuthorization: Basic {auth}\r\n\r\n"
            else:
                url = f"rtsp://{ip}:{port}/{path}"
                request = f"DESCRIBE {url} RTSP/1.0\r\nCSeq: 1\r\n\r\n"
            
            sock.send(request.encode())
            resp = sock.recv(2048).decode(errors='ignore')
            sock.close()
            
            if "200 OK" in resp:
                working_streams.append({
                    'path': path,
                    'status': 'open',
                    'url': f"rtsp://{login}:{password}@{ip}:{port}/{path}" if login and password else f"rtsp://{ip}:{port}/{path}"
                })
            elif "401 Unauthorized" in resp:
                working_streams.append({
                    'path': path,
                    'status': 'auth',
                    'url': None
                })
        except:
            pass
    
    return working_streams

# =============================================================================
# --------------------- API SCAN NETWORK --------------------------------------
@app.route('/api/scan_network', methods=['POST'])
def api_scan_network():
    data = request.get_json()
    subnet = data.get('subnet', '192.168.0.0/24')
    
    try:
        network = ipaddress.ip_network(subnet, strict=False)
        cameras = []
        
        def check_ip(ip):
            ip_str = str(ip)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect((ip_str, 554))
                sock.send(b"OPTIONS rtsp:// RTSP/1.0\r\nCSeq: 1\r\n\r\n")
                resp = sock.recv(1024).decode(errors='ignore')
                sock.close()
                
                if "200 OK" in resp:
                    return {'ip': ip_str, 'has_auth': False, 'status': 'open'}
                elif "401 Unauthorized" in resp:
                    return {'ip': ip_str, 'has_auth': True, 'status': 'protected'}
            except:
                pass
            return None
        
        with ThreadPoolExecutor(max_workers=200) as executor:
            futures = {executor.submit(check_ip, ip): ip for ip in network.hosts()}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    cameras.append(result)
        
        return jsonify(cameras)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# --------------------- API SCAN STREAMS --------------------------------------
@app.route('/api/scan_streams', methods=['POST'])
def api_scan_streams():
    data = request.get_json()
    ip = data.get('ip')
    login = data.get('login', 'admin')
    password = data.get('password', '')
    
    if not ip:
        return jsonify({'error': 'IP адрес не указан'}), 400
    
    try:
        streams = find_rtsp_streams(ip, login, password)
        return jsonify(streams)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# --------------------- API TEST CONNECTION -----------------------------------
@app.route('/api/test_connection', methods=['POST'])
def api_test_connection():
    data = request.get_json()
    ip = data.get('ip')
    login = data.get('login', 'admin')
    password = data.get('password', '')
    
    if not ip:
        return jsonify({'success': False, 'error': 'IP адрес не указан'}), 400
    
    try:
        streams = find_rtsp_streams(ip, login, password)
        open_streams = [s for s in streams if s['status'] == 'open']
        
        if open_streams:
            return jsonify({
                'success': True,
                'streams_count': len(open_streams),
                'streams': [s['path'] for s in open_streams],
                'first_url': open_streams[0]['url'] if open_streams else None
            })
        elif streams:
            return jsonify({
                'success': False,
                'error': 'Найдены потоки, но требуется авторизация. Проверьте логин/пароль.',
                'streams_count': len(streams)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Не найдено ни одного RTSP потока. Проверьте IP и порт.'
            })
    
    except socket.timeout:
        return jsonify({'success': False, 'error': 'Таймаут подключения. Камера не отвечает.'})
    except ConnectionRefusedError:
        return jsonify({'success': False, 'error': 'Подключение отклонено. Порт 554 закрыт.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# =============================================================================
# --------------------- STREAM VIEW --------------------------------------
@app.route('/video/<int:cam_id>')
def video(cam_id):
    def generate():
        import time
        last_send = 0
        SEND_INTERVAL = 0.1  # 10 FPS
        
        while True:
            cameras = CONFIG.get_cameras()
            
            if cam_id >= len(cameras):
                break
            
            now = time.time()
            if now - last_send < SEND_INTERVAL:
                time.sleep(0.001)
                continue
            
            cam = cameras[cam_id]
            frame = None
            
            try:
                while True:
                    frame = cam["frameQueue"].get_nowait()
            except queue.Empty:
                pass
            
            if frame is None:
                try:
                    frame = cam["frameQueue"].get(timeout=0.01)
                except queue.Empty:
                    continue
            
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if not ret:
                continue
            
            last_send = now
            
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
# =============================================================================
# --------------------- CAMERA SETTINGS ----------------------------------
@app.route("/settings")
def settings():
    settings = CONFIG.get_settings()
    return render_template("settings.html", settings=settings)


# =============================================================================
# --------------------- CAMERA SETTINGS ----------------------------------
@app.route("/camera/<int:cam_id>")
def camera_settings(cam_id):
    cameras = CONFIG.get_cameras()
    if cam_id >= len(cameras):
        return "Camera not found", 404
    return render_template("camera_settings.html", camera=cameras[cam_id], cam_id=cam_id)


# =============================================================================
# --------------------- CAMERA ADD ----------------------------------
@app.route("/camera/add", methods=["GET", "POST"])
def add_camera():
    if request.method == "POST":
        cam = {
            "name": request.form.get("name", ""),
            "stream_view": request.form.get("stream_view"),
            "stream_record": request.form.get("stream_record"),
            "record_duration_minutes": int(request.form.get("record_duration_minutes", 30)),
            "event_duration_seconds": int(request.form.get("event_duration_seconds", 5)),
            "searchObjectList": request.form.get("searchObjectList", "").split(),
            "threshold": float(request.form.get("threshold", 0.25)),
            "min_motion_area": int(request.form.get("min_motion_area", 2500)),
            "minWeight": float(request.form.get("minWeight", 0.5)), 
            "rois": [],
        }

        CONFIG.cameras.append(cam)
        CONFIG.save()

        from main import start_camera
        start_camera(cam, CONFIG)

        return redirect("/")

    return render_template("add_camera.html")

# =============================================================================
# --------------------- SAVE NEW CAMERA -----------------------------------------
@app.route("/saveNewCamera", methods=["POST"])
def saveNewCamera():
    cameras = CONFIG.get_cameras()

    if cameras:
        cam_id = max(cameras.keys()) + 1
    else:
        cam_id = 0

    cameras[cam_id] = {}

    cam = cameras[cam_id]

    default_cam = {
        "name": "",
        "stream_view": "",
        "stream_record": "",
        "record_duration_minutes": 30,
        "event_duration_seconds": 5,
        "searchObjectList": [],
        "threshold": 0.25,
        "min_motion_area": 2500,
        "minWeight": 0.5,
        "rois": [],
    }

    cam.update(default_cam)

    for key in cam.keys():
        value = request.form.get(key)
        if value is None:
            continue

        if key == "searchObjectList":
            cam[key] = value.split()
        elif key in ("threshold", "minWeight"):
            cam[key] = float(value)
        elif key in ("record_duration_minutes", "event_duration_seconds", "min_motion_area"):
            cam[key] = int(value)
        else:
            cam[key] = value

    CONFIG.save()
    return redirect("/")


# =============================================================================
# --------------------- SNAPSHOT -----------------------------------------
@app.route("/snapshot/<int:cam_id>")
def snapshot(cam_id):
    cameras = CONFIG.get_cameras()
    if cam_id >= len(cameras):
        return "Camera not found", 404

    cam = cameras[cam_id]

    try:
        frame = cam["frameQueue"].get(timeout=1)
    except queue.Empty:
        return "No frame", 404

    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return "Encode error", 500

    return Response(buffer.tobytes(), mimetype='image/jpeg')


# =============================================================================
# --------------------- SAVE CAMERA SETTINGS -------------------------------
@app.route("/saveCameraSettings/<int:cam_id>", methods=['POST'])
def saveCameraSettings(cam_id):
    cameras = CONFIG.get_cameras()
    if cam_id >= len(cameras):
        return "Camera not found", 404

    cam = cameras[cam_id]

    for key in cam.keys():
        if key == "frameQueue":
            continue

        value = request.form.get(key)
        if value is None:
            continue

        if key == "searchObjectList":
            cam[key] = [obj.strip() for obj in value.split() if obj.strip()]
        elif key == "rois":
            if value.strip():
                cam[key] = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
            else:
                cam[key] = []
        elif key in ("threshold", "minWeight"):
            try:
                cam[key] = float(value)
            except ValueError:
                cam[key] = 0.0
        elif key in ("record_duration_minutes", "event_duration_seconds", "min_motion_area"):
            try:
                cam[key] = int(value)
            except ValueError:
                cam[key] = 0
        else:
            cam[key] = value

    CONFIG.save()

    return redirect('/')


def IndicesToCoordinates(indices, grid_cols=12, grid_rows=7, image_width=640, image_height=480):
    if not indices:
        return []
    
    cell_width = image_width / grid_cols
    cell_height = image_height / grid_rows
    
    coordinates = []
    for index in indices:
        row = index // grid_cols
        col = index % grid_cols
        
        coordinates.append({
            'x': int(col * cell_width),
            'y': int(row * cell_height),
            'width': int(cell_width),
            'height': int(cell_height)
        })
    
    return coordinates


# =============================================================================
# --------------------- SAVE SETTINGS -------------------------------
@app.route("/saveSettings", methods=["POST"])
def saveSettings():
    settings = CONFIG.get_settings()

    if "modelName" in request.form:
        settings["modelName"] = request.form.get("modelName")

    if "countEventVideo" in request.form:
        settings["countEventVideo"] = int(request.form.get("countEventVideo"))

    if "countRecordVideo" in request.form:
        settings["countRecordVideo"] = int(request.form.get("countRecordVideo"))

    CONFIG.save()
    return redirect("/")


# =============================================================================
# ---------------------CAMERA DELETE -------------------------------------
@app.route("/camera/delete/<int:cam_id>", methods=["POST"])
def delete_camera(cam_id):
    cameras = CONFIG.get_cameras()
    if cam_id < 0 or cam_id >= len(cameras):
        return "Camera not found", 404

    cam = cameras[cam_id]
    cam["stop"] = True
    cameras.pop(cam_id)

    CONFIG.save()
    return redirect("/")


# =============================================================================
# --------------------- RUN FROM MAIN -------------------------------------
def run_app(config):
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    global CONFIG
    CONFIG = config

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
