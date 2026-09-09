import requests
import time
import json
import os
import re
from datetime import datetime, timezone

# ============================================================
#                 KONFIGURĀCIJA
# ============================================================

# DROŠĪBA: Kods automātiski paņem saiti no GitHub Secrets.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# TikTok lietotāji, kurus uzraudzīt. 
# Ja vēlies kādu pievienot vai dzēst, maini tikai šo sarakstu:
TIKTOK_USERS = [
    "gun4atrakias",
    "sirmais28",
    "salvixs18"
]

# Statusa fails, kurā bots atceras, vai strīmeris jau bija LIVE
STATUS_FILE = "live_status.json"

# HTTP timeout sekundēs
REQUEST_TIMEOUT = 15


# ============================================================
#                 STATUSA SAGLABĀŠANA
# ============================================================

def load_status():
    """Ielādē iepriekšējo LIVE statusu no faila."""
    if not os.path.exists(STATUS_FILE):
        return {}

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ Neizdevās nolasīt {STATUS_FILE}: {e}")

    return {}


def save_status(status):
    """Saglabā pašreizējo LIVE statusu failā."""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=4, ensure_ascii=False)
    except OSError as e:
        print(f"⚠️ Neizdevās saglabāt statusu: {e}")


# ============================================================
#                 TIKTOK DATU IEGŪŠANA
# ============================================================

def check_tiktok_live(user):
    """Pārbauda TikTok lietotāju, izmantojot drošu un nebloķējamu plūsmas metodi."""
    url = f"https://tiktok.com@{user}/live"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

    try:
        # Veicam pieprasījumu, neļaujot automātiski pāradresēt.
        # Ja lietotājs NAV live, TikTok pāradresē uz parasto profilu.
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=False)
        
        # SALABOTS: Pievienots pareizs skaitļu saraksts [301, 302]
        if response.status_code in:
            return False
            
        # Ja statuss ir 200, mēs esam iekšā LIVE istabā
        if response.status_code == 200:
            html = response.text
            # Pārbaudām zināmās TikTok LIVE pazīmes lapas saturā
            if "room_id" in html or "ROOM_STATUS_LIVING" in html or '"status":2' in html or "live-player" in html:
                return True
            if '"isLive":true' in html:
                return True

        return False

    except Exception as e:
        print(f"⚠️ Kļūda, pārbaudot @{user}: {e}")
        return None


def get_tiktok_avatar(html_text):
    """Mēģina atrast TikTok profila bildi HTML datos."""
    patterns = [
        r'"avatarLarger":"([^"]+)"',
        r'"avatarMedium":"([^"]+)"',
        r'"avatarThumb":"([^"]+)"'
    ]

    for pattern in patterns:
        try:
            match = re.search(pattern, html_text)
            if match:
                avatar_url = match.group(1)
                avatar_url = avatar_url.replace("\\u002F", "/")
                avatar_url = avatar_url.replace("\\/", "/")
                avatar_url = avatar_url.replace("\\u0026", "&")
                return avatar_url
        except Exception:
            pass
    return None


def get_user_avatar(user):
    """Iegūst TikTok lietotāja profila bildes adresi."""
    url = f"https://tiktok.com@{user}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return get_tiktok_avatar(response.text)
    except Exception:
        pass
    return None


# ============================================================
#                 DISCORD PAZIŅOJUMS
# ============================================================

def send_discord_notification(user, avatar_url=None):
    """Nosūta skaistu un modernu LIVE paziņojumu uz Discord."""
    if not DISCORD_WEBHOOK_URL:
        print("❌ Kļūda: DISCORD_WEBHOOK_URL nav atrasts GitHub Secrets iestatījumos!")
        return False

    tiktok_url = f"https://tiktok.com@{user}/live"
    timestamp = datetime.now(timezone.utc).isoformat()

    description_text = (
        f"📣 **{user}** pašlaik ir tiešraidē vietnē TikTok!\n\n"
        f"🚜 **Nāc un pievienojies saimniecībai:**\n"
        f"👉 [KLIKŠĶINI ŠEIT, LAI SKATĪTOS TIEŠRAIDI]({tiktok_url})\n\n"
        f"🌾 *Skaties strīmu, čato un atbalsti mūsējos!*"
    )

    embed = {
        "title": "🔴 TIEŠRAIDE IR SĀKUSIES!",
        "url": tiktok_url,
        "description": description_text,
        "color": 16657493,
        "timestamp": timestamp,
        "footer": {
            "text": "TikTok Live Alerts • Farming Vidzeme",
            "icon_url": "https://redditmedia.com"
        }
    }

    if avatar_url:
        embed["thumbnail"] = {"url": avatar_url}

    payload = {
        "username": "Farming Vidzeme Alerts",
        "avatar_url": "https://redditmedia.com",
        "embeds": [embed]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT)
        if 200 <= response.status_code < 300:
            print(f"✅ Skaistais Discord paziņojums nosūtīts par @{user}")
            return True
        print(f"❌ Discord webhook kļūda: HTTP {response.status_code}")
        return False
    except Exception as e:
        print(f"⚠️ Neizdevās nosūtīt paziņojumu: {e}")
        return False


# ============================================================
#                 VIENA PĀRBAUDES REIZE
# ============================================================

def check_all_users():
    """Pārbauda visus saraksta lietotājus tieši vienu reizi."""
    current_status = load_status()

    print("\n" + "="*60)
    print("🔄 Pārbaudu TikTok tiešraižu statusus...")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    for user in TIKTOK_USERS:
        print(f"\n👤 Pārbaudu @{user}...")
        previous_status = current_status.get(user, False)
        live_status = check_tiktok_live(user)

        if live_status is None:
            print(f"⚠️ @{user} statusu nevarēja noteikt.")
            continue

        if live_status and not previous_status:
            print(f"🚨 @{user} IR IEGĀJIS LIVE!")
            avatar_url = get_user_avatar(user)
            send_discord_notification(user, avatar_url)
            current_status[user] = True
        elif live_status and previous_status:
            print(f"🎥 @{user} joprojām turpina strīmot.")
            current_status[user] = True
        elif not live_status and previous_status:
            print(f"🛑 @{user} pabeidza tiešraidi.")
            current_status[user] = False
        else:
            print(f"💤 @{user} pašlaik nav tiešraidē.")
            current_status[user] = False

    save_status(current_status)
    print("\n💾 Statuss saglabāts.\n" + "="*60)


# ============================================================
#                 GALVENĀ PALAIŠANAS FUNKCIJA
# ============================================================

def main():
    print("\n🤖 TikTok LIVE → Discord bots (Cron režīms)")
    print("=" * 60)
    
    check_all_users()
    print("\n🚀 Pārbaude pabeigta, skripts izslēdzas līdz nākamajai plānotāja reizei.")


if __name__ == "__main__":
    main()
