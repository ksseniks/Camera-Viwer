import os
import cv2
import uuid
import time
from datetime import datetime
from ultralytics import YOLO

#------------------------------ MAIN VARIABLES --------------------------------#
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FOLDER = os.path.join(os.path.dirname(BASE_DIR), "models")
CUSTOM_MODEL = os.path.join(MODEL_FOLDER, "yolov5mu_custom.pt")

#=============================================================================#
#------------------------------ INITIALIZE --------------------------------#
class CameraMotionDetector:
    def __init__(self, threshold = 50000, blurSize = (15, 15), pixelThreshold = 20, consecutiveFrames = 15, minWeight = 0.6):
        self.roi = None                             # Border for search motion  
        self.lastSaveTime = 0
        self.prevFrame = None
        self.blurSize = blurSize                    # Size of the Gaussian blur kernel to reduce noise
        self.minWeight = minWeight                  # System’s minimum confidence level
        self.threshold = threshold                  # Minimum number of changed pixels to consider motion detected           
        self.motionFrameCounter = 0                 # Counter for consecutive frames with motion detected
        self.pixelThreshold = pixelThreshold        # Pixel intensity difference threshold to detect change
        self.consecutiveFrames = consecutiveFrames  # Number of consecutive frames required to confirm motion

        os.makedirs(MODEL_FOLDER, exist_ok=True)
        if os.path.exists(CUSTOM_MODEL):
            self.yolo = YOLO(CUSTOM_MODEL)
        else:
            self.yolo = YOLO(os.path.join(MODEL_FOLDER, "yolov5mu.pt"))

    #=============================================================================#
    #------------------------------ DETECT PEOPLE IN FRAME --------------------------------#
    def DetectPeopleInFrame(self, frame):
        if self.roi:
            x, y = self.roi.get("x", 0), self.roi.get("y", 0)
            w, h = self.roi.get("width", frame.shape[1]), self.roi.get("height", frame.shape[0])

            x = max(0, min(x, frame.shape[1] - 1))
            y = max(0, min(y, frame.shape[0] - 1))
            w = max(1, min(w, frame.shape[1] - x))
            h = max(1, min(h, frame.shape[0] - y))

            frame = frame[y:y + h, x:x + w]

        results = self.yolo(frame)

        for r in results:
            for box in r.boxes:
                cls_id = 0
                conf = float(box.conf[0])

                # for training model
                current_time = time.time()
                if current_time - self.lastSaveTime >= 5:
                    
                    self.lastSaveTime = current_time
                    folder_path = "recordings/unverified"
                    os.makedirs(folder_path, exist_ok=True)

                    x1, y1, x2, y2 = box.xyxy[0]
                    bbox = (float(x1), float(y1), float(x2 - x1), float(y2 - y1))  # x, y, w, h

                    filename = os.path.join(
                        folder_path,
                        f"frame_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
                    )
                    cv2.imwrite(filename, frame)

                    txt_path = os.path.splitext(filename)[0] + ".txt"
                    iw, ih = frame.shape[1], frame.shape[0]
                    x_center = (bbox[0] + bbox[2]/2) / iw
                    y_center = (bbox[1] + bbox[3]/2) / ih
                    w_n = bbox[2] / iw
                    h_n = bbox[3] / ih

                    with open(txt_path, "w") as f:
                        f.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {w_n:.6f} {h_n:.6f}\n")
                # end training model

                # cls_id = 0 - Person
                if cls_id == 0 and conf >= self.minWeight:
                    return True

        return False

    #=============================================================================#
    #------------------------------ PRE RENDER FRAME --------------------------------#
    def PreRenderFrame(self, frame):
        grayFrame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        grayFrame = cv2.GaussianBlur(grayFrame, self.blurSize, 0)
        return grayFrame

    #=============================================================================#
    #------------------------------ DETECT MOTION IN FRAME --------------------------------#
    def DetectMotionInFrame(self, frame):
        # Roi is valid
        if self.roi:
            x, y = self.roi.get("x", 0), self.roi.get("y", 0)
            w, h = self.roi.get("width", frame.shape[1]), self.roi.get("height", frame.shape[0])

            x = max(0, min(x, frame.shape[1] - 1))
            y = max(0, min(y, frame.shape[0] - 1))
            w = max(1, min(w, frame.shape[1] - x))
            h = max(1, min(h, frame.shape[0] - y))

            frame = frame[y:y+h, x:x+w]

        # Getting new frame
        newFrame = self.PreRenderFrame(frame)
        if self.prevFrame is None or self.prevFrame.shape != newFrame.shape:
            self.prevFrame = newFrame
            return False

        # Comparison of two frames
        diff = cv2.absdiff(self.prevFrame, newFrame)
        _, thresh = cv2.threshold(diff, self.pixelThreshold, 255, cv2.THRESH_BINARY)
        motion_score = cv2.countNonZero(thresh)
        self.prevFrame = newFrame

        if motion_score > self.threshold:
            self.motionFrameCounter += 1
        else:
            self.motionFrameCounter = 0 

        if self.motionFrameCounter >= self.consecutiveFrames:
            self.motionFrameCounter = 0 
            return True

        return False

    #=============================================================================#
    #------------------------------ SET ROI --------------------------------#
    def SetRoi(self, roi):
        self.roi = roi