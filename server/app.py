from flask import Flask, render_template, Response, request, jsonify, redirect
import math
import cv2
import queue

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
# --------------------- STREAM VIEW --------------------------------------
@app.route('/video/<int:cam_id>')
def video(cam_id):

    def generate():
        while True:
            cameras = CONFIG.get_cameras()

            if cam_id >= len(cameras):
                break

            cam = cameras[cam_id]

            try:
                frame = cam["frameQueue"].get(timeout=1)
            except queue.Empty:
                continue

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' +
                buffer.tobytes() +
                b'\r\n'
            )

    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

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
