import os
from ultralytics import YOLO
from datetime import datetime

#=============================================================================#
# ------------------------------ MAIN VARIABLES -------------------------------- #
MODEL_PATH = "yolov5mu.pt"
OUTPUT_MODEL = "yolov5mu_custom.pt"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(os.path.dirname(BASE_DIR), "data", "train")
POSITIVE_IMAGES_DIR = os.path.join(DATA_FOLDER, "images", "positive")
NEGATIVE_IMAGES_DIR = os.path.join(DATA_FOLDER, "images", "negative")
POSITIVE_LABELS_DIR = os.path.join(DATA_FOLDER, "labels", "positive")
NEGATIVE_LABELS_DIR = os.path.join(DATA_FOLDER, "labels", "negative")

EPOCHS = 100
BATCH_SIZE = 8
IMAGE_SIZE = 640

#=============================================================================#
# ------------------------------ PREPARE DATA YAML -------------------------------- #
def PrepareDataYaml():
    data_yaml = os.path.join(BASE_DIR, "data.yaml")

    pos_images = os.path.abspath(POSITIVE_IMAGES_DIR).replace("\\", "/")
    neg_images = os.path.abspath(NEGATIVE_IMAGES_DIR).replace("\\", "/")

    with open(data_yaml, "w") as f:
        f.write(f"""
            train:
            - {pos_images}
            - {neg_images}

            val:
            - {pos_images}
            - {neg_images}

            nc: 2
            names: ['negative', 'person']
        """)
    print(f"[INFO] data.yaml создан: {data_yaml}")
    return data_yaml

#=============================================================================#
# ------------------------------ TRAIN MODEL -------------------------------- #
def main():
    data_yaml = PrepareDataYaml()
    model = YOLO(MODEL_PATH)
    print(f"[INFO] Модель загружена: {MODEL_PATH}")

    model.train(
        data=data_yaml,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        patience=5,
        augment=True,
        verbose=True
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_model_name = f"yolov5mu_finetuned_{timestamp}.pt"
    model.save(new_model_name)
    os.replace(new_model_name, OUTPUT_MODEL)
    print(f"[INFO] Дообучение завершено. Новая модель: {OUTPUT_MODEL}")

if __name__ == "__main__":
    main()
