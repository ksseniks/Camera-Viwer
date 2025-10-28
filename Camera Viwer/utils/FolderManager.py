import os
import shutil
from datetime import datetime

#=============================================================================#
#------------------------------ FOLDER CLEANER --------------------------------#
def FolderCleaner(folderPath, counter):
    file = [f for f in os.listdir(folderPath) if os.path.exists(os.path.join(folderPath, f))]

    if not file:
        return

    file.sort(key=lambda f: os.path.getctime(os.path.join(folderPath, f)))

    if len(file) == counter:
        for item in file[:len(file) - counter]:
            item_path = os.path.join(folderPath, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f'[{datetime.now().strftime("%H:%M:%S")}] Удалена папка: {item_path}')
                elif os.path.isfile(item_path):
                    os.remove(item_path)
                    print(f'[{datetime.now().strftime("%H:%M:%S")}] Удален файл: {item_path}')
            except Exception as e:
                print(f'[{datetime.now().strftime("%H:%M:%S")}] Не удалось удалить {item_path}: {e}')
