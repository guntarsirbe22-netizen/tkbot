import requests
import time
import json
import os
import re
from datetime import datetime, timezone

# ============================================================
#                 KONFIGURĀCIJA
# ============================================================

# IEVADI ŠEIT JAUNO DISCORD WEBHOOK URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1544706655386738719/hQiHukYZH_TvZ_8Kj1BUOEzmb6Ysm0XTT7G5WPCi0JHpTGH4hL7OkXv_qLMZIwLIjey9"

# TikTok lietotāji, kurus uzraudzīt
TIKTOK_USERS = [
    "gun4atrakias",
    "sirmais28",
    "salvixs18"
]

# Cik sekundes gaidīt starp pārbaudēm
CHECK_INTERVAL = 60

# Statusa fails
STATUS_FILE = "live_status.json"

# HTTP timeout
REQUEST_TIMEOUT = 15


# ============================================================
#                 STATUSA SAGLABĀŠANA
# ============================================================

def load_status():
    """Ielādē iepriekšējo LIVE statusu."""

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
    """Saglabā LIVE statusu failā."""

    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                status,
                f,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:
        print(f"⚠️ Neizdevās saglabāt statusu: {e}")


# ============================================================
#                 TIKTOK DATU IEGŪŠANA
# ============================================================

def get_tiktok_avatar(html_text):
    """Mēģina atrast TikTok profila bildi HTML/JSON datos."""

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

                # TikTok escaped URL
                avatar_url = avatar_url.replace("\\u002F", "/")
                avatar_url = avatar_url.replace("\\/", "/")
                avatar_url = avatar_url.replace("\\u0026", "&")

                return avatar_url

        except Exception:
            pass

    # Ja bildi neizdodas atrast
    return None


def check_tiktok_live(user):
    """
    Pārbauda konkrētu TikTok lietotāju.

    Atgriež:
        True  = LIVE
        False = nav LIVE
        None  = pārbaudi nevarēja veikt
    """

    # PAREIZA TikTok URL struktūra
    url = f"https://www.tiktok.com/@{user}/live"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,"
            "image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.google.com/"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        print(
            f"   HTTP: {response.status_code} | "
            f"{response.url}"
        )

        if response.status_code != 200:
            print(
                f"⚠️ TikTok atgrieza HTTP "
                f"{response.status_code} lietotājam @{user}"
            )

            return None

        html = response.text

        # ----------------------------------------------------
        # TikTok LIVE pazīmju pārbaude
        # ----------------------------------------------------

        live_indicators = [
            '"roomId":"',
            '"room_id":"',
            '"roomId":',
            '"room_id":',
            "ROOM_STATUS_LIVING",
            "LIVE_ROOM",
            '"status":2',
            '"status":1'
        ]

        is_live = any(
            indicator in html
            for indicator in live_indicators
        )

        # ----------------------------------------------------
        # Papildu pārbaude, lai mazinātu false positive
        # ----------------------------------------------------

        # Dažās TikTok lapās roomId var parādīties tikai
        # saistībā ar LIVE datiem.
        if '"roomId":"' in html:
            is_live = True

        if "ROOM_STATUS_LIVING" in html:
            is_live = True

        return is_live

    except requests.exceptions.Timeout:
        print(
            f"⏱️ Timeout, pārbaudot @{user}"
        )
        return None

    except requests.exceptions.RequestException as e:
        print(
            f"⚠️ TikTok pieprasījuma kļūda @{user}: {e}"
        )
        return None

    except Exception as e:
        print(
            f"⚠️ Nezināma kļūda @{user}: {e}"
        )
        return None


# ============================================================
#                 DISCORD PAZIŅOJUMS
# ============================================================

def send_discord_notification(user, avatar_url=None):
    """Nosūta LIVE paziņojumu Discord."""

    if (
        not DISCORD_WEBHOOK_URL
        or DISCORD_WEBHOOK_URL
        == "IEVIETO_SAVU_JAUNO_DISCORD_WEBHOOK"
    ):
        print(
            "❌ Discord webhook nav iestatīts!"
        )
        return False

    tiktok_url = (
        f"https://www.tiktok.com/@{user}/live"
    )

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    embed = {
        "title": "🔴 TIEŠRAIDE IR SĀKUSIES!",
        "description": (
            f"**{user}** nupat uzsāka LIVE strīmu "
            f"vietnē TikTok!\n\n"
            f"👉 [KLIKŠĶINI ŠEIT, LAI SKATĪTOS]({tiktok_url})"
        ),
        "color": 16711711,
        "timestamp": timestamp,
        "footer": {
            "text": "TikTok LIVE paziņojums"
        }
    }

    if avatar_url:
        embed["thumbnail"] = {
            "url": avatar_url
        }

    payload = {
        "username": f"{user} LIVE",
        "embeds": [embed]
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if 200 <= response.status_code < 300:
            print(
                f"✅ Discord paziņojums nosūtīts par @{user}"
            )
            return True

        print(
            f"❌ Discord webhook kļūda: "
            f"HTTP {response.status_code}"
        )

        if response.text:
            print(response.text[:500])

        return False

    except requests.exceptions.RequestException as e:
        print(
            f"⚠️ Neizdevās nosūtīt Discord paziņojumu: {e}"
        )
        return False


# ============================================================
#                 VIENA PĀRBAUDES REIZE
# ============================================================

def check_all_users():
    """Pārbauda visus TikTok lietotājus vienu reizi."""

    current_status = load_status()

    print()
    print("=" * 60)
    print(
        "🔄 Pārbaudu TikTok tiešraižu statusus..."
    )
    print(
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
    print("=" * 60)

    for user in TIKTOK_USERS:

        print()
        print(f"👤 Pārbaudu @{user}...")

        previous_status = current_status.get(
            user,
            False
        )

        live_status = check_tiktok_live(user)

        # ----------------------------------------------------
        # Ja pārbaude neizdevās
        # ----------------------------------------------------

        if live_status is None:
            print(
                f"⚠️ @{user} statusu nevarēja noteikt."
            )

            # SVARĪGI:
            # kļūdas gadījumā mēs NEmainām iepriekšējo
            # statusu, lai nejauši neizraisītu paziņojumu.
            continue

        # ----------------------------------------------------
        # LIVE SĀKUMS
        # ----------------------------------------------------

        if live_status and not previous_status:

            print(
                f"🚨 @{user} IR IEGĀJIS LIVE!"
            )

            # Lai iegūtu avataru, vēlreiz paņemam profila lapu.
            avatar_url = get_user_avatar(user)

            sent = send_discord_notification(
                user,
                avatar_url
            )

            # Statusu uz True iestatām arī tad, ja Discord
            # īslaicīgi neatbild, lai neizsūtītu spam.
            current_status[user] = True

        # ----------------------------------------------------
        # TURPINA LIVE
        # ----------------------------------------------------

        elif live_status and previous_status:

            print(
                f"🎥 @{user} joprojām turpina strīmot."
            )

            current_status[user] = True

        # ----------------------------------------------------
        # LIVE BEIGAS
        # ----------------------------------------------------

        elif not live_status and previous_status:

            print(
                f"🛑 @{user} pabeidza tiešraidi."
            )

            current_status[user] = False

        # ----------------------------------------------------
        # NAV LIVE
        # ----------------------------------------------------

        else:

            print(
                f"💤 @{user} pašlaik nav tiešraidē."
            )

            current_status[user] = False

    save_status(current_status)

    print()
    print("💾 Statuss saglabāts.")
    print("=" * 60)


# ============================================================
#                 AVATARA IEGŪŠANA
# ============================================================

def get_user_avatar(user):
    """Iegūst TikTok lietotāja profila bildi."""

    url = f"https://www.tiktok.com/@{user}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return get_tiktok_avatar(
                response.text
            )

    except Exception as e:
        print(
            f"⚠️ Neizdevās iegūt @{user} avataru: {e}"
        )

    return None


# ============================================================
#                 GALVENĀ CIKLA FUNKCIJA
# ============================================================

def main():

    print()
    print("🤖 TikTok LIVE → Discord bots")
    print("=" * 60)

    print("👥 Uzraugāmie lietotāji:")

    for user in TIKTOK_USERS:
        print(f"   • @{user}")

    print()
    print(
        f"⏱️ Pārbaude ik pēc {CHECK_INTERVAL} sekundēm."
    )

    print()
    print(
        "🚀 Bots ir palaists!"
    )

    # Pirmā pārbaude uzreiz
    check_all_users()

    # --------------------------------------------------------
    # Nepārtraukta darbība
    # --------------------------------------------------------

    while True:

        try:
            print()
            print(
                f"⏳ Nākamā pārbaude pēc "
                f"{CHECK_INTERVAL} sekundēm..."
            )

            time.sleep(CHECK_INTERVAL)

            check_all_users()

        except KeyboardInterrupt:

            print()
            print(
                "🛑 Bots apturēts ar Ctrl+C."
            )
            break

        except Exception as e:

            print()
            print(
                f"❌ Galvenā cikla kļūda: {e}"
            )

            print(
                "🔄 Bots turpinās darbu pēc "
                f"{CHECK_INTERVAL} sekundēm..."
            )

            time.sleep(CHECK_INTERVAL)


# ============================================================
#                 PALAIŠANA
# ============================================================

if __name__ == "__main__":
    main()
