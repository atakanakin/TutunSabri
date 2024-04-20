from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import time
import requests
import sys
import signal

#read system arguments
botToken = sys.argv[1]
chatId = sys.argv[2]
user_nereden = sys.argv[3]
user_nereye = sys.argv[4]
user_tarih = sys.argv[5]
user_hour = sys.argv[6]
state = -1
timeout = 30


def signal_handler(sig, frame):
    sendTelegramMessage("YHT Seat Check programı kapatılıyor...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def sendTelegramMessage(message):
    # bot = Bot(token = botToken)
    # bot.send_message(chat_id=chatId, text=message)
    url = f"https://api.telegram.org/bot{botToken}/sendMessage?chat_id={chatId}&text={message}"
    res = requests.get(url).json()  # this sends the message
    if res.status_code != 200:
        raise Exception('Invalid response from Telegram API')



def initial_search():
    # Open the browser and go to the website
    options = Options()
    # user agent
    # Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-logging')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')

    options.page_load_strategy = 'normal'
    
    browser = webdriver.Chrome(options=options)
    browser.get('https://ebilet.tcddtasimacilik.gov.tr/view/eybis/tnmGenel/tcddWebContent.jsf')

    # nereden
    browser.find_element(By.XPATH, '//*[@id="nereden"]').send_keys(user_nereden)
    time.sleep(1)
    ActionChains(browser).send_keys(Keys.DOWN).send_keys(Keys.RETURN).perform()
    time.sleep(1)

    # nereye
    browser.find_element(By.XPATH, '//*[@id="nereye"]').send_keys(user_nereye)
    time.sleep(1)
    ActionChains(browser).send_keys(Keys.DOWN).send_keys(Keys.RETURN).perform()
    time.sleep(1)

    # tarih
    tarih = browser.find_element(By.XPATH, '//*[@id="trCalGid_input"]')
    tarih.clear()
    time.sleep(1)
    tarih.send_keys(user_tarih)
    ActionChains(browser).send_keys(Keys.TAB).perform()
    time.sleep(1)

    # ara
    browser.find_element(By.XPATH, '//*[@id="btnSeferSorgula"]/span').click()

    return browser

def get_browser():
    browser = initial_search()
    while(browser.current_url == 'https://ebilet.tcddtasimacilik.gov.tr/view/eybis/tnmGenel/tcddWebContent.jsf?expired=true'):

        browser.quit()
        time.sleep(1)
        browser = initial_search()
    return browser



def check_yht(counter = 0):
    browser = get_browser()
    # Wait for the page to load
    time.sleep(5)
    # Locate the table element
    table = browser.find_element(By.XPATH, '//*[@id="mainTabView:gidisSeferTablosu_data"]')

    # Get all rows of the table
    rows = table.find_elements(By.TAG_NAME, 'tr')
    while rows == []:
        if counter > 5:
            return
        browser.quit()
        time.sleep(1)
        check_yht(counter + 1)
        return

    for row in rows:
        # Extract data from each cell in the row
        cells = row.find_elements(By.TAG_NAME, 'td')
        hour = cells[0].text.split('\n')[1].strip()

        isYht = (cells[3].text).find('YHT') != -1

        if(isYht and hour in user_hour):
            countInfo = (cells[4].text).split(')')[1].replace('(', '').strip()
            
            try:
                countInfo = int(countInfo)
            except:
                countInfo = 0

            global state
            if(countInfo != state):
                state = countInfo
                if(countInfo > 0):
                    sendTelegramMessage(f'{user_nereden} - {user_nereye} arası {user_tarih} {hour} tarihli YHT seferinde {countInfo} kişilik yer bulunmaktadır.')
                else:
                    sendTelegramMessage(f'{user_nereden} - {user_nereye} arası {user_tarih} {hour} tarihli YHT seferinde yer bulunmamaktadır.')
    browser.quit()
    time.sleep(1)

counter = 0
while True:
    try:
        check_yht()
        counter = 0
        time.sleep(timeout)
    except Exception as e:
        counter += 1
        
        if counter > 5:
            f = open(f'yht/{chatId}_error.log', 'a+')
            f.write(f'{str(e)}\n\n')
            f.write(f'{time.ctime()}\n\n')
            f.close()
            sendTelegramMessage(f'YHT Seat Check programında bir hata oluştu. Hata loglarına error.log dosyasından ulaşabilirsiniz.')
            sys.exit(0)
