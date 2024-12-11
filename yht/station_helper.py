import json
import requests
from datetime import datetime, timedelta

base_headers = {
    "unit-id": "3895",
    "Authorization": ("eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0."
                    "eyJleHAiOjE3MjEzODQ0NzAsImlhdCI6MTcyMTM4NDQxMCwianRpIjoiYWFlNjVkNzgtNmRkZS00ZGY4LWEwZWYtYjRkNzZiYjZlODNjIiwiaXNzIjoiaHR0cDovL3l0cC1wcm9kLW1hc3RlcjEudGNkZHRhc2ltYWNpbGlrLmdvdi50cjo4MDgwL3JlYWxtcy9tYXN0ZXIiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiMDAzNDI3MmMtNTc2Yi00OTBlLWJhOTgtNTFkMzc1NWNhYjA3IiwidHlwIjoiQmVhcmVyIiwiYXpwIjoidG1zIiwic2Vzc2lvbl9zdGF0ZSI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImFjciI6IjEiLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy1tYXN0ZXIiLCJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJvcGVuaWQgZW1haWwgcHJvZmlsZSIsInNpZCI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoid2ViIiwiZ2l2ZW5fbmFtZSI6IiIsImZhbWlseV9uYW1lIjoiIn0.AIW_4Qws2wfwxyVg8dgHRT9jB3qNavob2C4mEQIQGl3urzW2jALPx-e51ZwHUb-TXB-X2RPHakonxKnWG6tDIP5aKhiidzXDcr6pDDoYU5DnQhMg1kywyOaMXsjLFjuYN5PAyGUMh6YSOVsg1PzNh-5GrJF44pS47JnB9zk03Pr08napjsZPoRB-5N4GQ49cnx7ePC82Y7YIc-gTew2baqKQPz9_v381Gbm2V38PZDH9KldlcWut7kqQYJFMJ7dkM_entPJn9lFk7R5h5j_06OlQEpWRMQTn9SQ1AYxxmZxBu5XYMKDkn4rzIIVCkdTPJNCt5PvjENjClKFeUA1DOg"),
    "Sec-Fetch-Site": "same-site",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "tr",
    "Sec-Fetch-Mode": "cors",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty"
}

def normalize_text(text: str):
    temp_str = text.replace('I', 'ı')
    text = temp_str.replace('İ', 'i')
    
    return text.lower()

def get_all_stations():
    global base_headers
    url = "https://cdn-api-prod-ytp.tcddtasimacilik.gov.tr/datas/station-pairs-INTERNET.json?environment=dev&userId=1"

    response = requests.get(url, headers=base_headers)
    data = response.json()
    yht_stations = [x for x in data if x["stationTrainTypes"] and "YHT" in x["stationTrainTypes"]]
    station_dict = {}
    station_id_dict = {}
    for station in yht_stations:
        if not station["district"]:
            # some stations do not have district information
            # skip for now
            continue
        station_city = normalize_text(station["district"]["city"]["name"])
        station_name = station["name"]
        station_id_dict[station_name] = station["id"]
        if station_city in station_dict:
            station_dict[station_city].append(station_name)
        else:
            station_dict[station_city] = [station_name]

    with open('station_dict.json', 'w', encoding='utf-8') as f:
        json.dump(station_dict, f, indent=4, ensure_ascii=False)

    with open('station_id_dict.json', 'w', encoding='utf-8') as f:
        json.dump(station_id_dict, f, indent=4, ensure_ascii=False)

def get_proper_station(station_name):
    with open('station_dict.json', 'r', encoding='utf-8') as f:
        station_dict = json.load(f)
    
    normalized_station_name = normalize_text(station_name)
    
    # Check if the station name is in the dictionary
    # also check when station_name is a substring of a key in the dictionary
    stations = []

    for key in station_dict.keys():
        if normalized_station_name in key:
            stations += station_dict[key]
    
    return stations 

def get_station_id(station_name):
    with open('station_id_dict.json', 'r', encoding='utf-8') as f:
        station_id_dict = json.load(f)
    
    return station_id_dict[station_name]

def yht_hour_helper(departure, arrival, date):
    global base_headers
    url = "https://gise-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability?environment=dev&userId=1"
    payload = {
        "searchRoutes": [
            {
                "departureStationId": get_station_id(departure),
                "arrivalStationId": get_station_id(arrival),
                "departureDate": f"{date.replace(".", "-")} 00:00:00"
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
    try:
        response = requests.post(url, headers=base_headers, json=payload)
        data = response.json()
        train_list = [x["trains"][0] for x in data["trainLegs"][0]["trainAvailabilities"] if x["trains"][0]["type"] == "YHT"]
        departure_id = get_station_id(departure)
        hours = [
            (datetime.strptime(segment["departureTime"], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=3)).strftime("%H:%M")
            for train in train_list
            for segment in train["trainSegments"]
            if segment["departureStationId"] == departure_id
        ]
        return hours
    except:
        return []
