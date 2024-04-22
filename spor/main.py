import os
import sys
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import selenium.webdriver.support.select as select
from selenium.webdriver.firefox.options import Options

chatId = sys.argv[1]
botToken = sys.argv[2]
desiredTime = sys.argv[3]
facilityName = 'ODTÜKENT Spor Merkezi - Fitness Salonu'

with open(os.path.join(os.getcwd(), 'credentials', 'rezmetu', f'{chatId}.json')) as config_file:
    config = json.load(config_file)

lastState = None


def sendTelegramMessage(message):
    global chatId, botToken
    url = f"https://api.telegram.org/bot{botToken}/sendMessage?chat_id={chatId}&text={message}"
    requests.get(url).json()


def main():
    global lastState, desiredTime, config, facilityName

    try:
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
        driver = webdriver.Chrome(options=options)
        
    except:
        print("Chrome driver not found. Please install it and try again.")
        return

    loginUrl = "https://rez.metu.edu.tr/"
    driver.get(loginUrl)
    usernameField = driver.find_element(
        By.XPATH, "//*[contains(@id, 'user')]")
    passwordField = driver.find_element(
        By.XPATH, "//*[contains(@id, 'password')]")
    usernameField.send_keys(config["username"])
    passwordField.send_keys(config["password"])
    passwordField.send_keys(Keys.RETURN)
    time.sleep(2)

    if driver.current_url != loginUrl:
        print("Login successful.")
    else:
        print("Login failed. Please check your credentials.")
        driver.quit()
        return

    try:
        dropdownSelect = select.Select(driver.find_element(
            # By.XPATH, "//*[@id=\"j_idt99:facility\"]"))
            By.XPATH, "//*[contains(@id, 'facility')]"))
        dropdownSelect.select_by_visible_text(facilityName)
    except:
        print("Facility not found. Please check your facility name. Try changing it with English/Turkish one.")
        driver.quit()
        return
    time.sleep(3)

    try:
        spanXPath = f"//span[contains(text(), '{desiredTime}')]"
        spanElement = driver.find_element(By.XPATH, spanXPath)
        grandParentElement = spanElement.find_element(By.XPATH, "./../..")
        secondChildOfGrandParent = grandParentElement.find_element(
            By.XPATH, "./*[2]")
        textInSecondChild = secondChildOfGrandParent.text
        empty = int(textInSecondChild.split()[2])
    except:
        empty = 0

    if empty == lastState:
        driver.quit()
        return

    if empty == 0:
        sendTelegramMessage(
            f"{facilityName} {desiredTime} seansında boş yer yok.")
    elif empty > 0:
        sendTelegramMessage(
            f"{facilityName} {desiredTime} seansında {empty} kişilik boş yer var.")

    lastState = empty
    driver.quit()
    return


if __name__ == "__main__":
    while True:
        main()
        time.sleep(20)
