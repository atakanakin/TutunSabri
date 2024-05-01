import os
import sys
import json
import shutil
import random
import logging
import requests
import instagrapi

bot_token = sys.argv[1]
user_id = sys.argv[2]
username = sys.argv[3]
directory = sys.argv[4]

def send_telegram_message(message: str):
    global bot_token, user_id
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {
        'chat_id': user_id,
        'text': message
    }
    requests.post(url, data=data)


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
    print(user_agent, flush=True)
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
        print('Giriş yapılamadı. Lütfen yeniden kullanıcı ekleyin.', flush=True)
        sys.exit(7)

    # dump the settings to the folder
    cl.dump_settings(os.path.join(directory, "settings.json"))

    # dump the username and password to the folder
    with open(os.path.join(directory, "credentials.json"), "w", encoding='utf-8') as f:
        json.dump({"username": username, "password": password}, f, ensure_ascii=False)


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
                print(e, flush=True)
                send_telegram_message('Giriş yapılamadı. Lütfen yeniden kullanıcı ekleyin.')
                sys.exit(7)
    except:
        try:
            cl.login(username=username, password=password, relogin=True)
            cl.get_timeline_feed()
            return cl
        except Exception as e:
            send_telegram_message('Giriş yapılamadı. Lütfen yeniden kullanıcı ekleyin.')
            print(e, flush=True)
            sys.exit(7)

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
        send_telegram_message('Reel yüklenemedi. Lütfen tekrar deneyin.')
        raise e
    # in the future; if you want to add thumbnail feature
    #cl.clip_upload(video, caption=caption_str, thumbnail="thumbnail.jpg")
    cl.dump_settings(setting_file)
    os.remove(video)
    try:
        os.remove(video + '.jpg')
    except:
        pass
    send_telegram_message('Reel yüklendi.')
    
main_directory = os.path.join(directory, username)
# if the main directory does not exist, create it
if not os.path.exists(main_directory):
    os.makedirs(main_directory)

content_directory = os.path.join(main_directory, 'content')
# if the content directory does not exist, create it
if not os.path.exists(content_directory):
    os.makedirs(content_directory)

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
    sys.exit(7)
        
# if there is no caption
if len(captions) == 0:
    captions.append(None)
# choose a random video and caption
video = random.choice(videos)
caption = random.choice(captions)

upload_reel(username, video, caption, main_directory)
#add_account(username, 'password', 'verification_code', main_directory)


