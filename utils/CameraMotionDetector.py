import os
import cv2
import numpy as np
from ultralytics import YOLO
from main import writeLog

# ------------------------------ MAIN VARIABLES -------------------------------- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
MODEL_FOLDER = os.path.join(PROJECT_DIR, "models")
os.makedirs(MODEL_FOLDER, exist_ok=True)
# ============================================================================= #
class CameraMotionDetector:
    def __init__(self, model_name="yolo8.pt"):
        self.prev_gray = None
        self.motion_counter = 0

        model_path = os.path.join(MODEL_FOLDER, model_name)
        if not os.path.exists(model_path):
            writeLog(f"Модель не найдена")

        self.yolo = YOLO(model_path)

    # ========================================================================== #
    # ------------------------------ APPLY ROI MASK ----------------------------- #
    def apply_roi_mask(self, frame, rois):
        if not rois:
            return frame
        
        height, width = frame.shape[:2]
        
        grid_rows = 7
        grid_cols = 12

        cell_width = width // grid_cols
        cell_height = height // grid_rows
        
        masked_frame = np.zeros_like(frame)
        
        for cell_id in rois:
            row = cell_id // grid_cols
            col = cell_id % grid_cols
            
            x = col * cell_width
            y = row * cell_height
            
            x_end = (col + 1) * cell_width if col < grid_cols - 1 else width
            y_end = (row + 1) * cell_height if row < grid_rows - 1 else height
            
            w = x_end - x
            h = y_end - y
            
            masked_frame[y:y + h, x:x + w] = frame[y:y + h, x:x + w]
        
        return masked_frame
    # ========================================================================== #
    # ------------------------------ DETECT MOTION ------------------------------ #
    def detectMotion(self, frame, cam):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self.prev_gray is None:
            self.prev_gray = gray
            return False, 0

        diff = cv2.absdiff(self.prev_gray, gray)

        _, thresh = cv2.threshold(diff, cam["threshold"], 255, cv2.THRESH_BINARY)

        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        self.prev_gray = gray

        motion_area = 0
        for cnt in contours:
            motion_area += cv2.contourArea(cnt)
            return motion_area > cam["min_motion_area"], motion_area

        return False, 0
    # ========================================================================== #
    # ------------------------------ YOLO DETECTION ----------------------------- #
    def detectPeople(self, frame, cam):
        image = self.apply_roi_mask(frame, cam["rois"])
        detection, motion_area = self.detectMotion(image, cam)

        # if self.motion_counter <= 3 and detection:
        #     self.motion_counter += 1
        #     return False
        # elif not detection:
        #     self.motion_counter = 0
        #     return False

        if not detection:
            return False

        self.motion_counter = 0
        results = self.yolo(image, device="cpu", verbose=False)

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                print(conf)
                print(motion_area)

                if ((not cam["searchObjectList"] or cls_id in cam["searchObjectList"]) and conf >= cam["minWeight"]):
                    return True

        return False
