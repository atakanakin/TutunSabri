import os
import sys
import json
import yaml
import psutil
import signal
import random
import telebot
import datetime
import subprocess
from telebot import types
from yht_helper import YHTHelper
from youtube_helper import YoutubeHelper
from dropbox_helper import DropBoxUpload

# global variables
active_process = {}
youtube_urls = {}
train_services = {}
usernames = {}
instagram_command_flags = {}


class CustomPopen(subprocess.Popen):
    creation_time = None
    working_directory = None
    wait_to_finish = None
    def dump_those_args(self):
        return self.args, self.creation_time
    def __str__(self) -> str:
        return f'PID: {self.pid}\n Command: {self.args}\n Time: {self.creation_time.strftime("%H:%M:%S")}'

# read the bot token from the json file
with open('bot_config.json') as f:
    data = json.load(f)
    token = data['bot_token']
    owner_id = data['owner_id']
    whitelist = data['white_list']
    dropbox_app_key = data['dropbox_app_key']
    dropbox_app_secret = data['dropbox_app_secret']
    dropbox_oauth2_refresh_token = data['dropbox_oauth2_refresh_token']

# create a dropbox upload object
dbu = DropBoxUpload(dropbox_app_key, dropbox_app_secret, dropbox_oauth2_refresh_token)

# create a bot object
bot = telebot.TeleBot(token)

## create and run a process
def process_handler(executable: list, wait_to_finish: bool, process_name: str, chat_id, cwd=None):
    global bot, active_process
    
    process = CustomPopen(executable,
                          cwd=cwd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                                )
    process.creation_time = datetime.datetime.now()
    process.working_directory = cwd
    process.wait_to_finish = wait_to_finish
    
    if(wait_to_finish):
        # add the process to the active process list
        if chat_id not in active_process:
            active_process[chat_id] = {}
        if process_name in active_process[chat_id]:
            active_process[chat_id][process_name].append(process)
        else:
            active_process[chat_id][process_name] = [process]
        # wait for the process to complete
        stdout, stderr = process.communicate()
        # get the exit code
        exit_code = process.returncode
        if(exit_code != 0):
            stderr_str = stderr.decode('utf-8')
            return (False, stderr_str)
        # decode stdout
        stdout_str = stdout.decode('utf-8')
        output = stdout_str.strip().split('\n')
        
        # remove the process from the active process list
        active_process[chat_id][process_name].remove(process)
        if len(active_process[chat_id][process_name]) == 0:
            del active_process[chat_id][process_name]
        if len(active_process[chat_id]) == 0:
            del active_process[chat_id]
            
        return (True, output[-1].strip())
    else:
        if chat_id not in active_process:
            active_process[chat_id] = {}
        # check if active process have key with chat id
        if chat_id in active_process and process_name in active_process[chat_id]:
            active_process[chat_id][process_name].append(process)
        else:
            active_process[chat_id][process_name] = [process]
            
        if process_name in ['gramaddict', 'instagram']:
            stdout, stderr = process.communicate()
            # check return code
            if process.returncode != 0:
                bot.send_message(chat_id, f'Bir hata oluştu: {process.returncode}')
            stdout_str = stdout.decode('utf-8')
            output = stdout_str.strip()
            if output != '':
                f = open(f'temp_{chat_id}_out.txt', 'w')
                f.write(stdout_str)
                f.close()
                bot.send_document(chat_id, open(f'temp_{chat_id}_out.txt', 'rb'))
                os.remove(f'temp_{chat_id}_out.txt')
            
            stderr_str = stderr.decode('utf-8').strip()
            if(stderr_str != ''):
                f = open(f'temp_{chat_id}_err.txt', 'w')
                f.write(stderr_str)
                f.close()
                bot.send_document(chat_id, open(f'temp_{chat_id}_err.txt', 'rb'))
                os.remove(f'temp_{chat_id}_err.txt')
            # remove the process from the active process list
            active_process[chat_id][process_name].remove(process)
            if len(active_process[chat_id][process_name]) == 0:
                del active_process[chat_id][process_name]
            if len(active_process[chat_id]) == 0:
                del active_process[chat_id]
                
# dump active process to a file
def dump_active_process():
    global active_process
    
    process_hold = {'active_process': []}

    if(len(active_process) > 0):
        for key, value in active_process.items():
            if(len(value) > 0):
                for key2, value2 in value.items():
                    for process in value2:
                        try:
                            user = key
                            process_name = key2
                            args, creation_time = process.dump_those_args()
                            working_directory = process.working_directory
                            wait_to_finish = process.wait_to_finish
                            process_hold['active_process'].append({'user': user, 'process_name': process_name, 'args': args, 'working_directory': working_directory, 'wait_to_finish': wait_to_finish})
                        except Exception as e:
                            print(f'Could not write the active process to the file. {e}', flush=True)
                   
    with open('active_process.json', 'w', encoding='utf-8') as f:
        json.dump(process_hold, f)
    
        
def load_active_process():
    with open('active_process.json', 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return
        if 'active_process' in data:
            for process in data['active_process']:
                user = process['user']
                process_name = process['process_name']
                args = process['args']
                working_directory = process['working_directory']
                wait_to_finish = process['wait_to_finish']
                try:
                    # enhance this part by adding synchronization and also handling the return value
                    # do not let func call block the main thread - run it in a separate thread
                    # use a lock to synchronize the access to the active_process dictionary
                    # use a condition variable to signal the main thread that the process is done
                    # use a queue to store the return value
                    # use a separate thread to handle the return value
                    # TODO: Implement the above v2.0
                    
                    # for now, just run processes that do not wait for the process to finish and important ones
                    if process_name in ['spor', 'yht']:
                        bot.send_message(user, f'{process_name} işlemi kaldığı yerden devam ediyor...')
                        process_handler(args, wait_to_finish, process_name, user, cwd=working_directory)
                        
                except Exception as e:
                    bot.send_message(user, f'{process_name} işlemi kaldığı yerden devam ederken bir hata oluştu. {e}')
    
    # clear the file
    with open('active_process.json', 'w', encoding='utf-8') as f:
        f.write('')

try:
    load_active_process()
except Exception as e:
    print(f'Could not load the active process. {e}', flush=True)
    
def signal_handler(sig, frame):
    # Inform the owner that the program is shutting down
    global owner_id
    global bot
    global active_process
    bot.send_message(owner_id, "Program kapatılıyor.")
    dump_active_process()
    # kill all active processes
    if(len(active_process) > 0):
        for key, value in active_process.items():
            if(len(value) > 0):
                for key2, value2 in value.items():
                    for process in value2:
                        try:
                            bot.send_message(key, f'{key2} işlemi kapatılıyor. Görüşürüz...')
                            if key2 in ['spor', 'yht']:
                                bot.send_message(key, f'Merak etme, [@atakan](tg://user?id={owner_id}) botu başlattığında __{key2}__ işlemini yeniden çalıştırmaya çalışcağım. Benden haber bekle...', parse_mode='Markdown')
                            kill_process_tree(process)
                        except Exception as e:
                            print(f'Process with pid {process.pid} thrown an exception. Could not kill the process. {e}', flush=True)
                            
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# some helper functions

def kill_process_tree(process):
    # I wish I lived in a world where I could just call process.kill() and be done with it
    parent = psutil.Process(process.pid)
    for child in parent.children(recursive=True):
        child.kill()
        
    process.kill()    

## create a message for the user to see the active processes
def create_process_list_message(chat_id):
    global active_process
    user_jobs = ''
    # get keys and their values together
    if chat_id not in active_process:
        return user_jobs

    for key, value in active_process[chat_id].items():
        if(len(value) > 0):
            user_jobs += f'{key}: adı altında {len(value)} tane işleminiz bulunmaktadır. \n\n'
            
    if(len(user_jobs) > 0):
        user_jobs = 'Aşağıda çalışmakta olan tüm işlemlerinizi görebilirsiniz.: \n\n' + user_jobs

    return user_jobs

## handle the file and send it to the user
def file_handler(message, output:str, type: str):
    global bot
    global dbu
    file = open(output, 'rb')
    if(type == 'audio'):
        try:
            bot.send_audio(message.chat.id, audio = file)
        except Exception as e:
            bot.send_message(message.chat.id, f'Ses dosyasını dropboxa yüklüyorum...')
            bot.send_message(message.chat.id, f'Video 1 gün sonra silinecektir.')
            try:
                audUrl = dbu.UpLoadFile('',output)
                bot.send_message(message.chat.id, text= f'<a href="{audUrl}">Ses dosyasını indir</a>', parse_mode='HTML')
            except Exception as dropboxError:
                bot.send_message(message.chat.id, f'Dropboxa yüklenirken bir hata oluştu.')
                
    elif(type == 'video'):
        try:
            file_id = bot.send_video(message.chat.id, video = file, supports_streaming=True, width=1920, height=1080)
            print(file_id.video.file_id) #TODO: Remove this line
        except Exception as e:
            bot.send_message(message.chat.id, f'Videoyu dropboxa yüklüyorum...')
            bot.send_message(message.chat.id, f'Video 1 gün sonra silinecektir.')
            try:
                vidUrl = dbu.UpLoadFile('',output)
                bot.send_message(message.chat.id, text= f'<a href="{vidUrl}">Videoyu indir</a>', parse_mode='HTML')
            except Exception as dropboxError:
                bot.send_message(message.chat.id, f'Dropboxa yüklenirken bir hata oluştu.')
    file.close()
    os.remove(output)
            
# check if the user is in the white list
def access_control(chat_id, admin: bool = False):
    global whitelist, bot, owner_id
    chat_id = str(chat_id)
    if chat_id == owner_id:
        return True
    elif chat_id in whitelist and not admin:
        return True
    elif chat_id in whitelist and admin:
        bot.send_message(chat_id, f'Bu işlemi yapmaya yetkiniz yok. Bu işlemi sadece [@atakan](tg://user?id={owner_id}) yapabilir.', parse_mode='Markdown')
        return False
    else:
        # inline keyboard markup
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        request_button = types.InlineKeyboardButton("Yetki İste  \U0001F6A7", callback_data='request')
        cancel_button = types.InlineKeyboardButton("İptal  \U0000274C", callback_data='cancel')
        keyboard.add(request_button, cancel_button)
        bot.send_message(chat_id, f'Bu işlemi yapmaya yetkiniz yok. Botu kullanabilmek için [@atakan](tg://user?id={owner_id}) kullanıcısından yetki isteyebilirsiniz.', parse_mode='Markdown', reply_markup=keyboard)
        # handle the callback
        @bot.callback_query_handler(func=lambda call: call.data == 'request')
        def request(call):
            bot.send_message(owner_id, f'[{call.message.chat.username}](tg://user?id={call.message.chat.id}) kullanıcısı yetki istiyor.', parse_mode='Markdown')
            # log the request
            request_file = os.path.join(os.getcwd(), 'requests', f'{call.message.chat.id}.txt')
            f = open(request_file, 'w')
            # log first name, last name, username, chat id, date
            f.write(f'{call.message.chat.first_name} {call.message.chat.last_name}\n{call.message.chat.username}\n{call.message.chat.id}\n{call.message.date}')
            f.close()            
            bot.send_message(call.message.chat.id, "Yetki isteğiniz gönderildi. Lütfen bekleyin.")
            bot.delete_message(call.message.chat.id, call.message.message_id)
        @bot.callback_query_handler(func=lambda call: call.data == 'cancel')
        def cancel(call):
            bot.delete_message(call.message.chat.id, call.message.message_id)
        return False
    
def gramaddict_yaml_file(chat_id):
    global usernames
    # get the directory for the gramaddict folder
    #  python -m site --user-site
    site = subprocess.run(['python', '-m', 'site', '--user-site'], stdout=subprocess.PIPE)
    # ensure the process is completed
    site.check_returncode()
    # get the site path
    site_path = site.stdout.decode('utf-8').strip('\n')
    # get the gramaddict folder
    gramaddict_folder = os.path.join(site_path, 'GramAddict')
    # get the username
    username = usernames[str(chat_id)]
    yaml_file = os.path.join(gramaddict_folder, 'accounts', username, 'config.yml')
    return yaml_file, site_path

def configure_yaml_file(config_file, to_add):
    with open(config_file) as f:
        config = yaml.safe_load(f)

    if 'blogger-followers' in config:
        del config['blogger-followers']

    if 'blogger-post-likers' in config:
        del config['blogger-post-likers']

    if 'hashtag-likers-top' in config:
        del config['hashtag-likers-top']

    if 'unfollow-any' in config:
        del config['unfollow-any']

    if 'working-hours' in config:
        del config['working-hours']

    f = open(config_file, 'w')
    f.write(yaml.dump(config, default_flow_style=False))
    f.write('working-hours: [00.00-23.59]\n')
    f.write(to_add)
    f.close()
    
# next step handlers

## youtube
def get_youtube_start_time(message):
    global youtube_urls
    try:
        chat_id = message.chat.id
        start_time = message.text.strip()
        if start_time == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            youtube_urls.pop(chat_id)
            return
        x = start_time.split(':')
        if len(x) != 2 or not x[0].isdigit() or not x[1].isdigit():
            bot.send_message(chat_id, "Hata: Lütfen başlangıç zamanını örnekteki gibi giriniz. Örnek: 01:15. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
            youtube_urls.pop(chat_id)
            bot.register_next_step_handler_by_chat_id(chat_id, get_youtube_start_time)
            return
        youtube_urls[chat_id].start_time = start_time
        bot.send_message(chat_id, "Klip bitiş zamanını giriniz: (Örnek: 01:30) veya 'cancel' yazarak işlemi iptal edebilirsiniz.")
        bot.register_next_step_handler_by_chat_id(chat_id, get_youtube_end_time)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
def get_youtube_end_time(message):
    global youtube_urls
    try:
        chat_id = message.chat.id
        end_time = message.text.strip()
        if end_time == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            youtube_urls.pop(chat_id)
            return
        x = end_time.split(':')
        if len(x) != 2 or not x[0].isdigit() or not x[1].isdigit():
            bot.send_message(chat_id, "Hata: Lütfen bitiş zamanını örnekteki gibi giriniz. Örnek: 02:57. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
            youtube_urls.pop(chat_id)
            bot.register_next_step_handler_by_chat_id(chat_id, get_youtube_end_time)
            return
        youtube_urls[chat_id].end_time = end_time
        bot.send_message(chat_id, "Klip indiriliyor...\nLütfen bekleyin.")
        # call the downloader
        executable_file = os.path.join(os.getcwd(), 'youtube', 'executable', 'youtube')
        arguments = [youtube_urls[chat_id].url, os.getcwd(), 'clip', youtube_urls[chat_id].start_time, youtube_urls[chat_id].end_time]
        
        out = process_handler([executable_file] + arguments, True, 'youtube', chat_id)
        
        if(not out[0]):
            bot.send_message(chat_id, f'Bir sorun oluştu: {out[1]}')
            return
        
        youtube_urls.pop(chat_id)
        
        file_handler(message, out[1], type='video')
        
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')        

## yht
def get_yht_departure_station(message):
    global train_services
    try:
        chat_id = message.chat.id
        departure_station = message.text.strip()
        if departure_station == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        train_services[chat_id] = YHTHelper(departure_station)
        bot.send_message(chat_id, "Varış istasyonunu giriniz: (Örnek: Konya (Selçuklu YHT)). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(chat_id, get_yht_arrival_station)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')

def get_yht_arrival_station(message):
    global train_services
    try:
        chat_id = message.chat.id
        arrival_station = message.text.strip()
        if arrival_station == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            train_services.pop(chat_id)
            return
        train_services[chat_id].arrival_station = arrival_station
        bot.send_message(chat_id, "Tarih bilgisini giriniz: (Örnek: 13.04.2024). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(chat_id, get_yht_date)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')

def get_yht_date(message):
    global train_services
    try:
        chat_id = message.chat.id
        date = message.text.strip()
        if date == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            train_services.pop(chat_id)
            return
        train_services[chat_id].date = date
        bot.send_message(chat_id, "Saat bilgisini giriniz: (Örnek: 15:33). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(chat_id, get_yht_time)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
def get_yht_time(message):
    global train_services
    try:
        chat_id = message.chat.id
        time = message.text.strip()
        if time == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            train_services.pop(chat_id)
            return
        train_services[chat_id].time = time
        bot.send_message(chat_id, f'{train_services[chat_id].departure_station} - {train_services[chat_id].arrival_station} arası {train_services[chat_id].date} - {train_services[chat_id].time} tarihindeki tren seferleri için boş koltuk aranıyor...')
        # call the train search
        python_file = os.path.join(os.getcwd(), 'yht', 'yht_check.py')
        arguments = [token, str(chat_id), train_services[chat_id].departure_station, train_services[chat_id].arrival_station, train_services[chat_id].date, train_services[chat_id].time]
        
        bot.send_message(chat_id, 'Arama işlemini durdurmak istediğinde /yhtcancel komutunu kullanabilirsin.')        
        process_handler(['python', python_file] + arguments, False, 'yht', message.chat.id)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
## spor
def get_spor_username(message):
    try:
        chat_id = message.chat.id
        username = message.text.strip()
        if username == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        user_credential_path = os.path.join(os.getcwd(), 'credentials', 'rezmetu', f'{chat_id}.json')
        with open(user_credential_path, 'w') as f:
            json.dump({'username': username}, f)
            
        bot.send_message(chat_id, "Şifrenizi giriniz: , İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(chat_id, get_spor_password)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
def get_spor_password(message):
    try:
        chat_id = message.chat.id
        password = message.text.strip()
        if password == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        user_credential_path = os.path.join(os.getcwd(), 'credentials', 'rezmetu', f'{chat_id}.json')
        with open(user_credential_path, 'r+') as f:
            config = json.load(f)
            config['password'] = password
            f.seek(0)
            f.write(json.dumps(config))
        bot.send_message(chat_id, "Kullanıcı bilgileriniz kaydedildi.")
        bot.send_message(message.chat.id, "Lütfen seans başlangıç saatini giriniz: (Örnek: 19:35). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(message.chat.id, get_spor_time)
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
    
def get_spor_time(message):
    try:
        chat_id = message.chat.id
        desired_time = message.text.strip()
        if desired_time == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        bot.send_message(chat_id, "Program başlatılıyor...\nLütfen bekleyin.")
        bot.send_message(chat_id, 'Arama işlemini durdurmak istediğinde /sporcancel komutunu kullanabilirsin.')   
        # call the reservation
        python_file = os.path.join(os.getcwd(), 'spor', 'spor_v2.py')
        arguments = [str(chat_id), token, desired_time]
        
        process_handler(['python', python_file] + arguments, False, 'spor', chat_id)
    
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
## broadcast
def get_broadcast_message(message):
    # get the media type and file id from the message
    global whitelist
    white_list_temp = whitelist.copy()
    white_list_temp.append(owner_id)
    if message.content_type == 'video':
        file_id = message.video.file_id
        for user in white_list_temp:
            bot.send_video(int(user), file_id, caption=f'[@atakan](tg://user?id={owner_id}) bu videoyu herkesin izlemesi gerektiğini düşünüyor.', parse_mode='Markdown', supports_streaming=True)
    elif message.content_type == 'photo':
        file_id = None
        size_temp = 0
        for photo in message.photo:
            if photo.file_size > size_temp:
                file_id = photo.file_id
                size_temp = photo.file_size
        for user in white_list_temp:
            bot.send_photo(int(user), file_id, caption=f'[@atakan](tg://user?id={owner_id}) bu fotoğrafı herkesin görmesi gerektiğini düşünüyor.', parse_mode='Markdown')
    elif message.content_type == 'audio':
        file_id = message.audio.file_id
        for user in white_list_temp:
            bot.send_audio(int(user), file_id, caption=f'[@atakan](tg://user?id={owner_id}) bu ses dosyasını herkesin dinlemesi gerektiğini düşünüyor.', parse_mode='Markdown')
        
## instagram
def get_instagram_download_info(message):
    global usernames, instagram_command_flags, token
    try:
        chat_id = message.chat.id
        user_input = message.text.strip()
        if user_input == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        bot.send_message(chat_id, "Lütfen bekleyin.")
        # call the instagram
        mode = instagram_command_flags[str(chat_id)]
        python_file = os.path.join(os.getcwd(), 'instagram', 'instagram.py')
        arguments = [
            "--mode", "download_reel",
            "--download_mode", mode,
            "--username", usernames[str(chat_id)],
            "--chat_id", str(chat_id),
            "--token", token,
            "--directory", os.path.join(os.getcwd(), 'credentials', 'instagram'),
        ]
        if mode == 'user':
            arguments += ["--download_user", user_input]
        else:
            arguments += ["--download_hashtag", user_input]
        
        process_handler(['python', python_file] + arguments, False, 'instagram', chat_id)
        
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
def get_instagram_follow_info(message):
    global usernames, instagram_command_flags
    try:
        chat_id = message.chat.id
        user_input = message.text.strip()
        if user_input == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        mode = instagram_command_flags[str(chat_id)]
        bot.send_message(message.chat.id, f"İşlem başlatılıyor...")

        yaml_file, site_path = gramaddict_yaml_file(message.chat.id)
        # edit the yaml file
        configure_yaml_file(yaml_file, f'{mode}[{user_input}]')

        # run the bot
        arguments = [
            'gramaddict', 'run',
            "--config", f'accounts/{usernames[str(message.chat.id)]}/config.yml',
        ]
        
        process_handler(arguments, False, 'gramaddict', message.chat.id, cwd=f'{site_path}/GramAddict')
        
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
        
def get_instagram_username(message):
    try:
        chat_id = message.chat.id
        username = message.text.strip()
        if username == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
        with open(f'{chat_id}_instagram_temp.json', 'w') as f:
            json.dump({'username': username}, f)
        bot.send_message(chat_id, "Şifrenizi giriniz: , işlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(chat_id, get_instagram_password)
    
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
    
def get_instagram_password(message):
    try:
        chat_id = message.chat.id
        password = message.text.strip()
        if password == 'cancel':
            bot.send_message(chat_id, "İşlem iptal edildi.")
            return
            
        with open(f'{chat_id}_instagram_temp.json', 'r') as f:
            data = json.load(f)
            username = data['username']
            
        os.remove(f'{chat_id}_instagram_temp.json')

        instagram_path = os.path.join(os.getcwd(), 'credentials', 'instagram')
        
        bot.send_message(message.chat.id, f'{username} kullanıcısı ekleniyor.')
        
        python_file = os.path.join(os.getcwd(), 'instagram', 'instagram.py')
        arguments = [
            "--mode", "add_account",
            "--username", username,
            "--password", password,
            "--chat_id", str(chat_id),
            "--token", token,
            "--directory", instagram_path,
        ]
        out = process_handler(['python', python_file] + arguments, True, 'instagram', message.chat.id)
        if(not out[0]):
            bot.send_message(chat_id, f'Bir sorun oluştu: {out[1]}')
            return
    except Exception as e:
        bot.send_message(chat_id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
# command handlers

## start, help, info
@bot.message_handler(commands=['start', 'help', 'info'])
def start(message):
   # open the welcome message file
    
    # create reply markup
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    whoami_button = types.InlineKeyboardButton("Ben Kimim?  \U0001F464", callback_data='whoami')
    howtowork_button = types.InlineKeyboardButton("Nasıl Çalışır?  \U0001F4BB", callback_data='howtowork')
    contact_button = types.InlineKeyboardButton("İletişim  \U0001F4E9", callback_data='contact')
    
    keyboard.add(whoami_button, howtowork_button, contact_button)
    
    start = open('info/start.txt', 'r', encoding='utf-8')
    start_message = start.read()
    start.close()
    
    bot.send_message(message.chat.id, start_message, reply_markup=keyboard)
    
    @bot.callback_query_handler(func=lambda call: call.data == 'whoami')
    def whoami(call):
        whoami = open('info/whoami.txt', 'r', encoding='utf-8')
        whoami_message = whoami.read()
        whoami.close()
        bot.send_message(call.message.chat.id, whoami_message)
        bot.send_photo(call.message.chat.id, photo = 'AgACAgQAAxkDAAIEgWYkV3BKtaeqtdZQLXC4NSB_LF7LAALtwTEbjY8gUYKMYUIbPb_0AQADAgADeQADNAQ', caption='Gerçekte ben.')
        
    @bot.callback_query_handler(func=lambda call: call.data == 'howtowork')
    def howtowork(call):
        howtowork = open('info/howtowork.txt', 'r', encoding='utf-8')
        howtowork_message = howtowork.read()
        howtowork.close()
        bot.send_message(call.message.chat.id, howtowork_message, parse_mode='HTML')
        
    @bot.callback_query_handler(func=lambda call: call.data == 'contact')
    def contact(call):
        contact = open('info/contact.txt', 'r', encoding='utf-8')
        contact_message = contact.read()
        contact.close()
        bot.send_message(call.message.chat.id, contact_message)
    

## youtube
@bot.message_handler(commands=['youtube'])
def youtube_handler(message):
    if not access_control(message.chat.id):
        return
    # Extract the YouTube URL from the message text
    try:
        youtube_url = message.text.split(' ', 1)[1]
        youtube_urls[message.chat.id] = YoutubeHelper(youtube_url)
    except IndexError:
        bot.reply_to(message, "Hata: youtube komutu kullanımı '/youtube video_link' olacak şekildedir daha fazla detay için '/help' komutunu kullanabilirsiniz.")
        return
    # Create inline keyboard markup
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    full_video_button = types.InlineKeyboardButton("Full Video  \U0001F517", callback_data='full_video')
    extract_clip_button = types.InlineKeyboardButton("Klip  \U0001F3AC", callback_data='extract_clip')
    only_audio_button = types.InlineKeyboardButton("Sadece Ses  \U0001F50A", callback_data='only_audio')
    cancel_button = types.InlineKeyboardButton("İptal  \U0000274C", callback_data='cancel')
    keyboard.add(full_video_button, extract_clip_button, only_audio_button, cancel_button)

    bot.reply_to(message, "Lütfen bir seçenek seçiniz.", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data == 'full_video')
    def full_video(call):
        global youtube_urls
        youtube_url = youtube_urls[call.message.chat.id].url
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Video indiriliyor...\nLütfen bekleyin.")
        # call the downloader
        executable_file = os.path.join(os.getcwd(), 'youtube', 'executable', 'youtube')
        arguments = [youtube_url, os.getcwd(), 'full_video']

        out = process_handler([executable_file] + arguments, True, 'youtube', call.message.chat.id)
        
        if(not out[0]):
            bot.send_message(call.message.chat.id, f'Bir sorun oluştu: {out[1]}')
            return
    
        file_handler(call.message, out[1], type='video')
        return
        

    @bot.callback_query_handler(func=lambda call: call.data == 'extract_clip')
    def extract_clip(call):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # ask for the start and end time
        bot.send_message(call.message.chat.id, "Klip başlangıç zamanını giriniz: (Örnek: 00:00). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_youtube_start_time)

    @bot.callback_query_handler(func=lambda call: call.data == 'only_audio')
    def only_audio(call):
        global youtube_urls
        youtube_url = youtube_urls[call.message.chat.id]
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Ses indiriliyor...\nLütfen bekleyin.")
        # call the downloader
        executable_file = os.path.join(os.getcwd(), 'youtube', 'executable', 'youtube')
        arguments = [youtube_url.url , os.getcwd(), 'audio']
        
        out = process_handler([executable_file] + arguments, True, 'youtube', call.message.chat.id)
        
        if(not out[0]):
            bot.send_message(call.message.chat.id, f'Bir sorun oluştu: {out[1]}')
            return
        
        file_handler(call.message, out[1], type='audio')
        
        return
    
    @bot.callback_query_handler(func=lambda call: call.data == 'cancel')
    def cancel(call):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "İşlem iptal edildi.")
        return

# ## twitter
# @bot.message_handler(commands=['twitter'])
# def twitter_handler(message):
#     if not access_control(message.chat.id):
#         return
#     # if user has credentials
#     credentials = None
#     user_credential_path = os.path.join(os.getcwd(), 'credentials', 'twitter', f'{message.chat.id}.json')
#     if(os.path.exists(user_credential_path)):
#         with open(user_credential_path) as f:
#             credentials = json.load(f)
#         bot.send_message(message.chat.id, f'{credentials["username"]} kullanıcısı ile giriş yapıldı.')
#     else:
#         # ask for credentials
#         bot.send_message(message.chat.id, "Twitter kullanıcı adınızı giriniz:")
#         hold = [True, True]
#         @bot.message_handler(func=lambda message: hold[0])
#         def get_twitter_username(message):
#             twitter_username = message.text
#             hold[0] = False
#             bot.send_message(message.chat.id, "Twitter şifrenizi giriniz:")
#             @bot.message_handler(func=lambda message: hold[1])
#             def get_twitter_password(message):
#                 hold[1] = False
#                 twitter_password = message.text
#                 credentials = {
#                     'username': twitter_username,
#                     'password': twitter_password
#                 }
#                 with open(user_credential_path, 'w') as f:
#                     json.dump(credentials, f)
#     bot.send_message(message.chat.id, "Bu işlem biraz zaman alabilir.\nLütfen bekleyin...")

## YHT Train
@bot.message_handler(commands=['yht'])
def yht_handler(message):
    if not access_control(message.chat.id):
        return
    if message.text.strip() not in ['/yht', '/yht ']:
        bot.send_message(message.chat.id, "Hata: Lütfen komutu '/yht' şeklinde kullanınız. {message.text}")
        return
    bot.send_message(message.chat.id, "Kalkış istasyonunu giriniz (Örnek: Ankara Gar). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
    bot.register_next_step_handler_by_chat_id(message.chat.id, get_yht_departure_station)

## cancel the yht search
@bot.message_handler(commands=['yhtcancel'])
def yht_cancel_handler(message):
    global owner_id
    if not access_control(message.chat.id):
        return
    global active_process
    if message.chat.id in active_process and 'yht' in active_process[message.chat.id]:
        for process in active_process[message.chat.id]['yht']:
            # kill the process with the pid
            try:
               kill_process_tree(process)
               # if it does not stop causing problems, use the following line
               #os.system(f'kill -9 {process.pid}') # an elegant solution :)
            except ProcessLookupError as e:
                bot.send_message(message.chat.id, f'Process with pid {process.pid} not found.')
                bot.send_message(owner_id, f'Process with pid {process.pid} not found. {e}\n\n {message.chat.id}: yht' )
                return
            except Exception as e:
                bot.send_message(message.chat.id, f'Process with pid {process.pid} thrown an exception. Could not kill the process.')
                bot.send_message(owner_id, f'Process with pid {process.pid} thrown an exception. Could not kill the process. {e}\n\n {message.chat.id}: yht')
                return
            active_process[message.chat.id]['yht'].remove(process)
            if(len(active_process[message.chat.id]['yht']) == 0):
                del active_process[message.chat.id]['yht']
            if(len(active_process[message.chat.id]) == 0):
                del active_process[message.chat.id]
        bot.send_message(message.chat.id, "Tren seferi arama işlemi iptal edildi.")
    else:
        bot.send_message(message.chat.id, "Aktif bir tren seferi arama işlemi bulunamadı.")

        user_jobs = create_process_list_message(message.chat.id)
        
        if(len(user_jobs) > 0):
            bot.send_message(message.chat.id, user_jobs)
            

## text to speech
@bot.message_handler(commands=['tts'])
def tts_handler(message):
    if not access_control(message.chat.id):
        return
    # Extract the text from the message text
    try:
        text = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Hata: Lütfen bir metin giriniz.")
        return
    if len(text) < 12:
        bot.reply_to(message, "Hata: Lütfen daha uzun bir metin giriniz.")
        return
    bot.reply_to(message, "Lütfen bekleyin...")
    
    txt_file = os.path.join(os.getcwd(), 'temp_content', f'{message.message_id}_tts_req.txt')

    f = open(txt_file, 'w', encoding='utf-8')
    f.write(text)
    f.close()

    python_file = os.path.join(os.getcwd(), 'tts', 'tts.py')
    arguments = ['--path', txt_file]

    out = process_handler(['python', python_file] + arguments, True, 'tts', message.chat.id)
    
    if(not out[0]):
        bot.send_message(message.chat.id, f'Bir sorun oluştu: {out[1]}')
        return
    
    file_handler(message, out[1], type='audio')
    
    
## spor
@bot.message_handler(commands=['spor'])
def spor_handler(message):
    if not access_control(message.chat.id):
        return
    # check if the user has credentials
    user_credential_path = os.path.join(os.getcwd(), 'credentials', 'rezmetu', f'{message.chat.id}.json')
    if(os.path.exists(user_credential_path)):
        f = open(user_credential_path, 'r')
        config = json.load(f)
        f.close()
        bot.send_message(message.chat.id, f'{config["username"]} kullanıcısı ile işlem yapılacak.')
        bot.send_message(message.chat.id, "Lütfen seans saat başlangıç saatini giriniz: (Örnek: 19:35). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(message.chat.id, get_spor_time)
    else:
        # ask for credentials
        bot.send_message(message.chat.id, "Rezervasyon yapmak için lütfen kullanıcı adınızı giriniz: (Örnek: e123456). İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
        bot.register_next_step_handler_by_chat_id(message.chat.id, get_spor_username)

## cancel the spor reservation
@bot.message_handler(commands=['sporcancel'])
def spor_cancel_handler(message):
    global owner_id
    if not access_control(message.chat.id):
        return
    global active_process
    if message.chat.id in active_process and 'spor' in active_process[message.chat.id]:
        for process in active_process[message.chat.id]['spor']:
            # kill the process with the pid
            try:
               kill_process_tree(process)
                # if it does not stop causing problems, use the following line
                #os.system(f'kill -9 {process.pid}') # an elegant solution :)
            except ProcessLookupError as e:
                bot.send_message(message.chat.id, f'Process with pid {process.pid} not found.')
                bot.send_message(owner_id, f'Process with pid {process.pid} not found. {e}\n\n {message.chat.id}: spor')
                return
            except Exception as e:
                bot.send_message(message.chat.id, f'Process with pid {process.pid} thrown an exception. Could not kill the process.')
                bot.send_message(owner_id, f'Process with pid {process.pid} thrown an exception. Could not kill the process. {e}\n\n {message.chat.id}: spor')
                return
            active_process[message.chat.id]['spor'].remove(process)
            if(len(active_process[message.chat.id]['spor']) == 0):
                del active_process[message.chat.id]['spor']
            if(len(active_process[message.chat.id]) == 0):
                del active_process[message.chat.id]
        bot.send_message(message.chat.id, "Spor salonu rezervasyon işlemi iptal edildi.")
    else:
        bot.send_message(message.chat.id, "Aktif bir spor salonu rezervasyon işlemi bulunamadı.")
        
        user_jobs = create_process_list_message(message.chat.id)
        
        if(len(user_jobs) > 0):
            bot.send_message(message.chat.id, user_jobs)
            
    
## mood
@bot.message_handler(commands=['mood'])
def mood_handler(message):
    if not access_control(message.chat.id):
        return
    try:
        # get video file id's from file
        with open(os.path.join(os.getcwd(), 'mood', 'mood.json'), 'r') as f:
            mood = json.load(f)
        video_ids = mood['video_ids']
        # choose a random video,
        video_id = random.choice(video_ids)
        # send the video
        bot.send_video(message.chat.id, video = video_id, supports_streaming=True, width=1920, height=1080)
    except Exception as e:
        bot.send_message(message.chat.id, f'Bu mesajı aldıysan bir şeyler çok yanlış ve büyük ihtimalle benimle ilgili değil. {e}')
    
    
## pedro
@bot.message_handler(commands=['pedro'])
def pedro_handler(message):
    if not access_control(message.chat.id):
        return
    bot.send_video(message.chat.id, video = 'BAACAgQAAxkDAAIEI2YkHfk_t10R31SISqYxWk27VaDcAAJGEwACwmwgUZ6kBxvyfD_UNAQ', supports_streaming=True, width=1920, height=1080)


# admin commands

## get requests
@bot.message_handler(commands=['requests'])
def requests_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    # get all request files
    requests = os.listdir(os.path.join(os.getcwd(), 'requests'))
    requests = [request for request in requests if request.endswith('.txt')]
    if(len(requests) == 0):
        bot.send_message(message.chat.id, "Henüz hiçbir yetki isteği bulunmamaktadır.")
        return
    for request in requests:
        f = open(os.path.join(os.getcwd(), 'requests', request), 'r', encoding='utf-8')
        user_info = f.read().strip().split('\n')
        f.close()
        bot.send_message(message.chat.id, f'Kullanıcı: {user_info[0]} @{user_info[1]} ({user_info[2]})\nTarih: {user_info[3]}')
        bot.send_message(message.chat.id, f'Kullanıcıya yetki vermek için /grant {user_info[2]} komutunu kullanabilirsiniz.')
            
## grant access
@bot.message_handler(commands=['grant'])
def grant_handler(message):
    global data
    if not access_control(message.chat.id, admin=True):
        return
    # get the user id from the message text
    try:
        user_id = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Hata: Lütfen bir kullanıcı id'si giriniz.")
        return
    # check if the user id is in the requests
    request_file = os.path.join(os.getcwd(), 'requests', f'{user_id}.txt')
    if not os.path.exists(request_file):
        bot.reply_to(message, "Hata: Kullanıcı isteği bulunamadı.")
        return
    # get the user info
    with open(request_file, 'r', encoding='utf-8') as f:
        user_info = f.readlines()
    # add the user to the white list
    global whitelist
    whitelist.append(user_info[2].strip('\n'))
    # remove the request file
    os.remove(request_file)
    # add the user to the white list file
    with open('bot_config.json', 'w') as f:
        data['white_list'] = whitelist
        json.dump(data, f)
    # send a message to the user
    bot.send_message(int(user_info[2]), "Yetkiniz verildi. Artık botu kullanabilirsiniz.")
    bot.send_message(message.chat.id, f'Kullanıcı yetkisi verildi: {user_info[0]} @{user_info[1]} ({user_info[2]})')
    
## revoke access
@bot.message_handler(commands=['revoke'])
def revoke_handler(message):
    global data
    if not access_control(message.chat.id, admin=True):
        return
    # get the user id from the message text
    try:
        user_id = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Hata: Lütfen bir kullanıcı id'si giriniz.")
        return
    # check if the user id is in the white list
    global whitelist
    if user_id not in whitelist:
        bot.reply_to(message, "Hata: Kullanıcı zaten yetkili değil.")
        return
    # remove the user from the white list
    whitelist.remove(user_id)
    # add the user to the white list file
    with open('bot_config.json', 'w') as f:
        data['white_list'] = whitelist
        json.dump(data, f)
    # send a message to the user
    bot.send_message(int(user_id), "Yetkiniz alındı. Artık botu kullanamazsınız.")
    bot.send_message(message.chat.id, f'Kullanıcı yetkisi geri alındı: {user_id}')
    
## broadcast
@bot.message_handler(commands=['broadcast'])
def broadcast_handler(message):
    if not access_control(message.chat.id, admin=True):
        return

    bot.send_message(message.chat.id, "Lütfen göndermek istediğiniz mesajı yazınız. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
    bot.register_next_step_handler_by_chat_id(message.chat.id, get_broadcast_message)
    
## list users
@bot.message_handler(commands=['listusers'])
def listusers_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    global whitelist
    for user in whitelist:
        bot.send_message(message.chat.id, f'[{user}](tg://user?id={user})', parse_mode='Markdown')
        
## list active processes
@bot.message_handler(commands=['process'])
def process_message_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    global active_process
    
    # if there is no active process
    if(len(active_process) == 0):
        bot.send_message(message.chat.id, "Şu anda hiçbir işlem çalışmıyor.")
        return
    
    for key, value in active_process.items():
        for key2, value2 in value.items():
            for process in value2:
                bot.send_message(message.chat.id, f'user: {key}, process: {str(process)}')
                
## kill process with pid
@bot.message_handler(commands=['kill'])
def kill_process_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    # get the pid from the message text
    try:
        pid = int(message.text.split(' ', 1)[1])
    except IndexError:
        bot.reply_to(message, "Hata: Lütfen bir pid giriniz.")
        return
    except ValueError:
        bot.reply_to(message, "Hata: Lütfen geçerli bir pid giriniz.")
        return
    # kill the process
    try:
        # find the process from the pid
        global active_process
        for key, value in active_process.items():
            for key2, value2 in value.items():
                for process in value2:
                    if(process.pid == pid):
                        kill_process_tree(process)
                        bot.send_message(key, f'{key2} işlemi kapatıldı.')
                        #bot.send_message(message.chat.id, f'Process with pid {pid} killed.')
                        return
    except Exception as e:
        bot.send_message(message.chat.id, f'Hata: {e}')
                
## selfie
@bot.message_handler(commands=['selfie'])
def selfie_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    bot.send_message(message.chat.id, "Fotoğraf çekiliyor...\nLütfen bekleyin.")
    # call the selfie
    python_file = os.path.join(os.getcwd(), 'selfie', 'take_picture.py')
    arguments = [os.path.join(os.getcwd(), 'selfie', f'{message.chat.id}.jpg')]
    
    process_handler(['python', python_file] + arguments, True, 'selfie', message.chat.id)
    
    # send the photo
    bot.send_photo(message.chat.id, photo = open(arguments[0], 'rb'))
    
    # remove the photo
    os.remove(arguments[0])
    
## instagram - for now only for personal use
@bot.message_handler(commands=['instagram'])
def instagram_handler(message):
    global usernames, token, instagram_command_flags
    if not access_control(message.chat.id, admin=True):
        return
    # credentials folder
    credentials_folder = os.path.join(os.getcwd(), 'credentials', 'instagram')
    # list all the folders
    folders = [folder for folder in os.listdir(credentials_folder) if os.path.isdir(os.path.join(credentials_folder, folder))]
    # create a keyboard
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    # add the folders to the keyboard
    for folder in folders:
        button = types.InlineKeyboardButton(folder, callback_data=folder)
        keyboard.add(button)
    add_button = types.InlineKeyboardButton("Yeni Kullanıcı Ekle  \U0001F64B", callback_data='add_account')
    keyboard.add(add_button)
    # send the message
    bot.send_message(message.chat.id, "Lütfen bir kullanıcı seçin veya yeni bir kullanıcı ekleyin (Giriş yapılan hesabı güncellemek için yeni bir kullanıcı ekleyebilirsiniz, bu seçenek varolan hesabı overwrite eder.).", reply_markup=keyboard)
    
    @bot.callback_query_handler(func=lambda call: call.data in folders)
    def instagram_user(call):
        # delete the message
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # send the message
        options = types.InlineKeyboardMarkup(row_width=2)
        upload_reel_button = types.InlineKeyboardButton("Reel Yükle  \U0001F4F7", callback_data='upload_reel')
        download_reel_button = types.InlineKeyboardButton("Reel İndir  \U0001F4E5", callback_data='download_reel')
        follow_button = types.InlineKeyboardButton("Takip Et  \U0001F4E5", callback_data='follow')
        unfollow_button = types.InlineKeyboardButton("Takipten Çık  \U0001F4E5", callback_data='unfollow')
        options.add(upload_reel_button, download_reel_button, follow_button, unfollow_button)
        bot.send_message(call.message.chat.id, f'{call.data} kullanıcısı ile işlem yapılacak.', reply_markup=options)
        usernames[str(call.message.chat.id)] = call.data
        
        @bot.callback_query_handler(func=lambda call: call.data == 'upload_reel')
        def upload_reel(call):
            # delete the message
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Lütfen bekleyin.")

            # call the instagram
            python_file = os.path.join(os.getcwd(), 'instagram', 'instagram.py')
            
            arguments = [
                "--mode", "upload_reel",
                "--username", usernames[str(call.message.chat.id)],
                "--chat_id", str(call.message.chat.id),
                "--token", token,
                "--directory", os.path.join(os.getcwd(), 'credentials', 'instagram'),
            ]
            
            process_handler(['python', python_file] + arguments, False, 'instagram', call.message.chat.id)
            
        @bot.callback_query_handler(func=lambda call: call.data == 'download_reel')
        def download_reel(call):
            # delete the message
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Lütfen bekleyin.")
            
            download_options = types.InlineKeyboardMarkup(row_width=2)
            hashtag_top_button = types.InlineKeyboardButton("Hashtag's Top Reels  \U0001F4F7", callback_data='hashtag_top')
            hashtag_recent_button = types.InlineKeyboardButton("Hashtag's Recent Reels  \U0001F4E5", callback_data='hashtag_new')
            user_button = types.InlineKeyboardButton("User's Reel  \U0001F4E5", callback_data='user')
            download_options.add(hashtag_top_button, hashtag_recent_button, user_button)
            bot.send_message(call.message.chat.id, "İndirme seçeneklerinden birini seçiniz.", reply_markup=download_options)
            
            @bot.callback_query_handler(func=lambda call: (call.data).split('_')[0] == 'hashtag')
            def hashtag_top(call):
                # delete the message
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, "Lütfen hashtag ismini yazınız. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
                instagram_command_flags[str(call.message.chat.id)] = call.data
                bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_instagram_download_info)
            
            @bot.callback_query_handler(func=lambda call: call.data == 'user')
            def user_reel(call):
                # delete the message
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, "Lütfen kullanıcı adını yazınız. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
                instagram_command_flags[str(call.message.chat.id)] = call.data
                bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_instagram_download_info)

                    
        @bot.callback_query_handler(func=lambda call: call.data == 'follow')
        def follow(call):
            # delete the message
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
            follow_options = types.InlineKeyboardMarkup(row_width=2)
            follow_hashtag_button = types.InlineKeyboardButton("Hashtag Gönderilerini Beğenenleri Takip Et  \U0001F4F7", callback_data='follow_hashtag_likers')
            follow_user_followers_button = types.InlineKeyboardButton("Kullanıcı Takipçilerini Takip Et  \U0001F4E5", callback_data='follow_user_followers')
            follow_user_likers_button = types.InlineKeyboardButton("Kullanıcı Gönderilerini Beğenenleri Takip Et  \U0001F4E5", callback_data='follow_user_likers')
            follow_options.add(follow_hashtag_button, follow_user_followers_button, follow_user_likers_button)
            bot.send_message(call.message.chat.id, "Takip seçeneklerinden birini seçiniz.", reply_markup=follow_options)
            
            @bot.callback_query_handler(func=lambda call: call.data == 'follow_hashtag_likers')
            def follow_hashtag_likers(call):
                # delete the message
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, "Lütfen hashtag ismini yazınız. İşlemi iptal etmek için 'cancel' yazabilirsiniz")
                instagram_command_flags[str(call.message.chat.id)] = 'hashtag-likers-top: '
                bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_instagram_follow_info)
                    
            @bot.callback_query_handler(func=lambda call: call.data == 'follow_user_followers')
            def follow_user_followers(call):
                # delete the message
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, "Lütfen kullanıcı adını yazınız. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
                instagram_command_flags[str(call.message.chat.id)] = 'blogger-followers: '
                bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_instagram_follow_info)
                    
            @bot.callback_query_handler(func=lambda call: call.data == 'follow_user_likers')
            def follow_user_likers(call):
                # delete the message
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_message(call.message.chat.id, "Lütfen kullanıcı adını yazınız. İşlemi iptal etmek için 'cancel' yazabilirsiniz.")
                instagram_command_flags[str(call.message.chat.id)] = 'blogger-post-likers: '
                bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_instagram_follow_info)
                    
        @bot.callback_query_handler(func=lambda call: call.data == 'unfollow')
        def unfollow(call):
            # delete the message
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(message.chat.id, f"İşlem başlatılıyor. 20-30 kişi takipten çıkılacak.")
                    
            yaml_file, site_path = gramaddict_yaml_file(message.chat.id)
            # edit the yaml file
            configure_yaml_file(yaml_file, f'unfollow-any: 20-30')
            
            # run the bot
            arguments = [
                'gramaddict', 'run',
                "--config", f'accounts/{usernames[str(message.chat.id)]}/config.yml',
            ]
            
            process_handler(arguments, False, 'gramaddict', message.chat.id, cwd=f'{site_path}/GramAddict')
            
            
    @bot.callback_query_handler(func=lambda call: call.data == 'add_account')
    def add_user(call):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Kullanıcı adınızı giriniz: (işlemi iptal etmek için 'cancel' yazabilirsiniz.)")
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, get_instagram_username)
                
## hostname -- eduroam uses dynamic ip, after rebooting the pi, the ip may change
@bot.message_handler(commands=['hostname'])
def hostname_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    output = (os.popen('hostname -I').read()).strip().split(" ")
    for out in output:
        bot.send_message(message.chat.id, out)
    
## exit
@bot.message_handler(commands=['exit'])
def exit_handler(message):
    if not access_control(message.chat.id, admin=True):
        return
    # shutting down completely
    bot.send_message(message.chat.id, "Raspberry kapatılıyor...")
    # Inform the owner that the program is shutting down
    global owner_id
    global active_process
    
    bot.send_message(owner_id, "Aktif işlemler kapatılıyor.")
    # kill all active processes
    if(len(active_process) > 0):
        for key, value in active_process.items():
            if(len(value) > 0):
                for key2, value2 in value.items():
                    for process in value2:
                        try:
                            bot.send_message(key, f'[@atakan](tg://user?id={owner_id}) reboot attığı için {key2} işlemi kapatılıyor. Görüşürüz...', parse_mode='Markdown')
                            if key2 in ['yht', 'spor']:
                                bot.send_message(key, f'Merak etme raspberry tekrar açıldığında işlemi devam ettirmeye çalışacak. Sana haber vereceğim.')
                            kill_process_tree(process)
                        except Exception as e:
                            print(f'Process with pid {process.pid} thrown an exception. Could not kill the process. {e}', flush=True)
    dump_active_process()
    # reboot
    os.system('sudo reboot')

# Start the bot
bot.polling()
