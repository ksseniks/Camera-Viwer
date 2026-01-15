import json
import os
import threading
import queue

class CameraConfig:
    _instance = None
    _lock = threading.Lock()

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CAMERA_CONFIG_FILE = os.path.join(BASE_DIR, "cameras.json")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraConfig, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.cameras = []
        self.settings = {}

    def load(self):
        with self._lock:
            if not os.path.exists(self.CAMERA_CONFIG_FILE):
                raise FileNotFoundError(
                    f"Конфигурационный файл {self.CAMERA_CONFIG_FILE} не найден"
                )

            with open(self.CAMERA_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            old_cameras = {cam["name"]: cam for cam in self.cameras}

            self.settings = {
                "modelName": data.get("modelName", "yolo8.pt"),
                "min_motion_frames": data.get("min_motion_frames", 3),
                "max_rois": data.get("max_rois", 3),
                "min_motion_area": data.get("min_motion_area",  500),
            }

            self.cameras.clear()

            for cam in data.get("cameras", []):
                name = cam["name"]

                if name in old_cameras:
                    frame_queue = old_cameras[name]["frameQueue"]
                else:
                    frame_queue = queue.Queue(maxsize=5)

                self.cameras.append({
                    "name": name,
                    "stream_view": cam.get("stream_view", cam.get("stream_record")),
                    "stream_record": cam["stream_record"],
                    "record_duration_minutes": cam.get("record_duration_minutes", 30),
                    "event_duration_seconds": cam.get("event_duration_seconds", 5),
                    "searchObjectList": cam.get("searchObjectList", []),
                    "threshold": cam.get("threshold", 0.01),
                    "minWeight": cam.get("minWeight", 0.3),
                    "roi": cam.get("roi"),
                    "frameQueue": frame_queue
                })


    def save(self):
        with self._lock:
            data = {
                "modelName": self.settings.get("modelName"),
                "min_motion_frames": self.settings.get("min_motion_frames"),
                "max_rois": self.settings.get("max_rois"),
                "min_motion_area": self.settings.get("min_motion_area"),
                "cameras": []
            }

            for cam in self.cameras:
                data["cameras"].append({
                    "name": cam["name"],
                    "stream_view": cam.get("stream_view"),
                    "stream_record": cam["stream_record"],
                    "record_duration_minutes": cam.get("record_duration_minutes"),
                    "event_duration_seconds": cam.get("event_duration_seconds"),
                    "searchObjectList": cam.get("searchObjectList"),
                    "threshold": cam.get("threshold"),
                    "minWeight": cam.get("minWeight"),
                    "roi": cam.get("roi"),
                })

            with open(self.CAMERA_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

    def get_cameras(self):
        with self._lock:
            return self.cameras

    def get_settings(self):
        with self._lock:
            return self.settings
