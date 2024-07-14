"""
Used to check the availability of YHT tickets between two stations at a specific date and time.
The script sends a message to a telegram chat if there is a change in the number of available seats.
The script will keep running until it is stopped manually.
Usage: python yht_v2.py <botToken> <chatId> <departure> <arrival> <date> <hour>
Example: python yht_v2.py 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11 123456789 Ankara Istanbul 01.01.2022 12:00
"""
import sys
import time
import json
import locale
import datetime
import requests
from inputimeout import inputimeout, TimeoutOccurred

SPECIAL_CHARS = [
  '\\',
  '-',
  '=',
  '|',
  '{',
  '}',
  '.',
  '!',
  '(',
  ')',
  '[',
    ']',
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
hold_the_seat = True
empty_economy = -1
empty_business = -1
timeout = 30

temp_usr_hour = user_hour

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
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
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

def check_wagon(wagon_num: int, train_session_id: int, departure_station_id: int, arrival_station_id: int):
    global user_departure, user_arrival
    
    wagon_info_url = "https://api-yebsp.tcddtasimacilik.gov.tr/vagon/vagonHaritasindanYerSecimi"
    wagon_info_payload = {
    "kanalKodu": "3",
    "dil": 0,
    "seferBaslikId": train_session_id,
    "vagonSiraNo": wagon_num,
    "binisIst": user_departure,
    "InisIst": user_arrival
    } 
    
    wagon_info_response = requests.post(wagon_info_url, headers=headers, json=wagon_info_payload).json()
        
    all_seats = wagon_info_response['vagonHaritasiIcerikDVO']['koltukDurumlari']
    
    # filter the seats to get only the empty ones which means 'durum' parameter is 0
    empty_seats = [x['koltukNo'] for x in all_seats if x['durum'] == 0]
    
    if len(empty_seats) == 0:
        return
    
    seat_details = wagon_info_response['vagonHaritasiIcerikDVO']['vagonYerlesim']
    
    seat_details_economy = [x for x in seat_details if x['ekHizmetId'] == None and x['koltukNo'] in empty_seats]
    
    for seat in seat_details_economy:
        if seat['koltukNo'] in empty_seats and (seat['koltukNo'])[-1] != 'h':
            # hold the seat
            kl_check_url = "https://api-yebsp.tcddtasimacilik.gov.tr/koltuk/klCheck"
            kl_check_payload = {
                "kanalKodu": "3",
                "dil": 0,
                "koltukNo": seat['koltukNo'],
                "seciliVagonSiraNo": wagon_num,
                "seferId": train_session_id,
            }
            
            kl_check_response = requests.post(kl_check_url, headers=headers, json=kl_check_payload).json()
            if kl_check_response['cevapBilgileri']['cevapKodu'] == "000":
                kl_sec_url = "https://api-yebsp.tcddtasimacilik.gov.tr/koltuk/klSec"
                kl_sec_payload = {
                    "kanalKodu": "3",
                    "dil": 0,
                    "koltukNo": seat['koltukNo'],
                    "vagonSiraNo": wagon_num,
                    "seferId": train_session_id,
                    "binisIst": departure_station_id,
                    "inisIst": arrival_station_id,
                    "cinsiyet": 'E',
                    "huawei": False,
                    "dakika": 10
                }
                kl_sec_response = requests.post(kl_sec_url, headers=headers, json=kl_sec_payload).json()
                if kl_check_response['cevapBilgileri']['cevapKodu'] == "000":
                    # inform the user that the seat is held
                    sendTelegramMessage(f'{user_departure} - {user_arrival} arası {user_date} {temp_usr_hour} tarihli trende *{wagon_num}. vagonda {seat["koltukNo"]}* numaralı koltuk tutuldu.')
                    sendTelegramMessage(f'10 dakika süreniz var. Eğer 10 dakika içinde /yhtrelease komutunu kullanmazsanız koltuk bırakılacak ve program kapatılacak.')
                    try:
                        user_input = inputimeout(prompt='Please enter something: ', timeout=600)  # 600 seconds = 10 minutes
                    except TimeoutOccurred:
                        user_input = None
                    
                    if user_input is not None:
                        # release the seat
                        kl_birak_url = "https://api-yebsp.tcddtasimacilik.gov.tr/koltuk/klBirak"
                        kl_birak_payload = {
                            "kanalKodu": "3",
                            "dil": 0,
                            "koltukNo": seat['koltukNo'],
                            "vagonSiraNo": wagon_num,
                            "seferBaslikId": train_session_id,
                        }
                        kl_birak_response = requests.post(kl_birak_url, headers=headers, json=kl_birak_payload).json()
                        if kl_birak_response['cevapBilgileri']['cevapKodu'] == "000":
                            sendTelegramMessage(f'Koltuk bırakıldı. Program kapatılıyor.')
                            sys.exit(1)
                            
                        else:
                            sendTelegramMessage(f'Koltuk bırakılırken bir hata oluştu. Program kapatılıyor.')
                            sys.exit(1)
                        
                    else:
                        sendTelegramMessage(f'10 dakika süreniz doldu. Koltuk bırakılıyor. Program kapatılıyor.')
                        sys.exit(1)
    
    
    # Get business seats for future use
    # seat_details_business = [x for x in seat_details if x['ekHizmetId'] != None and x['koltukNo'] in empty_seats]
    
    
    
    

def wagon_info(train_session_id: int, departure_station_id: int, arrival_station_id: int):
    url_hold = "https://api-yebsp.tcddtasimacilik.gov.tr/vagon/vagonBosYerSorgula"
    
    payload_hold = {
        "kanalKodu": "3",
        "dil": 0,
        "seferBaslikId": train_session_id,  
        "binisIstId": departure_station_id,
        "inisIstId": arrival_station_id
    }
    
    response_hold = requests.post(url_hold, headers=headers, json=payload_hold).json()
    
    wagon_list = response_hold['vagonBosYerList']
    
    # reverse the list to check the wagons from the last one
    wagon_list.reverse()
    
    for i in wagon_list:
        if i['bosYer'] != 0:
            print(f'Checking wagon {i["vagonSiraNo"]}')
            check_wagon(i['vagonSiraNo'], train_session_id, departure_station_id, arrival_station_id)
            

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
            # store this variable to get detailed seat info
            train_session_id = train['seferId']
            
            hour_check = True
            for i in train["vagonTipleriBosYerUcret"]:
                temp = i['vagonListesi'][0]
                
                # store the station ids to get detailed seat info
                departure_station_id = temp['baslangicIstasyonId']
                arrival_station_id = temp['bitisIstasyonId']
                
                empty_seat_count = i["kalanSayi"]- i["kalanEngelliKoltukSayisi"]
                if i["ubsKodu"] == 2:
                    if empty_economy != empty_seat_count:
                        formatted_date_str = date_obj.strftime("%d %B %H:%M")
                        temp_str = f'*{empty_seat_count}* adet *boş* yer bulunmaktadır.'
                        if empty_seat_count <= 0:
                            empty_seat_count = 0
                            temp_str = 'boş yer *bulunmamaktadır*.'
                        elif hold_the_seat:
                            wagon_info(train_session_id, departure_station_id, arrival_station_id)
                                    
                        sendTelegramMessage(f'{user_departure} - {user_arrival} arası {formatted_date_str} tarihli trende *Ekonomi* vagonunda {temp_str}')
                        empty_economy = empty_seat_count

                elif i["ubsKodu"] == 1:
                    if empty_business != empty_seat_count:
                        formatted_date_str = date_obj.strftime("%d %B %H:%M")
                        temp_str = f'*{empty_seat_count}* adet *boş* yer bulunmaktadır.'
                        if empty_seat_count <= 0:
                            empty_seat_count = 0
                            temp_str = 'boş yer *bulunmamaktadır*.'        
                        sendTelegramMessage(f'{user_departure} - {user_arrival} arası {formatted_date_str} tarihli trende *Business* vagonunda {temp_str}')
                        empty_business = empty_seat_count
    
    if not hour_check:
        sendTelegramMessage(f'{user_departure} - {user_arrival} arası için {user_date} tarihinde {user_hour[0]}:{user_hour[1]} saatlerinde tren bulunamadı. Program kapatılıyor.')
        sys.exit(1)
        
err_count = 0

while True:
    try:
        check_yht()
        time.sleep(timeout)
        if timeout > 100:
            timeout = 30
        err_count  = 0
    except Exception as e:
        # Due to the nature of the program, it is expected to have some errors.
        # However, if the error count exceeds 10, the program will be terminated.
        timeout *= 1.5
        err_count += 1
        if err_count >= 10:
            sendTelegramMessage(f'Programda bir hata oluştu: {e}. İşlem kapatılıyor.')
            sys.exit(1)