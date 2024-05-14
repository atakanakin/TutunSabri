import os
import sys
import time
import json
import signal
import requests
import subprocess

process = None

def signal_handler(signum, frame):
    global process
    process.send_signal(signal.SIGINT)
    sys.exit(0)
    
signal.signal(signal.SIGINT, signal_handler)
    

def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {
        'chat_id': owner_id,
        'text': message
    }
    response = requests.post(url, data=data)
    return response.json()

with open('bot_config.json', 'r') as f:
    bot_config = json.load(f)
    
owner_id = bot_config['owner_id']
bot_token = bot_config['bot_token']

python_file = os.path.join(os.getcwd(), 'main.py')

send_telegram_message('Tütün Sabri başlatılıyor...')

while True:
    time.sleep(5)
    try:
        # Run the python file
        process = subprocess.Popen(['python', python_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # wait for the process to complete
        stdout, stderr = process.communicate()
        # get the exit code
        exit_code = process.returncode
        if(exit_code != 0):
            stderr_str = stderr.decode('utf-8')
            send_telegram_message(f'Program hata ile karşılaştı: {stderr_str}')
            print(f'Exit code: {exit_code}: {stderr_str}')
        # decode stdout
        stdout_str = stdout.decode('utf-8')
        output = stdout_str.strip().split('\n')
        print(f'stdout: {output}')

    except Exception as e:
        send_telegram_message(f'Eyvah! : {e}')
        print(f'Eyvah: {e}')
        continue