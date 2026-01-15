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
# --------------------- SET ROI ------------------------------------------
@app.route('/setroi/<camera_name>', methods=['POST'])
def setroi(camera_name):
    data = request.json
    if not data:
        return jsonify({"error": "Нет данных"}), 400

    roi = {
        "x": int(data['x']),
        "y": int(data['y']),
        "width": int(data['width']),
        "height": int(data['height'])
    }

    cameras = CONFIG.get_cameras()
    for cam in cameras:
        if cam["name"] == camera_name:
            cam["roi"] = roi
            CONFIG.save()
            return jsonify({"message": "ROI обновлён", "roi": roi})

    return jsonify({"error": "Камера не найдена"}), 404


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
            "minWeight": float(request.form.get("minWeight", 0.5)), 
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
        "minWeight": 0.5
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
        elif key in ("record_duration_minutes", "event_duration_seconds"):
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
            cam[key] = value.split()
        elif key in ("threshold", "minWeight"):
            cam[key] = float(value)
        elif key in ("record_duration_minutes", "event_duration_seconds"):
            cam[key] = int(value)
        else:
            cam[key] = value

    # --------------------- SAVE ROI -------------------------------
    roi_x = request.form.getlist("roi_x")
    roi_y = request.form.getlist("roi_y")
    roi_width = request.form.getlist("roi_width")
    roi_height = request.form.getlist("roi_height")

    rois = []
    for x, y, w, h in zip(roi_x, roi_y, roi_width, roi_height):
        try:
            r = {
                "x": int(float(x)),
                "y": int(float(y)),
                "width": int(float(w)),
                "height": int(float(h))
            }
            rois.append(r)
        except ValueError:
            continue

    cam["roi"] = rois

    if "detector" in cam and cam["detector"] is not None:
        cam["detector"].setRoi(rois) 

    CONFIG.save()

    return redirect('/')


# =============================================================================
# --------------------- SAVE SETTINGS -------------------------------
@app.route("/saveSettings", methods=["POST"])
def saveSettings():
    settings = CONFIG.get_settings()

    if "modelName" in request.form:
        settings["modelName"] = request.form.get("modelName")

    if "min_motion_frames" in request.form:
        settings["min_motion_frames"] = int(request.form.get("min_motion_frames"))

    if "max_rois" in request.form:
        settings["max_rois"] = int(request.form.get("max_rois"))

    if "min_motion_area" in request.form:
        settings["min_motion_area"] = int(request.form.get("min_motion_area"))

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
