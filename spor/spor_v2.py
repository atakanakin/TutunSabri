import os
import sys
import time
import json
import datetime
import requests
from bs4 import BeautifulSoup

chatId = sys.argv[1]
botToken = sys.argv[2]
desiredTime = sys.argv[3]

with open(os.path.join(os.getcwd(), 'credentials', 'rezmetu', f'{chatId}.json')) as config_file:
    config = json.load(config_file)

lastState = None


def sendTelegramMessage(message):
    global chatId, botToken
    url = f"https://api.telegram.org/bot{botToken}/sendMessage?chat_id={chatId}&text={message}"
    requests.get(url).json()

def main():
    global lastState, desiredTime, config
    session = requests.Session()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://rez.metu.edu.tr/'
    }

    login_page_url = 'https://rez.metu.edu.tr/'
    initial_response = session.get(login_page_url, headers=headers)

    soup = BeautifulSoup(initial_response.text, 'html.parser')
    viewstate = soup.find('input', {'name': 'javax.faces.ViewState'})['value']

    payload = {
        'javax.faces.partial.ajax': 'true',
        'javax.faces.source': 'form:button',
        'javax.faces.partial.execute': 'form',
        'javax.faces.partial.render': 'form',
        'form:button': 'form:button',
        'form': 'form',
        'form:user': config['username'],
        'form:password': config['password'],
        'javax.faces.ViewState': viewstate
    }

    response = session.post(login_page_url, data=payload, headers=headers)

    if response.status_code == 200:
        encodings = ['utf-8', 'iso-8859-1', 'windows-1252']
        for encoding in encodings:
            try:
                decoded_content = response.content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        xml_soup = BeautifulSoup(decoded_content, 'xml')
        redirect_element = xml_soup.find('redirect')
        
        if redirect_element:
            pass
            #print("Login successful.")
        else:
            sendTelegramMessage("Spor Command: Login failed. Please check your username and password.")
            sys.exit()
    else:
        sendTelegramMessage(f"Spor Command: Login failed with status code {response.status_code}")
        sys.exit()

    secondary_response = session.get('https://rez.metu.edu.tr/view/home.jsf', headers=headers, cookies=session.cookies)

    soup = BeautifulSoup(secondary_response.text, 'html.parser')
    viewstate = soup.find('input', {'name': 'javax.faces.ViewState'})['value']

    facility_payload = {
        'javax.faces.partial.ajax': 'true',
        'javax.faces.source': 'form:facility',
        'javax.faces.partial.execute': 'form:facility',
        'javax.faces.partial.render': 'form:facility',
        'javax.faces.behavior.event': 'valueChange',
        'javax.faces.partial.event': 'change',
        'form:facility': '21', #change this to your facility id - 21 is: ODTÜKENT Spor Merkezi - Fitness Salonu
        'form': 'form',
        'javax.faces.ViewState': viewstate
    }

    facility_response = session.post('https://rez.metu.edu.tr/view/home.jsf', data=facility_payload, headers=headers, cookies=session.cookies)

    start_time = datetime.datetime.now()
    end_time = start_time.replace(hour=0, minute=0, second=0) + datetime.timedelta(days=1)

    start_time = int(start_time.timestamp() * 1000)
    end_time = int(end_time.timestamp() * 1000)


    if facility_response.status_code == 200:
        #print("Facility selection successful.")
        
        # Extract updated ViewState after facility selection
        xml_soup = BeautifulSoup(facility_response.content, 'xml')
        viewstate = xml_soup.find('update', {'id': 'j_id1:javax.faces.ViewState:0'}).text.strip()
        
        schedule_payload = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'form:myschedule',
            'javax.faces.partial.execute': 'form:myschedule',
            'javax.faces.partial.render': 'form:myschedule',
            'form:myschedule': 'form:myschedule',
            'form:myschedule_start': start_time,
            'form:myschedule_end': end_time,
            'form:facility': '21',
            'form:myschedule_view': 'agendaDay',
            'form': 'form',
            'javax.faces.ViewState': viewstate
        }

        schedule_response = session.post('https://rez.metu.edu.tr/view/home.jsf', data=schedule_payload, headers=headers, cookies=session.cookies)

        if schedule_response.status_code == 200:
            #print("Schedule retrieved successfully.")
            #decoded_content = schedule_response.content.decode('utf-8')
            soup = BeautifulSoup(schedule_response.content, 'xml')
            
            # Find the update tag with the relevant CDATA section
            update_tag = soup.find('update', id="form:myschedule")
            
            if update_tag and update_tag.string:
                cdata_content = update_tag.string
                
                # Load the JSON data from the CDATA section
                try:
                    schedule_data = json.loads(cdata_content)
                    
                    # Extract the events
                    events = schedule_data.get('events', [])

                    flag = False
                    
                    # Extract start and title values from each event
                    for event in events:
                        # convert 2024-05-20T18:00:00+0300 to datetime object
                        start = datetime.datetime.strptime(event['start'], '%Y-%m-%dT%H:%M:%S%z')
                        # if int 9, convert to string '09'
                        start_hour = str(start.hour).zfill(2)
                        start_minute = str(start.minute).zfill(2)
                        session_start_time = f"{start_hour}:{start_minute}"
                        empty_slots = int(event['title'].split(': ')[1])
                        if session_start_time == desiredTime:
                            flag = True
                            if empty_slots == lastState:
                                return
                            if empty_slots == 0:
                                #print(f"{desiredTime} seansında boş yer yok.")
                                sendTelegramMessage(f"{desiredTime} seansında boş yer yok.")
                            else:
                                #print(f"{desiredTime} seansında {empty_slots} kişilik boş yer var.")
                                sendTelegramMessage(f"{desiredTime} seansında {empty_slots} kişilik boş yer var.")
                            lastState = empty_slots
                    if not flag:
                        sendTelegramMessage(f"{desiredTime} seansında boş yer yok.")
                except json.JSONDecodeError:
                    pass
                    #print("Failed to decode JSON data.")
            else:
                pass
                #print("No CDATA section found in the response.")
            
        else:
            pass
            # print(f"Schedule retrieval failed with status code {schedule_response.status_code}")
            # print(schedule_response.text)
    else:
        pass
        # print(f"Facility selection failed with status code {facility_response.status_code}")
        # print(facility_response.text)


if __name__ == "__main__":
    while True:
        main()
        time.sleep(30)