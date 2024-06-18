"""
This script is used to upload reels to Instagram and download reels from Instagram.
The script uses the instagrapi library to interact with Instagram.
The script sends a message to a telegram chat when the reel is uploaded or downloaded.
"""
import os
import sys
import time
import json
import random
import logging
import argparse
import requests
import instagrapi
from instagrapi.types import *

def send_telegram_message(message: str):
    global bot_token, user_id
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {
        'chat_id': user_id,
        'text': message
    }
    requests.post(url, data=data)

def shorten_user(user: User):
    return UserShort(username=user.username, pk=user.pk, full_name=user.full_name, is_private=user.is_private, profile_pic_url=user.profile_pic_url, profile_pic_url_hd=user.profile_pic_url_hd)

def add_account(username :str, password :str, verification_code :str, directory: str):
    # 0-3-4-5
    user_agents = [
        #"Mozilla/5.0 (Linux; Android 12; T431D Build/SP1A.210812.016;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36 Instagram 312.1.0.34.111 Android (31/12; 240dpi; 480x888; TCL; T431D; Rio; mt6761; it_IT; 548323740)",
        "Mozilla/5.0 (Linux; Android 12; PEPM00 Build/OPPOPEPM00;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/99.0.4844.88 Safari/537.36 Instagram 312.1.0.34.111 Android (31/12; 300dpi; 1440x2200; OPPO; PEPM00; OP4ECB; qcom; ar_SA; 548323749)",
        "Mozilla/5.0 (Linux; Android 13; OT5 Build/TP1A.220624.014;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/121.0.6167.164 Safari/537.36 Instagram 317.0.0.34.109 Android (33/13; 254dpi; 1200x1962; OUKITEL; OT5; OT5; mt6789; de_DE; 563459863)",
        #"Mozilla/5.0 (Linux; Android 12; T431D Build/SP1A.210812.016;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/118.0.0.0 Mobile Safari/537.36 Instagram 312.1.0.34.111 Android (31/12; 240dpi; 480x888; TCL; T431D; Rio; mt6761; it_IT; 548323740)",
        #"Mozilla/5.0 (Linux; Android 12; A202SH Build/SC263;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36 Instagram 312.1.0.34.111 Android (31/12; 530dpi; 1260x2502; SHARP/SG; A202SH; Mineva; qcom; ja_JP; 548323757)",
        #"Mozilla/5.0 (Linux; Android 12; T431D Build/SP1A.210812.016;) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36 Instagram 309.0.0.40.113 Android (31/12; 240dpi; 480x888; TCL; T431D; Rio; mt6761; it_IT; 536988415)",
    ]
    user_agent = random.choice(user_agents)
    cl = instagrapi.Client(
        settings= {
            #"user_agent": user_agent,
            "country": "TR",
            "locale": "tr_TR",
            "country_code": 90,
            "timezone_offset": 10800
        },
        logger= logging.getLogger("tutun"),
        delay_range= [3, 7]
    )
    cl.login(username=username, password=password, verification_code=verification_code)
    
    try:
        cl.get_timeline_feed()
    except:
        raise Exception('Giriş yapılamadı. Lütfen tekrar deneyin.')

    # dump the settings to the folder
    cl.dump_settings(os.path.join(directory, "settings.json"))

    # dump the username and password to the folder
    with open(os.path.join(directory, "credentials.json"), "w", encoding='utf-8') as f:
        json.dump({"username": username, "password": password}, f, ensure_ascii=False)
        
    send_telegram_message(f'{username} kullanıcısı eklendi.')

def usual_login(settings_path: str, username: str, password: str):
    cl = instagrapi.Client(logger= logging.getLogger("SM-A035M"), delay_range= [3, 7], request_timeout=5)
    session = cl.load_settings(settings_path)
    try:
        cl.login_by_sessionid(sessionid=session["authorization_data"]["sessionid"])
        cl.delay_range = [1, 3]
        try:
            cl.get_timeline_feed()
            return cl
        except:
            try:
                cl.login(username=username, password=password, relogin=True)
                cl.get_timeline_feed()
                return cl
            except Exception as e:
                raise Exception('Giriş yapılamadı. Lütfen tekrar deneyin.')
    except:
        try:
            cl.login(username=username, password=password, relogin=True)
            cl.get_timeline_feed()
            return cl
        except Exception as e:
            raise Exception('Giriş yapılamadı. Lütfen tekrar deneyin.')

def upload_reel(username: str, video: str, caption: str, directory: str):

    password_json = open(os.path.join(directory, 'credentials.json'), 'r', encoding='utf-8')
    password = json.load(password_json)['password']

    setting_file = os.path.join(directory, 'settings.json')
    cl = usual_login(setting_file, username, password)

    caption_str = ''
    if(caption != None):
        caption_str = open(caption, 'r', encoding='utf-8').read()

    send_telegram_message('Reel yükleniyor...')
    try:
        cl.clip_upload(video, caption=caption_str, extra_data={'share_to_facebook': 1})

    except Exception as e:
        cl.dump_settings(setting_file)
        raise Exception('Reel yüklenemedi. Lütfen tekrar deneyin.')
    # in the future; if you want to add thumbnail feature
    #cl.clip_upload(video, caption=caption_str, thumbnail="thumbnail.jpg")
    cl.dump_settings(setting_file)
    os.remove(video)
    try:
        os.remove(video + '.jpg')
    except:
        pass
    send_telegram_message('Reel yüklendi.')
    
def download_reel(username: str, download_mode: str, download_hashtag: str, download_user: str, directory: str):
    # limitation is hardcoded for now TODO: make it dynamic in the future
    limitation = 10
    credentials_path = os.path.join(directory, 'credentials.json')
    
    with open(credentials_path, 'r', encoding='utf-8') as f:
        credentials = json.load(f)
        
    password = credentials['password']
    setting_file = os.path.join(directory, 'settings.json')

    cl = usual_login(setting_file, username, password)
    
    if download_mode == 'link':
        media_pk = cl.media_pk_from_url(download_hashtag)
        media_id = cl.media_id(media_pk)
        downlaoded_clip = cl.clip_download(media_id, folder=os.path.join(directory, 'content'))
        
        # send clip to the user
        url = f'https://api.telegram.org/bot{bot_token}/sendVideo'
        with open(os.path.join(directory, 'content', f'{downlaoded_clip}'), 'rb') as f_video:
            data = {
                'chat_id': user_id,
                'height': '1920',
                'width': '1080',
                'supports_streaming': True
            }
            files = {
                'video': f_video
            }
            response = requests.post(url, files=files, data=data)
            
        if response.status_code != 200:
            send_telegram_message('Video gönderilemedi.')
            
        # remove the video
        os.remove(os.path.join(directory, 'content', f'{downlaoded_clip}'))
        
        cl.dump_settings(setting_file)
        return

    temp = download_mode.split('_')
    
    temp_clips = []
    
    if temp[0] == 'hashtag':
        if temp[1] == 'top':
            clips = cl.hashtag_medias_top(download_hashtag, amount=limitation*2)
        elif temp[1] == 'new':
            clips = cl.hashtag_medias_recent(download_hashtag, amount=limitation*2)
            
        temp_clips = [x.id for x in clips if x.media_type == 2 and x.product_type == 'clips']
    
    else:
        # download users reels
        user_info = shorten_user(cl.user_info_by_username(download_user))
        clips = cl.user_clips(user_info.pk, amount=limitation)
        temp_clips = [x.id for x in clips]
        
    download_directory = os.path.join(directory, 'content')
    count = 0
    for x, clip in enumerate(temp_clips):
        try:
            cl.clip_download(clip, folder=download_directory)
            count += 1
            if x != 0 and (x + 1) % 2 == 0:
                send_telegram_message(f'{x+1} medya indirildi.')
        except Exception as e:
            cl.dump_settings(setting_file)
            raise Exception('Limit aşıldı. Lütfen daha sonra tekrar deneyin.')
        cl.delay_range = [3, 7]
        if x >= limitation:
            break
    cl.dump_settings(setting_file)
    send_telegram_message(f'İşlem başarılı. {count} adet reels indirildi. İndirilen medyalar "content" klasörüne kaydedildi.')
    
argparser = argparse.ArgumentParser()
argparser.add_argument("--mode", help="Mode of the script", required=True, type=str, choices=["add_account", "upload_reel", "download_reel"])
argparser.add_argument("--download_mode", help="Download mode", required=False, type=str, choices=["hashtag_top", "hastag_new", "user", "link"])
argparser.add_argument("--download_hashtag", help="Hashtag to download reels", required=False, type=str)
argparser.add_argument("--download_user", help="Username to download reels", required=False, type=str)
argparser.add_argument("--download_link", help="Link of the reel", required=False, type=str)
argparser.add_argument("--username", help="Instagram username", required=True, type=str)
argparser.add_argument("--password", help="Instagram password", required=False, type=str)
argparser.add_argument("--chat_id", help="Telegram user id", required=True, type=str)
argparser.add_argument("--token", help="Telegram bot token", required=True, type=str)
argparser.add_argument("--directory", help="Directory to store the settings and credentials", required=True, type=str)

args = argparser.parse_args()
mode = args.mode
username = args.username
password = args.password
user_id = args.chat_id
bot_token = args.token
directory = args.directory
    
main_directory = os.path.join(directory, username)
# if the main directory does not exist, create it
if not os.path.exists(main_directory):
    os.makedirs(main_directory)

content_directory = os.path.join(main_directory, 'content')
# if the content directory does not exist, create it
if not os.path.exists(content_directory):
    os.makedirs(content_directory)
    
if mode == 'add_account':
    add_account(username, password, None, main_directory)

elif mode == 'upload_reel':
    # randomly choose a video and caption
    files = os.listdir(content_directory)
    captions = []
    videos = []
    for file in files:
        if file.endswith('.txt'):
            captions.append(os.path.join(content_directory, file))
        elif file.endswith('.mp4'):
            videos.append(os.path.join(content_directory, file))
            
    # if there is no video
    if len(videos) == 0:
        send_telegram_message('Reel yüklenemedi. Lütfen video ekleyin.')
        raise Exception('Reel yüklenemedi. Hiç video yok.')

    # if there is no caption
    if len(captions) == 0:
        captions.append(None)
    # choose a random video and caption
    video = random.choice(videos)
    caption = random.choice(captions)
    
    file_stats = os.stat(video)
    video_size = file_stats.st_size / (1024 * 1024)
    
    if video_size > 49:
        send_telegram_message('Video boyutu çok yüksek. Video preview gönderilemiyor.')
        
    else:   
        # send video and caption to the user and ask for confirmation
        # use sendVideo endpoint
        send_telegram_message('Video preview gönderiliyor...')
        
        url = f'https://api.telegram.org/bot{bot_token}/sendVideo'
        with open(video, 'rb') as f_video, open(caption, 'r', encoding='utf-8') as f_caption:
            data = {
                'chat_id': user_id,
                'caption': f_caption.read(),
                'height': '1920',
                'width': '1080',
                'supports_streaming': True
            }
            files = {
                'video': f_video
            }
            response = requests.post(url, files=files, data=data)
        
        # check if the response is successful
        if response.status_code != 200:
            send_telegram_message('Video gönderilemedi. Video yüklenecek.')
            send_telegram_message(f'Response: {response.text}')
        else:
            send_telegram_message('Reel yüklemek istediğinizden emin misiniz? Seçim yapmak için 20 saniyeniz var. Eğer yüklemek istemiyorsanız aşağıdaki komutu kullanabilirsiniz. Hiçbir şey yapmazsanız video yüklenecektir.')
            send_telegram_message(f'/kill {os.getpid()}')
            time.sleep(20)
    
    # TODO: Remove this if statement, this part only for my personal project
    if username == 'daily.random.duck':
        captions.sort()
        
        f = open(captions[0], 'r', encoding='utf-8')
        count = f.read()
        f.close()
        
        count = int(count)
        f = open(captions[0], 'w', encoding='utf-8')    
        f.write(str(count + 1))
        f.close()
        
        f = open(captions[1], 'r', encoding='utf-8')
        template = f.read()
        f.close()
        template = template.replace(str(count - 1), str(count))
        
        f = open(captions[1], 'w', encoding='utf-8')
        f.write(template)
        f.close()
        caption = captions[1]

    upload_reel(username, video, caption, main_directory)

elif mode == 'download_reel':
    download_reel(username, args.download_mode, args.download_hashtag, args.download_user, main_directory)

else:
    send_telegram_message('Geçersiz mod. Lütfen modu kontrol edin.')
    sys.exit(0)


