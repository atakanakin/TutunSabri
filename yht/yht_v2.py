import sys
import time
import json
import locale
import datetime
import requests
SPECIAL_CHARS = [
  '\\',
  '-',
  '=',
  '|',
  '{',
  '}',
  '.',
  '!'
]

def replace_special_chars(text):
  for char in SPECIAL_CHARS:
    text = text.replace(char, f'\\{char}')
  return text

#read system arguments
botToken = sys.argv[1]
chatId = sys.argv[2]
user_departure = sys.argv[3]
user_arrival = sys.argv[4]
user_date = sys.argv[5]
user_hour = sys.argv[6]
empty_economy = -1
empty_business = -1
timeout = 30

user_hour = [int(x) for x in user_hour.split(":")]
locale.setlocale(locale.LC_TIME, 'en_US.utf8')
user_date_obj = datetime.datetime.strptime(user_date, "%d.%m.%Y")
final_user_date = user_date_obj.strftime("%b %d, %Y 00:00:00 AM")


def sendTelegramMessage(message):
    global botToken, chatId
    # send message to telegram but parse the message to be in markdown format
    final_message = replace_special_chars(message)
    res = requests.get(f'https://api.telegram.org/bot{botToken}/sendMessage?chat_id={chatId}&parse_mode=MarkdownV2&text={final_message}')
    
    if res.status_code != 200:
        print(f"Error sending message to telegram: {res.text}")

# Define the URL for the API endpoint
url = "https://api-yebsp.tcddtasimacilik.gov.tr/sefer/seferSorgula"

# Define the headers for the request
headers = {
    "Host": "api-yebsp.tcddtasimacilik.gov.tr",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Authorization": "Basic ZGl0cmF2b3llYnNwOmRpdHJhMzQhdm8u",
    "Content-Type": "application/json",
    "Origin": "https://bilet.tcdd.gov.tr",
    "Connection": "keep-alive",
    "Referer": "https://bilet.tcdd.gov.tr/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
    "Priority": "u=1"
}

# Define the payload for the request
payload = {
    "kanalKodu": 3,
    "dil": 0,
    "seferSorgulamaKriterWSDVO": {
        "satisKanali": 3,
        "binisIstasyonu": user_departure,
        "binisIstasyonu_isHaritaGosterimi": False,
        "inisIstasyonu": user_arrival,
        "inisIstasyonu_isHaritaGosterimi": False,
        "seyahatTuru": 1,
        "gidisTarih": final_user_date,
        "bolgeselGelsin": False,
        "islemTipi": 0,
        "yolcuSayisi": 1,
        "aktarmalarGelsin": True,
    }
}

def check_yht():
    global headers, payload, url, empty_economy, empty_business, user_hour, user_departure, user_arrival
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    trains = response.json()
    if trains["seferSorgulamaSonucList"] == None:
        sendTelegramMessage(f'{user_departure} - {user_arrival} arası için {user_date} tarihinde tren bulunamadı.')
        sys.exit(1)
        
    hour_check = False
        
    for train in trains["seferSorgulamaSonucList"]:
        locale.setlocale(locale.LC_TIME, 'en_US.utf8')
        date_obj = datetime.datetime.strptime(train["binisTarih"], "%b %d, %Y %I:%M:%S %p")
        locale.setlocale(locale.LC_TIME, 'tr_TR.utf8')
        
        if date_obj.hour == user_hour[0] and date_obj.minute == user_hour[1]:
            hour_check = True
            for i in train["vagonTipleriBosYerUcret"]:
                if i["ubsKodu"] == 2:
                    if empty_economy != i["kalanSayi"]:
                        formatted_date_str = date_obj.strftime("%d %B %H:%M")
                        temp_str = f'*{i["kalanSayi"]}* adet *boş* yer bulunmaktadır.'
                        if i["kalanSayi"] == 0:
                            temp_str = 'boş yer *bulunmamaktadır*.'        
                        sendTelegramMessage(f'{user_departure} - {user_arrival} arası {formatted_date_str} tarihli trende *Ekonomi* vagonunda {temp_str}')
                        empty_economy = i["kalanSayi"] 

                elif i["ubsKodu"] == 1:
                    if empty_business != i["kalanSayi"]:
                        formatted_date_str = date_obj.strftime("%d %B %H:%M")
                        temp_str = f'*{i["kalanSayi"]}* adet *boş* yer bulunmaktadır.'
                        if i["kalanSayi"] == 0:
                            temp_str = 'boş yer *bulunmamaktadır*.'        
                        sendTelegramMessage(f'{user_departure} - {user_arrival} arası {formatted_date_str} tarihli trende *Business* vagonunda {temp_str}')
                        empty_business = i["kalanSayi"]
    
    if not hour_check:
        sendTelegramMessage(f'{user_departure} - {user_arrival} arası için {user_date} tarihinde {user_hour[0]}:{user_hour[1]} saatlerinde tren bulunamadı. Program kapatılıyor.')
        sys.exit(1)

while True:
    try:
        check_yht()
        time.sleep(timeout)
    except Exception as e:
        sendTelegramMessage(f'Programda bir hata oluştu: {e}')
        sys.exit(1)
