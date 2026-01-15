import os
import cv2
import numpy as np
from ultralytics import YOLO

# ------------------------------ MAIN VARIABLES -------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
MODEL_FOLDER = os.path.join(PROJECT_DIR, "models")
os.makedirs(MODEL_FOLDER, exist_ok=True)
# ============================================================================= #


class CameraMotionDetector:
    def __init__(
        self,
        threshold=0.02,
        minWeight=0.6,
        model_name="yolo8.pt",
        searchObjectList=None,
        roi=None,
        min_motion_frames=2,
        max_rois=3,
        min_motion_area = 500,
    ):
        self.prevFrame = None
        self.motionFrameCounter = 0
        self.threshold = threshold
        self.minWeight = minWeight
        self.searchObjectList = searchObjectList or []
        self.roi = roi or []
        self.min_motion_frames = min_motion_frames
        self.max_rois = max_rois
        self.min_motion_area = min_motion_area

        model_path = os.path.join(MODEL_FOLDER, model_name)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель не найдена: {model_path}")

        self.yolo = YOLO(model_path)

    # ========================================================================== #
    # ------------------------------ PREPARE FRAME ----------------------------- #
    def _preprocess(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (15, 15), 0)

    # ========================================================================== #
    # ------------------------------ APPLY ROI MASK ----------------------------- #
    def apply_roi_mask(self, frame):
        if not self.roi:
            return frame

        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        for r in self.roi:
            x, y, w, h = r["x"], r["y"], r["width"], r["height"]
            mask[y : y + h, x : x + w] = 255

        return cv2.bitwise_and(frame, frame, mask=mask)

    # ========================================================================== #
    # ------------------------------ DETECT MOTION ------------------------------ #
    def detect_motion_rois(self, frame):
        frame = self.apply_roi_mask(frame)
        gray = self._preprocess(frame)

        if self.prevFrame is None:
            self.prevFrame = gray
            return []

        diff = cv2.absdiff(self.prevFrame, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, np.ones((5, 5)))

        motion_pixels = cv2.countNonZero(thresh)
        roi_area = frame.shape[0] * frame.shape[1]

        self.prevFrame = gray

        if motion_pixels < roi_area * self.threshold:
            self.motionFrameCounter = 0
            return []

        self.motionFrameCounter += 1
        if self.motionFrameCounter < self.min_motion_frames:
            return []

        self.motionFrameCounter = 0

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        rois = []
        for cnt in contours:
            if cv2.contourArea(cnt) < self.min_motion_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if h < 160 or w < 160:
                continue

            pad = 20
            x = max(0, x - pad)
            y = max(0, y - pad)
            w = min(frame.shape[1] - x, w + pad * 2)
            h = min(frame.shape[0] - y, h + pad * 2)

            rois.append(frame[y : y + h, x : x + w])

        return rois[: self.max_rois]

    # ========================================================================== #
    # ------------------------------ YOLO DETECTION ----------------------------- #
    def detect_people(self, frame):
        motion_rois = self.detect_motion_rois(frame)

        if not motion_rois:
            return False

        for roi in motion_rois:
            results = self.yolo(roi, device="cpu", verbose=False)

            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    print(conf)

                    if ((not self.searchObjectList or cls_id in self.searchObjectList) and conf >= self.minWeight):
                        return True

        return False
