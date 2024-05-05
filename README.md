# <center>Tütün Sabri</center>

__[for english version, please click](README_eng.md)__

![Tütün Sabri](https://i.imgur.com/KoYarmr.jpg)

## Tütün Sabri'nin Hikayesi

Bir zamanlar, sert topraklarında Adıyaman'ın, dağların arasında, yaşlı bir çınar ağacının gölgesinde Tütün Sabri'nin hikayesi başlar.

Kurtuluş Savaşı'nın sıcak günlerinde, toprağın altında kök salmış bir direnişçi olarak yetişti Tütün Sabri. Gençliği, kahramanlıkla değil, belalarla ve illegal işlerle doluydu. Kimilerine göre bir serseri, kimilerine göre ise cesur bir maceraperestti. Ama asıl tanınışı, vatan sevgisi uğruna gösterdiği fedakarlıklarla oldu.

Çocukluğundan beri, savaşın tozunu yutan Tütün Sabri, halkının yanında, vatanının bağımsızlığı için mücadele etti. İlk başlarda, çete gibi görülen gruplarıyla, düşmana karşı koydu. Ancak zamanla, milli mücadeleye olan inancıyla birleşti ve Kuvâ-yı Millîyeci oldu. Belki de en büyük savaşı, içindeki şüphelerle verdi. Ama sonunda, vatanseverliği galip geldi.

Zorlu geçen gençlik yıllarından sonra, Adıyaman'ın topraklarına kök saldı Tütün Sabri. Artık savaşın izleri bedeninde, yılların hüznü gözlerindeydi. Ancak yüreğindeki ateş hiç sönmemişti. Her dumanıyla, geçmişinin hatıralarını tüttürdü, unutmadı.

Ama tüm bu kahramanlık ve fedakarlıkların arasında, kalbinde bir boşluk hissetti Tütün Sabri. Savaşa gitmeden önce, Adıyaman'ın güzel kızlarından birine aşık olmuştu. Onunla evlenme sözü vermişti, ama kader bir kez daha acımasızca müdahale etti. Sevdiğinin babası öldüğünde, ailesi onu savaşın karmaşasından uzaklaştırmak için alıp götürdü. Tütün Sabri, savaştan döndüğünde sevdiği kadını bir daha göremedi. Belki de onu bulmak için yıllarını harcadı, belki de yalnızca yıldızlara bakarak geçirdi ömrünü, umutla bekleyerek. Ancak ne olursa olsun, onun yüreğindeki sevda ve umut, hiç solmadı. Bu da onun hikayesinin bir parçasıydı, geçmişin hatıralarıyla geleceğe doğru ilerlerken.

Gerçekte ben.
![Tütün Sabri-actual](https://i.imgur.com/OIpUDhX.jpg)

## Nasıl kullanılır

## Komutlar

### /start /help /info
Bot hakkında ve nasıl kullanılacağı hakkında detaylar verir.

### /youtube YOUTUBE_URL
Bu komutla bağlantısını verdiğiniz YouTube videosunu, sesi veya aralığını seçtiğiniz klibi indirebilirsiniz. Telegram'da videolar için 50 MB sınırı olduğundan yükleme başarısız olursa video Dropbox'a yüklenir ve size bir indirme bağlantısı sağlanır. 

### /tts TEXT
Bu komutla girdiğiniz metin ses dosyasına çevrilip size gönderilir. 46'dan fazla dil desteği bulunmaktadır.

### /yht
Bu komutu girdiğinizde size Kalkış istasyonu, Varış istasyonu, tarih ve zaman gibi parametreler sorulur. Bu sorgu sırasında işlemi iptal etmek için 'cancel' yazabilirsiniz. Bunları girdikten sonra TCDD YHT bileti için arama yapılmaya başlanır. Bu aşamada kritik detay durak isimlerini TCDD web sitesinde geçtiği gibi girmenizdir. Eğer boş koltuk sayısı değişirse size bir mesaj gönderilir. Aramayı sonlandırmak için __/yhtcancel__ komutunu kullanınız.

### /spor
Bu komutu girdiğinizde eğer daha önce giriş yapmadıysanız size bir kullanıcı adı ve şifre sorulur. Bu sorgu sırasında işlemi iptal etmek için 'cancel' yazabilirsiniz. Bu bilgileri girdikten sonra sizden bir seans saati girmeniz istenir. Bu bilgileri girdikten sonra ODTÜKENT spor merkezinde o seansta bulunan kontenjan değişikliklerini size bildirir. Aramayı sonlandırmak için __/sporcancel__ komutunu kullanınız. 

### /pedro
PEDRO

### /mood
Önceden seçilmiş videolar arasından random bir video gönderir. mood klasörü altında mood.json dosyasına göz atabilirsiniz.

### /twitter
Çok yakında...

## Admin Komutları

### requests
Bu bot bir whitelist botudur. Yani sadece belirli kullanıcılar bu botu kullanabilir. Bu komutla botu kullanmak isteyen kullanıcıların listesine erişebilirsiniz.

### grant USER_ID
Bu komutla belirli bir kullanıcıya botu kullanma izni verebilirsiniz. USER_ID, kullanıcının Telegram ID'sidir.

### revoke USER_ID
Bu komutla belirli bir kullanıcının botu kullanma iznini iptal edebilirsiniz. USER_ID, kullanıcının Telegram ID'sidir.

### listusers
Bu komutla botu kullanma izni olan kullanıcıların listesine erişebilirsiniz.

### /process
Bu komutla aktif olan işlemleri görebilirsiniz. Eğer bir işlemi iptal etmek isterseniz, işlem numarasını kullanarak __/kill pid__ komutunu kullanabilirsiniz.

### /kill pid
Bu komutla belirli bir işlemi sonlandırabilirsiniz.

### /hostname
Bu komutla botun çalıştığı sunucunun ismini öğrenebilirsiniz. SSH ile bağlanmak isterseniz bu bilgiye ihtiyacınız olacaktır.

### /selfie
Bu komut raspberry pi kameranızdan bir fotoğraf çekip size gönderir. Sadece raspberry pi kameranız varsa çalışır.

### /instagram
Bu komutu kullanarak yeni bir instagram hesabı ekleyebilir, eklediğiniz hesaplardan reels videoları paylaşabilir veya kullanıcıların ve hashtaglerin reels videolarını indirebilirsiniz. Ayrıca botu çalıştırdığınız cihazda çalışan bir android emulator varsa veya kabloyla bağlı bir android cihaz varsa bu cihazı kullanarak instagrama giriş yapabilir, kullanıcıları otomatik olarak takip edebilir, takipten çıkabilir, gönderilerini beğenebilirsiniz.
Takip işlemi üç kategöriden oluşur. Bunlar: belirttiğiniz hashtagdeki gönderileri beğenenleri takip etme, belirttiğiniz bir kullanıcının gönderilerini takip etme ve belirttiğiniz bir kullanıcının takipçilerini takip etmedir. Bu işlemler yapılırken instagram algoritmasının sizi engellememesi için belirli bir süre beklenir. Bu süreler botun çalıştığı cihazın hızına göre değişebilir. Burada amaç hızlı işlem yapmak değil tespit edilmeden işlem yapmaktır. Bu yüzden işlemler biraz yavaş olabilir. Bu işlemleri yaparken instagram hesabınızın güvenliğini düşünerek hareket edin. Daha fazla bilgi için [GramAddict](https://github.com/GramAddict/bot) kütüphanesine bakabilirsiniz.

## Geliştirme

Geliştirmeye başlamadan önce, gereken kütüphaneleri yüklediğinizden emin olun:

```
python -m pip install -r requirements.txt
```

Ayrıca, __/youtube__ komutunu kullanmak için gerekli bileşenleri kurmak için [youtube/executable/README.md](youtube/executable/README.md) dosyasındaki talimatları izlediğinizden emin olun.

Botu başlatmadan önce, gerekli bilgileri [bot_config.json](bot_config.json) dosyasına eklediğinizden emin olun.

Botu başlatmak için şu komutu kullanabilirsiniz:

```
python main.py
```

Ek bir error handling katmanı için şu komutu çalıştırabilirsiniz:

```
python wrapper.py
```

Botu başlangıçta çalıştırmak istiyorsanız, [start_sabri.sh](start_sabri.sh) dosyasına gidin ve yolunuzu repository yolunuzla değiştirin. Ardından, aşağıdaki komutu çalıştırın:

```
chmod +x start_sabri.sh
```

Son olarak, crontab dosyanıza aşağıdaki satırı ekleyin:

```
@reboot /path/to/start_sabri.sh
```

## Katkıda Bulunma

Botu kullanırken herhangi bir sorunla karşılaşırsanız lütfen [issue tracker](https://github.com/atakanakin/TutunSabri/issues) üzerinden bir sorun bildirin.

Projeye katkıda bulunmak istiyorsanız, aşağıdaki komutu kullanarak depoyu klonlayabilirsiniz:

```
git clone https://github.com/atakanakin/TutunSabri.git
```

Değişiklikler yapmaktan, özellikler eklemekten veya hataları düzeltmekten çekinmeyin. İşiniz bittiğinde, main branche pull request gönderin.

Kolay gelsin!