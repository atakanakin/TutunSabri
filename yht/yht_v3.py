"""
Adapted from yht_v2.py to work with the new TCDD website.
A yell out to backend developer: Fuck you!
Used to check the availability of YHT tickets between two stations at a specific date and time.
The script sends a message to a telegram chat if there is a change in the number of available seats.
The script will keep running until it is stopped manually.
Usage: python yht_v3.py <botToken> <chatId> <departure> <arrival> <date> <hour>
Example: python yht_v3.py 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11 123456789 Ankara Istanbul 01.01.2022 12:00
"""
import re
import sys
import time
import requests
from datetime import datetime, timedelta
from station_helper import get_station_id
from inputimeout import inputimeout, TimeoutOccurred
from urllib.parse import quote

# read system arguments
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

# handle gmt+3 timezone
formatted_date = user_date.replace(".", "-")
full_date = f"{user_date} {user_hour}"
readable_date = datetime.strptime(full_date, "%d.%m.%Y %H:%M")
full_date = datetime.strptime(full_date, "%d.%m.%Y %H:%M")
full_date = full_date - timedelta(hours=3)
full_date = full_date.strftime("%Y-%m-%dT%H:%M:%S")

# handle departure and arrival stations
departure_id = get_station_id(user_departure)
arrival_id = get_station_id(user_arrival)

# global error counters
MAX_ERR_COUNT = 3
main_error_count = 0
train_request_error = 0
hour_check_flag = False
hour_check_error = 0

# Construct the URL and headers
base_url = "https://gise-api-prod-ytp.tcddtasimacilik.gov.tr/tms/"
base_headers = {
    "Accept": "application/json, text/plain, */*",
    "unit-id": "3895",
    "Authorization": ("eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0."
                      "eyJleHAiOjE3MjEzODQ0NzAsImlhdCI6MTcyMTM4NDQxMCwianRpIjoiYWFlNjVkNzgtNmRkZS00ZGY4LWEwZWYtYjRkNzZiYjZlODNjIiwiaXNzIjoiaHR0cDovL3l0cC1wcm9kLW1hc3RlcjEudGNkZHRhc2ltYWNpbGlrLmdvdi50cjo4MDgwL3JlYWxtcy9tYXN0ZXIiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiMDAzNDI3MmMtNTc2Yi00OTBlLWJhOTgtNTFkMzc1NWNhYjA3IiwidHlwIjoiQmVhcmVyIiwiYXpwIjoidG1zIiwic2Vzc2lvbl9zdGF0ZSI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImFjciI6IjEiLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy1tYXN0ZXIiLCJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJvcGVuaWQgZW1haWwgcHJvZmlsZSIsInNpZCI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoid2ViIiwiZ2l2ZW5fbmFtZSI6IiIsImZhbWlseV9uYW1lIjoiIn0.AIW_4Qws2wfwxyVg8dgHRT9jB3qNavob2C4mEQIQGl3urzW2jALPx-e51ZwHUb-TXB-X2RPHakonxKnWG6tDIP5aKhiidzXDcr6pDDoYU5DnQhMg1kywyOaMXsjLFjuYN5PAyGUMh6YSOVsg1PzNh-5GrJF44pS47JnB9zk03Pr08napjsZPoRB-5N4GQ49cnx7ePC82Y7YIc-gTew2baqKQPz9_v381Gbm2V38PZDH9KldlcWut7kqQYJFMJ7dkM_entPJn9lFk7R5h5j_06OlQEpWRMQTn9SQ1AYxxmZxBu5XYMKDkn4rzIIVCkdTPJNCt5PvjENjClKFeUA1DOg"),
    "Sec-Fetch-Site": "same-site",
    "Accept-Language": "tr",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Mode": "cors",
    "Content-Type": "application/json",
    "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty"
}

base_payload = {
    "searchRoutes": [
        {
            "departureStationId": departure_id,
            "arrivalStationId": arrival_id,
            "departureDate": f"{formatted_date} 00:00:00"
        }
    ],
    "passengerTypeCounts": [
        {
            "id": 0,
            "count": 1
        }
    ],
    "searchReservation": False
}

def replace_special_chars(text):
  for char in SPECIAL_CHARS:
    text = text.replace(char, f'\\{char}')
  return text

def sendTelegramMessage(message):
    global botToken, chatId
    # send message to telegram but parse the message to be in markdown format
    final_message = replace_special_chars(message)
    encoded_message = quote(final_message)
    res = requests.get(f'https://api.telegram.org/bot{botToken}/sendMessage?chat_id={chatId}&parse_mode=MarkdownV2&text={encoded_message}')
    
    if res.status_code != 200:
        print(f"Error sending message to telegram: {res.text}")

def user_info_message(count, type):
    global user_departure, user_arrival, readable_date
    if count == 0:
        return f'{user_departure} - {user_arrival} arası {readable_date} tarihli trende *{type}* vagonunda boş koltuk *bulunmamaktadır*.' 
    return f'{user_departure} - {user_arrival} arası {readable_date} tarihli trende *{type}* vagonunda *{count}* adet boş koltuk bulunmaktadır.'

def release_seat(train_id, allocation_id, seat_number):
    global base_url, base_headers
    release_payload = {
        "trainCarId": train_id,
        "allocationId": allocation_id,
        "seatNumber": seat_number
    }

    response = requests.post(base_url+"inventory/release-seat?environment=dev&userId=1", headers=base_headers, json=release_payload)
    
    if response.status_code == 200:
        sendTelegramMessage(f'Koltuk bırakıldı. Program kapatılıyor.')
        sys.exit(0)
    else:
        sendTelegramMessage(f'Koltuk bırakılırken bir hata oluştu. Program kapatılıyor.')
        sys.exit(1)

def hold_seat(train_id):
    global base_url, base_headers, departure_id, arrival_id, user_departure, user_arrival, readable_date
    # tcdd backend is shitty, idk whoose idea was this but to find the empty seat we need to extract allocated seats from whole seats
    seat_pattern = r"^\d{1,2}[ABCD]$"
    # first get wagon list
    seat_map_payload = {
        "fromStationId": departure_id,
        "toStationId": arrival_id,
        "trainId": train_id,
        "legIndex": 0
    }
    response = requests.post(base_url+"seat-maps/load-by-train-id?environment=dev&userId=1", headers=base_headers, json=seat_map_payload)
    data = response.json()

    wagon_list = data["seatMaps"]
    empty_count_list = [x["availableSeatCount"] for x in wagon_list]
    wagon_indices = [x for x, value in enumerate(empty_count_list) if value != 0]
    # reverse the list to get the last wagon first
    wagon_indices.reverse()
    for wagon_index in wagon_indices:
        wagon = wagon_list[wagon_index]
        all_seats = [x["seatNumber"] for x in wagon["seatMapTemplate"]["seatMaps"] if re.match(seat_pattern, x["seatNumber"])]
        allocated_seats =[x["seatNumber"] for x in wagon["allocationSeats"]]
        empty_seats = list(set(all_seats) - set(allocated_seats))
        if empty_seats:
            wagon_id = wagon["trainCarId"]
            # hold the seat
            reserve_payload = {
                "trainCarId": wagon_id,
                "fromStationId": departure_id,
                "toStationId": arrival_id,
                "gender": "M",
                "seatNumber": empty_seats[0],
                "passengerTypeId": 0,
                "totalPassengerCount": 1,
                "fareFamilyId": 0
            }
            response = requests.post(base_url+"inventory/select-seat?environment=dev&userId=1", headers=base_headers, json=reserve_payload)
            if response.status_code == 200:
                allocation_id = response.json()["allocationId"]
                sendTelegramMessage(f'{user_departure} - {user_arrival} arası {readable_date} tarihli trende *{wagon_index+1}. vagonda {empty_seats[0]}* numaralı koltuk tutuldu.')
                sendTelegramMessage(f'10 dakika süreniz var. Eğer 10 dakika içinde /yhtrelease komutunu kullanmazsanız koltuk bırakılacak ve program kapatılacak.')
                try:
                    user_input = inputimeout(prompt='Please enter something: ', timeout=600)  # 600 seconds = 10 minutes
                except TimeoutOccurred:
                    user_input = None
                if user_input is not None:
                    release_seat(wagon_id, allocation_id, empty_seats[0])
                else:
                    sendTelegramMessage(f'10 dakika süreniz doldu. Koltuk bırakılıyor ve program kapatılıyor.')
                    sys.exit(0)

def check_yht():
    global base_url, base_headers, base_payload, train_request_error, full_date, readable_date, hour_check_flag, hour_check_error, empty_economy, empty_business, departure_id
    response = requests.post(base_url+"train/train-availability?environment=dev&userId=1", headers=base_headers, json=base_payload)

    if response.status_code != 200:
        train_request_error += 1
        if train_request_error == MAX_ERR_COUNT:
            sendTelegramMessage(f"*Hata: {response.status_code}* TCDD sitesi yanıt vermiyor. Lütfen kontrol edin. Program durduruldu.")
            sys.exit(1)
        return
    
    data = response.json()

    train_list = [x["trains"][0] for x in data["trainLegs"][0]["trainAvailabilities"] if x["trains"][0]["type"] == "YHT"]
    
    if not train_list:
        train_request_error += 1
        if train_request_error == MAX_ERR_COUNT:
            sendTelegramMessage(f"*Hata: {response.status_code}* TCDD sitesi yanıt vermiyor. Lütfen kontrol edin. Program durduruldu.")
            sys.exit(1)
        return

    train_request_error = 0
    hour_check_flag = False
    for train in train_list:
        train_segment_index = next((i for i, x in enumerate(train["trainSegments"]) if x["departureStationId"] == departure_id), 0)
        if train["trainSegments"][train_segment_index]["departureTime"] == full_date:
            hour_check_flag = True
            hour_check_error = 0
            economy_available_count = next((x["availabilityCount"] for x in train["cabinClassAvailabilities"] if x["cabinClass"]["code"] == "Y1"), 0)
            business_available_count = next((x["availabilityCount"] for x in train["cabinClassAvailabilities"] if x["cabinClass"]["code"] == "C"), 0)
            if economy_available_count > 0:
                hold_seat(train["id"])
                return
            elif empty_economy != economy_available_count:
                empty_economy = economy_available_count
                sendTelegramMessage(user_info_message(empty_economy, "Ekonomi"))
            if empty_business != business_available_count:
                empty_business = business_available_count
                sendTelegramMessage(user_info_message(empty_business, "Business"))
            break

    if not hour_check_flag:
        hour_check_error += 1
        if hour_check_error == MAX_ERR_COUNT:
            sendTelegramMessage(f"*Hata:* {readable_date} tarihli tren bulunamadı. Program durduruldu.")
            sys.exit(1)

while True:
    try:
        check_yht()
        time.sleep(timeout)
        if timeout > 100:
            timeout = 30
        main_error_count  = 0
    except Exception as e:
        # due to the nature of the program, it is expected to have some errors.
        # however, if the error count exceeds MAX_ERR_COUNT, the program will be terminated.
        timeout *= 1.5
        main_error_count += 1
        if main_error_count > MAX_ERR_COUNT:
            sendTelegramMessage(f'Programda bir hata oluştu: {e}. İşlem kapatılıyor.')
            sys.exit(1)
