import edge_tts
import random
import os
from langdetect import detect
import argparse
import asyncio

parser = argparse.ArgumentParser()
parser.add_argument('-p', '--path', type= str, help='Provide the path to the text file', required=True)


args = parser.parse_args()
path = args.path

async def text_to_speech(path: str):
    f = open(path, 'r', encoding='utf-8')
    text = f.read()
    f.close()
    # first we need to detect the language of the text using 'langdetect' library
    lang = detect(text)
    if lang == "en":
        lang = "en-US"
    elif lang == "tr":
        lang = "tr-TR"

    # get the voice list and choose random one
    voice_list = await voices(lang)
    voice = random.choice(voice_list)[0]

    output_file = f'{path[:-4]}.mp3' 
    communicate = edge_tts.Communicate(text, voice, receive_timeout=10)

    with open(output_file, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
    os.remove(path)
    print(output_file)
    

# from the voices available filter only the language we detect
async def voices(lang: str = 'en-US'):
    voices = await edge_tts.list_voices()
    final = []
    for i in voices:
        if(lang in i["Locale"]):
            if("Cute" in i['VoiceTag']['VoicePersonalities']):
                continue
            # keep the gender value in case one might want to add gender specific processes
            final.append((i["ShortName"], i["Gender"]))
    return final

asyncio.run(text_to_speech(path))
