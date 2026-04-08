import os
import vk_api
import aiohttp
import random
# ========================================================================== #
# ------------------------------ MAIN VARIABLES ----------------------------- #
TOKEN = "YOU TOKEN"
CHAT_ID = 68
# ========================================================================== #
# ------------------------------ VK SETUP ----------------------------------- #
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
# ========================================================================== #
# ------------------------------ VIDEO SENDER ------------------------------- #
async def SendVideo(video_path: str):
    if not os.path.exists(video_path):
        print(f"Файл не найден: {video_path}")
        return False
    try:
        upload_server = vk.video.save(
            name=os.path.basename(video_path),
        )
        
        with open(video_path, 'rb') as video_file:
            data = aiohttp.FormData()
            data.add_field('video_file', 
                         video_file.read(), 
                         filename=os.path.basename(video_path),
                         content_type='video/mp4')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(upload_server['upload_url'], data=data) as response:
                    result = await response.json()
        
        attachment = f"video{result['owner_id']}_{result['video_id']}"
        
        vk.messages.send(
            peer_id=2000000000 + CHAT_ID,
            attachment=attachment,
            random_id=random.randint(1, 2**31)
        )
        
        return True
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return False
