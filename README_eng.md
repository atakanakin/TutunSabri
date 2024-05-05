# <center>Tütün Sabri</center>

__[Türkçe versiyonu için tıklayınız.](README.md)__

![Tütün Sabri](https://i.imgur.com/KoYarmr.jpg)

## The Tale of Tütün Sabri

Once upon a time, amidst the harsh lands of Adıyaman, nestled among the mountains, the story of Tütün Sabri begins under the shade of an old plane tree.

In the heat of the Independence War, Tütün Sabri grew underground as a resistant. His youth was not adorned with heroism but rather with troubles and illicit activities. Some saw him as a vagabond, while others regarded him as a daring adventurer. Yet, his true recognition came from the sacrifices he made for the love of his homeland.

Since his childhood, Tütün Sabri, who had swallowed the dust of war, stood by his people, fighting for the independence of his nation. Initially, he resisted the enemy with groups that were seen as gangs. However, over time, his belief in the national struggle grew, and he became a staunch supporter of the National Forces. Perhaps his greatest battle was the one fought within himself, with doubts clouding his mind. But in the end, his patriotism prevailed.

After the challenging years of his youth, Tütün Sabri took root in the lands of Adıyaman. The traces of war now marked his body, and the sorrow of years lingered in his eyes. Yet, the fire in his heart never extinguished. With every puff of smoke, he reminisced about his past, never forgetting.

However, amidst all this heroism and sacrifice, Tütün Sabri felt a void in his heart. Before going to war, he had fallen in love with one of the beautiful girls of Adıyaman. He had promised to marry her, but fate intervened cruelly once again. When her father died, her family took her away to keep her away from the chaos of war. When Tütün Sabri returned from war, he could never see the woman he loved again. Perhaps he spent years trying to find her, or maybe he spent his life simply gazing at the stars, waiting with hope. But regardless, the love and hope in his heart never faded. This too was a part of his story, as he journeyed from the memories of the past towards the future.

Me in the flesh.
![Tütün Sabri-actual](https://i.imgur.com/OIpUDhX.jpg)

## How to Use

## Commands

### /start /help /info
Provides details about the bot and how to use it.

### /youtube YOUTUBE_URL
With this command, you can download the video, audio, or clip you selected by providing its link. Since Telegram has a 50 MB limit for videos, if the upload fails, the video will be uploaded to Dropbox and a download link will be provided to you.

### /tts TEXT
This command converts the entered text into a voice file and sends it to you. It supports more than 46 languages.

### /yht
When you enter this command, parameters such as Departure station, Arrival station, date, and time will be requested from you. During this query, you can type 'cancel' to cancel the operation. After entering this information, a search for TCDD HST tickets will begin. At this stage, it is essential to enter the stop names as they appear on the TCDD website. If the number of available seats changes, you will receive a message. To end the search, use the command __/yhtcancel__.

### /spor
When you enter this command, if you haven't logged in before, you will be asked for a username and password. During this query, you can type 'cancel' to cancel the operation. After entering this information, you will be asked to enter a session time. After entering this information, it informs you about the changes in the quota for that session at ODTÜKENT sports center. To end the search, use the command __/sporcancel__.

### /pedro
PEDRO

### /mood
Sends a random video from preselected videos. You can check the mood.json file under the mood folder for more details.

### /twitter
Coming soon...

## Admin Commands

### requests
This bot is a whitelist bot, meaning only specific users can use it. With this command, you can access the list of users who want to use the bot.

### grant USER_ID
With this command, you can grant permission to a specific user to use the bot. USER_ID is the user's Telegram ID.

### revoke USER_ID
With this command, you can revoke the permission for a specific user to use the bot. USER_ID is the user's Telegram ID.

### listusers
With this command, you can access the list of users who have permission to use the bot.

### /process
With this command, you can see the active processes. If you want to cancel a process, you can use the command __/kill pid__ followed by the process number.

### /kill pid
With this command, you can terminate a specific process.

### /hostname
With this command, you can find out the name of the server where the bot is running. You will need this information if you want to connect via SSH.

### /selfie
This command takes a photo from your Raspberry Pi camera and sends it to you. It only works if you have a Raspberry Pi camera.

### /instagram
With this command, you can add a new Instagram account, share reels videos from the accounts you added, or download reels videos from users and hashtags. Additionally, if you have an Android emulator running on the device where the bot is running or if you have an Android device connected via cable, you can log in to Instagram with that device and automatically follow users, unfollow users, and like posts. The follow process consists of three categories: following users who liked posts in the hashtag you specified, following the posts of a specified user, and following the followers of a specified user. While these operations are being performed, a certain period of time is waited to avoid detection by the Instagram algorithm. These waiting times may vary depending on the speed of the device where the bot is running. The aim here is not to perform fast operations but to perform operations without being detected. Therefore, the operations may be a bit slow. Be cautious about the security of your Instagram account while performing these operations. For more information, you can refer to the [GramAddict](https://github.com/GramAddict/bot) library.

## Development

Before starting development, make sure you have installed the required dependencies by running:

```
python -m pip install -r requirements.txt
```

Also, ensure to follow the instructions in [youtube/executable/README.md](youtube/executable/README.md) to set up the necessary components for using the __/youtube__ command.

Before launching the bot, insert your credentials into the [bot_config.json](bot_config.json) file.

To start the bot, you can simply run:

```
python main.py
```

For an extra layer of error handling, you can run:

```
python wrapper.py
```

If you wish to run the bot on startup, navigate to the [start_sabri.sh](start_sabri.sh) file and replace the path with your repository path. Then, run the following command:

```
chmod +x start_sabri.sh
```

Finally, add the following line to your crontab:

```
@reboot /path/to/start_sabri.sh
```

## Contributing

If you encounter any problems or issues while using the bot, please submit an issue on the [issue tracker](https://github.com/atakanakin/TutunSabri/issues).

If you want to contribute to the project, you can clone the repository using the following command:

```
git clone https://github.com/atakanakin/TutunSabri.git
```

Feel free to make changes, add features, or fix bugs. Once you're done, submit a pull request to the main repository.

Happy coding!