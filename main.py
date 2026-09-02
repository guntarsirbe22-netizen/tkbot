import requests
import time
import json
import os
import re

# ==================== KONFIGURĀCIJA ====================
DISCORD_WEBHOOK_URL = "https://discord.com"

TIKTOK_USERS = ["gun4atrakias", "sirmais28", "salvixs18"]

# Render serverim 5 minūtes ir ideāls laiks
CHECK_INTERVAL = 300
# =======================================================

STATUS_FILE = "live_status.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=4, ensure_ascii=False)

def get_tiktok_avatar(html_text):
    default_avatar = "https://stickpng.com"
    try:
        match = re.search(r'"avatarLarger":"([^"]+)"', html_text)
        if match:
            avatar_url = match.group(1).replace(r"\u002F", "/")
            return avatar_url
    except Exception:
        pass
    return default_avatar

def check_live():
    current_status = load_status()
    print("🔄 Pārbaudu TikTok tiešraižu statusus...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://google.com"
    }

    for user in TIKTOK_USERS:
        # SAITE PILNĪBĀ IZLABOTA UN PĀRBAUDĪTA
        url = f"https://tiktok.com@{user}/live"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            
            is_currently_live = '"roomId":"' in response.text or 'ROOM_STATUS_LIVING' in response.text
            was_live = current_status.get(user, False)

            if is_currently_live and not was_live:
                print(f"🚨 {user} IR IEGĀJIS LIVE!")
                user_avatar = get_tiktok_avatar(response.text)
                
                payload = {
                    "username": f"{user} LIVE",
                    "avatar_url": user_avatar,
                    "embeds": [
                        {
                            "title": "🔴 TIEŠRAIDE IR SĀKUSIES!",
                            "description": f"**{user}** nupat uzsāka LIVE strīmu vietnē TikTok!\n\n👉 [KLIKŠĶINI ŠEIT, LAI SKATĪTOS](https://tiktok.com@{user}/live)",
                            "color": 16711711,
                            "thumbnail": {
                                "url": user_avatar
                            },
                            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                        }
                    ]
                }
                requests.post(DISCORD_WEBHOOK_URL, json=payload)
                current_status[user] = True

            elif not is_currently_live and was_live:
                print(f"🛑 {user} pabeidza tiešraidi.")
                current_status[user] = False
            else:
                if is_currently_live:
                    print(f"🎥 {user} joprojām turpina strīmot.")
                else:
                    print(f"💤 {user} pašlaik nav tiešraidē (guļ).")
                current_status[user] = is_currently_live

        except Exception as e:
            print(f"⚠️ Kļūda, mēģinot pārbaudīt lietotāju {user}: {e}")

    save_status(current_status)

if __name__ == "__main__":
    print("🤖 TikTok LIVE bots uz Render servera ir palaists!")
    while True:
        check_live()
        time.sleep(CHECK_INTERVAL)
