import os
import sys
import json
import psutil
import signal
import telebot
import subprocess
from telebot import types
from dropbox_helper import DropBoxUpload

# global variables
active_process = {}
youtube_urls = {}

# read the bot token from the json file
with open('bot_config.json') as f:
    data = json.load(f)
    token = data['bot_token']
    dropbox_token = data['dropbox_token']
    owner_id = data['owner_id']
    
# create a dropbox upload object
dbu = DropBoxUpload(dropbox_token)

# create a bot object
bot = telebot.TeleBot(token)
    
def signal_handler(sig, frame):
    # Inform the owner that the program is shutting down
    global owner_id
    global bot
    global active_process
    #bot.send_message(owner_id, "Program kapatılıyor.") TODO: Uncomment this line
    # kill all active processes
    print(active_process)
    if(len(active_process) > 0):
        for key, value in active_process.items():
            if(len(value) > 0):
                for key2, value2 in value.items():
                    for process in value2:
                        try:
                            bot.send_message(key, f'{key2} işlemi kapatılıyor. Görüşürüz...')
                            kill_process_tree(process)
                        except Exception as e:
                            print(f'Process with pid {process.pid} thrown an exception. Could not kill the process. {e}')
                            
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# some helper functions

def kill_process_tree(process):
    # I wish I lived in a world where I could just call process.kill() and be done with it
    parent = psutil.Process(process.pid)
    for child in parent.children(recursive=True):
        child.kill()
        
    process.kill()    
    print(f'Process with PID {process.pid} and its child processes killed.')

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
            bot.send_message(message.chat.id, f'Ses dosyası gönderilemiyor.')
            bot.send_message(message.chat.id, f'Ses dosyasını dropboxa yüklüyorum...')
            try:
                audUrl = dbu.UpLoadFile('',output)
                bot.send_message(message.chat.id, text= f'<a href="{audUrl}">Ses dosyasını indir</a>', parse_mode='HTML')
            except Exception as dropboxError:
                bot.send_message(message.chat.id, f'Dropboxa yüklenirken bir hata oluştu.')
                
    elif(type == 'video'):
        try:
            bot.send_video(message.chat.id, video = file, supports_streaming=True, width=1920, height=1080)
        except Exception as e:
            bot.send_message(message.chat.id, f'Video dosyası gönderilemiyor.')
            bot.send_message(message.chat.id, f'Videoyu dropboxa yüklüyorum...')
            vidUrl = dbu.UpLoadFile('',output)
            bot.send_message(message.chat.id, text= f'<a href="{vidUrl}">Videoyu indir</a>', parse_mode='HTML')
            
    file.close()
    os.remove(output)
    
## create and run a process
def process_handler(executable: list, wait_to_finish: bool, process_name: str, chat_id):
    process = subprocess.Popen(executable,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        
    if(wait_to_finish):
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
        return (True, output[-1].strip())
    else:
        global active_process
        if chat_id not in active_process:
            active_process[chat_id] = {}
        # check if active process have key with chat id
        if chat_id in active_process and process_name in active_process[chat_id]:
            active_process[chat_id][process_name].append(process)
        else:
            active_process[chat_id][process_name] = [process]
            
        print(active_process)
            
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
    # Extract the YouTube URL from the message text
    try:
        youtube_url = message.text.split(' ', 1)[1]
        youtube_urls[message.chat.id] = youtube_url
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
        youtube_url = youtube_urls[call.message.chat.id]
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
        global youtube_urls
        youtube_url = youtube_urls[call.message.chat.id]
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # ask for the start and end time
        bot.send_message(call.message.chat.id, "Klip başlangıç zamanını giriniz: (Örnek: 00:00)")
        hold = [True, True]
        @bot.message_handler(func=lambda message: hold[0])
        def get_start_time(message):
            start_time = message.text
            hold[0] = False
            bot.send_message(message.chat.id, "Klip bitiş zamanını giriniz: (Örnek: 01:30)")
            @bot.message_handler(func=lambda message: hold[1])
            def get_end_time(message):
                end_time = message.text
                hold[1] = False
                bot.send_message(message.chat.id, "Klip indiriliyor...\nLütfen bekleyin.")
                # call the downloader
                executable_file = os.path.join(os.getcwd(), 'youtube', 'executable', 'youtube')
                arguments = [youtube_url, os.getcwd(), 'clip', start_time, end_time]
                
                out = process_handler([executable_file] + arguments, True, 'youtube', message.chat.id)
                
                if(not out[0]):
                    bot.send_message(message.chat.id, f'Bir sorun oluştu: {out[1]}')
                    return
                
                file_handler(message, out[1], type='video')
                return

    @bot.callback_query_handler(func=lambda call: call.data == 'only_audio')
    def only_audio(call):
        global youtube_urls
        youtube_url = youtube_urls[call.message.chat.id]
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Ses indiriliyor...\nLütfen bekleyin.")
        # call the downloader
        executable_file = os.path.join(os.getcwd(), 'youtube', 'executable', 'youtube')
        arguments = [youtube_url , os.getcwd(), 'audio']
        
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

## twitter
@bot.message_handler(commands=['twitter'])
def twitter_handler(message):
    # if user has credentials
    credentials = None
    user_credential_path = os.path.join(os.getcwd(), 'credentials', 'twitter', f'{message.chat.id}.json')
    if(os.path.exists(user_credential_path)):
        with open(user_credential_path) as f:
            credentials = json.load(f)
        bot.send_message(message.chat.id, f'{credentials["username"]} kullanıcısı ile giriş yapıldı.')
    else:
        # ask for credentials
        bot.send_message(message.chat.id, "Twitter kullanıcı adınızı giriniz:")
        hold = [True, True]
        @bot.message_handler(func=lambda message: hold[0])
        def get_twitter_username(message):
            twitter_username = message.text
            hold[0] = False
            bot.send_message(message.chat.id, "Twitter şifrenizi giriniz:")
            @bot.message_handler(func=lambda message: hold[1])
            def get_twitter_password(message):
                hold[1] = False
                twitter_password = message.text
                credentials = {
                    'username': twitter_username,
                    'password': twitter_password
                }
                with open(user_credential_path, 'w') as f:
                    json.dump(credentials, f)
    bot.send_message(message.chat.id, "Bu işlem biraz zaman alabilir.\nLütfen bekleyin...")

## YHT Train
@bot.message_handler(commands=['yht'])
def yht_handler(message):
    global active_process
    # ask for 2 cities
    info = None
    bot.send_message(message.chat.id, "Kalkış istasyonunu giriniz (Örnek: Ankara Gar):")
    hold = [True, True, True, True]
    @bot.message_handler(func=lambda message: hold[0])
    def get_departure_station(message):
        departure_station = message.text
        hold[0] = False
        bot.send_message(message.chat.id, "Varış istasyonunu giriniz: (Örnek: Konya (Selçuklu YHT))")
        @bot.message_handler(func=lambda message: hold[1])
        def get_arrival_station(message):
            arrival_station = message.text
            hold[1] = False
            bot.send_message(message.chat.id, "Tarih bilgisini giriniz: (Örnek: 13.04.2024)")
            @bot.message_handler(func=lambda message: hold[2])
            def get_date(message):
                hold[2] = False
                date = message.text
                bot.send_message(message.chat.id, "Saat bilgisini giriniz: (Örnek: 15:33)")
                @bot.message_handler(func=lambda message: hold[3])
                def get_time(message):
                    hold[3] = False
                    time = message.text
                    info = {
                        'departure_station': departure_station,
                        'arrival_station': arrival_station,
                        'date': date,
                        'time': time
                    }
                    bot.send_message(message.chat.id, f'{info["departure_station"]} - {info["arrival_station"]} arası {info["date"]} - {info["time"]} tarihindeki tren seferleri için boş koltuk aranıyor...')

                    # call the train search
                    python_file = os.path.join(os.getcwd(), 'yht', 'yht_check.py')
                    arguments = [token, str(message.chat.id), info['departure_station'], info['arrival_station'], info['date'], info['time']]
                    
                    process_handler(['python', python_file] + arguments, False, 'yht', message.chat.id)

## cancel the yht search
@bot.message_handler(commands=['yhtcancel'])
def yht_cancel_handler(message):
    global active_process
    if message.chat.id in active_process and 'yht' in active_process[message.chat.id]:
        for process in active_process[message.chat.id]['yht']:
            # kill the process with the pid
            try:
               kill_process_tree(process)
            except ProcessLookupError as e:
                print('Look up error?')
                print(e)
            except Exception as e:
                print(e)
            active_process[message.chat.id]['yht'].remove(process)
        bot.send_message(message.chat.id, "Tren seferi arama işlemi iptal edildi.")
    else:
        bot.send_message(message.chat.id, "Aktif bir tren seferi arama işlemi bulunamadı.")

        user_jobs = create_process_list_message(message.chat.id)
        
        if(len(user_jobs) > 0):
            bot.send_message(message.chat.id, user_jobs)
            
    print(active_process)
                         

## text to speech
@bot.message_handler(commands=['tts'])
def tts_handler(message):
    # Extract the text from the message text
    try:
        text = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Hata: Lütfen bir metin giriniz.")
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
    # check if the user has credentials
    user_credential_path = os.path.join(os.getcwd(), 'credentials', 'rezmetu', f'{message.chat.id}.json')
    if(os.path.exists(user_credential_path)):
        f = open(user_credential_path, 'r')
        config = json.load(f)
        f.close()
        bot.send_message(message.chat.id, f'{config["username"]} kullanıcısı ile işlem yapılacak.')
    else:
        # ask for credentials
        bot.send_message(message.chat.id, "Rezervasyon yapmak için lütfen kullanıcı adınızı giriniz: (Örnek: e123456)")
        hold = [True, True]
        @bot.message_handler(func=lambda message: hold[0])
        def get_username(message):
            username = message.text
            hold[0] = False
            bot.send_message(message.chat.id, "Şifrenizi giriniz:")
            @bot.message_handler(func=lambda message: hold[1])
            def get_password(message):
                password = message.text
                hold[1] = False
                credentials = {
                    'username': username,
                    'password': password
                }
                with open(user_credential_path, 'w') as f:
                    json.dump(credentials, f)
    
    bot.send_message(message.chat.id, "Lütfen seans saat bilgisini giriniz: (Örnek: 19:35 - 20:55)")
    desiredTime = None
    timeHold = True
    @bot.message_handler(func=lambda message: timeHold)
    def get_time(message):
        global desiredTime
        desiredTime = message.text
        timeHold = False
        bot.send_message(message.chat.id, "Program başlatılıyor...\nLütfen bekleyin.")
        # call the reservation
        python_file = os.path.join(os.getcwd(), 'spor', 'main.py')
        arguments = [str(message.chat.id), token, desiredTime]
        
        process_handler(['python', python_file] + arguments, False, 'spor', message.chat.id)
        

## cancel the spor reservation
@bot.message_handler(commands=['sporcancel'])
def spor_cancel_handler(message):
    global active_process
    if message.chat.id in active_process and 'spor' in active_process[message.chat.id]:
        for process in active_process[message.chat.id]['spor']:
            # kill the process with the pid
            try:
               kill_process_tree(process)
            except ProcessLookupError as e:
                print('Look up error?')
                print(e)
            except Exception as e:
                print(e)
            active_process[message.chat.id]['spor'].remove(process)
        bot.send_message(message.chat.id, "Spor salonu rezervasyon işlemi iptal edildi.")
    else:
        bot.send_message(message.chat.id, "Aktif bir spor salonu rezervasyon işlemi bulunamadı.")
        
        user_jobs = create_process_list_message(message.chat.id)
        
        if(len(user_jobs) > 0):
            bot.send_message(message.chat.id, user_jobs)
            
    print(active_process)
    
    
    
## pedro
@bot.message_handler(commands=['pedro'])
def pedro_handler(message):
    bot.send_video(message.chat.id, video = 'BAACAgQAAxkDAAIEI2YkHfk_t10R31SISqYxWk27VaDcAAJGEwACwmwgUZ6kBxvyfD_UNAQ', supports_streaming=True, width=1920, height=1080)

# Start the bot
bot.polling()
