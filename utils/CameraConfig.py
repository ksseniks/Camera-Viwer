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

            self.settings = {
                "modelName": data.get("modelName", "yolo8.pt"),
                "countEventVideo": data.get("countEventVideo", 6),
                "countRecordVideo": data.get("countRecordVideo", 30),
            }

            self.cameras.clear()

            for cam in data.get("cameras", []):
                name = cam["name"]
                frame_queue = queue.Queue(maxsize=2)
                event_queue = queue.Queue()

                self.cameras.append({
                    "name": name,
                    "stream_view": cam.get("stream_view", cam.get("stream_record")),
                    "stream_record": cam["stream_record"],
                    "record_duration_minutes": cam.get("record_duration_minutes", 30),
                    "event_duration_seconds": cam.get("event_duration_seconds", 5),
                    "searchObjectList": cam.get("searchObjectList", []),
                    "threshold": cam.get("threshold", 0.01),
                    "min_motion_area": cam.get("min_motion_area",  5000),
                    "minWeight": cam.get("minWeight", 0.3),
                    "rois": cam.get("rois", []),
                    "frameQueue": frame_queue,
                    "eventQueue": event_queue,
                    "fps": 60
                })


    def save(self):
        with self._lock:
            data = {
                "modelName": self.settings.get("modelName"),
                "countEventVideo": self.settings.get("countEventVideo", 6),
                "countRecordVideo": self.settings.get("countRecordVideo", 30),
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
                    "min_motion_area": cam.get("min_motion_area"),
                    "minWeight": cam.get("minWeight"),
                    "rois": cam.get("rois"),
                })

            with open(self.CAMERA_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

    def get_cameras(self):
        with self._lock:
            return self.cameras

    def get_settings(self):
        with self._lock:
            return self.settings
