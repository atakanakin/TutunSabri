import sys
import json
import requests

def normalize_text(text: str):
    temp_str = text.replace('I', 'ı')
    text = temp_str.replace('İ', 'i')
    
    return text.lower()

def get_all_stations():
    station_dict = {}

    url = "https://api-yebsp.tcddtasimacilik.gov.tr/istasyon/istasyonYukle"

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
        "Sec-Fetch-Site": "cross-site"
    }

    payload = {
        "kanalKodu": "3",
        "dil": 1,
        "satisSorgu": True
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Check if the request was successful
    if response.status_code == 200:
        try:
            response_json = response.json()
            for i in response_json['istasyonBilgileriList']:
                
                # check if it is High Speed Train station
                if 'YHT' in i['stationTrainTypes']:
                    temp_view_name = i['stationViewName'].split(', ')[-1]
                    
                    temp_view_name = normalize_text(temp_view_name)

                    # Check if the station name is already in the dictionary
                    if temp_view_name in station_dict:
                        station_dict[temp_view_name].append(i['istasyonAdi'])
                    else:
                        station_dict[temp_view_name] = [i['istasyonAdi']]
                
            # dump the dictionary to a json file
            with open('station_dict.json', 'w', encoding='utf-8') as f:
                json.dump(station_dict, f, indent=4, ensure_ascii=False)
        except json.JSONDecodeError:
            print('Error decoding JSON response. Exiting...')
            sys.exit(1)
    else:
        print('Error fetching stations. Exiting...')
        sys.exit(1)

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