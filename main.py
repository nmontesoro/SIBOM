import tweepy
import time
from SIBOM import SIBOM

CONSUMER_KEY = 0
CONSUMER_SECRET = 1
ACCESS_TOKEN = 2
ACCESS_TOKEN_SECRET = 3
CITY_ID = "010d7db066434a8a"  # Mar del Plata, AR
last_id = 0

# Leo los keys desde un archivo
keys = []
with open("keys", "rt") as fp:
    for i in range(0, 4):
        # Elimino el '\n' al final
        keys.append(fp.readline()[:-1])

with open("id", "rt") as fp:
    last_id = int(fp.readline())

auth = tweepy.OAuthHandler(keys[CONSUMER_KEY], keys[CONSUMER_SECRET])
auth.set_access_token(keys[ACCESS_TOKEN], keys[ACCESS_TOKEN_SECRET])
api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

s = SIBOM("@BoletinMGP", "General Pueyrredón", r"general pueyrred.n",
          "assets/Montserrat-Regular.ttf", "assets/logo.png")
id = s.GetLatestID()

if id == 0:
    exit(1)
if id == last_id:
    print("No hay boletines nuevos.")
    exit(0)

with open("id", "wt") as fp:
    fp.write(str(id))

urls = s.GetAllURLs(id)
url_count = len(urls)
i = 1
for url in urls:
    print("Procesando URL %s de %s" % (i, url_count))
    tweets = s.ParsePublicacion(url).GetTweets()

    last_tweet_id = ""
    tw_count = len(tweets)
    j = 1
    for tweet in tweets:
        print("\n    Tweet %s de %s... " % (j, tw_count), end="")
        try:
            media_ids = []
            for filename in tweet.media_filenames:
                media_id = api.media_upload(filename).media_id
                media_ids.append(media_id)
            last_tweet = api.update_status(
                status=tweet.content, in_reply_to_status_id=last_tweet_id, media_ids=media_ids, place_id=CITY_ID)
            last_tweet_id = last_tweet.id
            print("Enviado")
        except Exception:
            print("ERROR!")
            pass
        # Espero 15s entre cada tweet, para no llenar el timeline de los
        # seguidores y evitar que marquen la cuenta como spam.
        j += 1
        time.sleep(15)
    # Espero 15s adicionales entre cada hilo
    i += 1
    time.sleep(15)
            
