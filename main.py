import requests
import json
import os
import re
from datetime import datetime, timezone

# ============================================================
#                       KONFIGURĀCIJA
# ============================================================

# Discord webhook no GitHub Secrets / Environment variables
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# TikTok lietotāji, kurus uzraudzīt
TIKTOK_USERS = [
    "gun4atrakias",
    "sirmais28",
    "salvixs18"
]

# Statusa fails
STATUS_FILE = "live_status.json"

# HTTP timeout
REQUEST_TIMEOUT = 20


# ============================================================
#                       HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1"
})


# ============================================================
#                   STATUSA SAGLABĀŠANA
# ============================================================

def load_status():
    """
    Ielādē iepriekš saglabāto LIVE statusu.
    """

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
    """
    Saglabā pašreizējo LIVE statusu.
    """

    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                status,
                f,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:
        print(f"⚠️ Neizdevās saglabāt {STATUS_FILE}: {e}")


# ============================================================
#                   AVATAR MEKLĒŠANA
# ============================================================

def get_tiktok_avatar(html_text):
    """
    Mēģina atrast TikTok lietotāja profila bildi HTML/JSON datos.
    """

    if not html_text:
        return None

    patterns = [
        r'"avatarLarger"\s*:\s*"([^"]+)"',
        r'"avatarMedium"\s*:\s*"([^"]+)"',
        r'"avatarThumb"\s*:\s*"([^"]+)"',
        r'"avatar_300x300"\s*:\s*"([^"]+)"',
        r'"avatar_168x168"\s*:\s*"([^"]+)"'
    ]

    for pattern in patterns:
        match = re.search(pattern, html_text)

        if match:
            avatar_url = match.group(1)

            avatar_url = (
                avatar_url
                .replace("\\u002F", "/")
                .replace("\\/", "/")
                .replace("\\u0026", "&")
                .replace("\\u003D", "=")
            )

            return avatar_url

    return None


def get_user_avatar(user):
    """
    Iegūst lietotāja TikTok profila bildi.
    """

    profile_url = f"https://www.tiktok.com/@{user}"

    try:
        response = session.get(
            profile_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        if response.status_code == 200:
            avatar = get_tiktok_avatar(response.text)

            if avatar:
                print(f"🖼️ @{user} profila bilde atrasta.")
                return avatar

        print(
            f"⚠️ Neizdevās iegūt @{user} profila bildi "
            f"(HTTP {response.status_code})"
        )

    except requests.RequestException as e:
        print(f"⚠️ Avatara kļūda @{user}: {e}")

    return None


# ============================================================
#                   LIVE STATUSA NOTEIKŠANA
# ============================================================

def check_tiktok_live(user):
    """
    Pārbauda, vai TikTok lietotājs pašlaik ir LIVE.

    Atgriež:
        True  = LIVE
        False = OFFLINE
        None  = statusu nevarēja droši noteikt
    """

    live_url = f"https://www.tiktok.com/@{user}/live"

    try:
        response = session.get(
            live_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

    except requests.Timeout:
        print(f"⚠️ TikTok pieprasījums @{user} pārsniedza timeout.")
        return None

    except requests.RequestException as e:
        print(f"⚠️ TikTok pieprasījuma kļūda @{user}: {e}")
        return None

    print(
        f"🌐 TikTok HTTP: {response.status_code} | "
        f"URL: {response.url}"
    )

    # --------------------------------------------------------
    # TikTok rate-limit vai bloķēšana
    # --------------------------------------------------------

    if response.status_code in (403, 429):
        print(
            f"⚠️ TikTok bloķēja/ierobežoja @{user} pārbaudi "
            f"(HTTP {response.status_code})."
        )
        return None

    # Servera kļūda
    if response.status_code >= 500:
        print(
            f"⚠️ TikTok servera kļūda @{user}: "
            f"HTTP {response.status_code}"
        )
        return None

    # Profils/lapa nav atrasta
    if response.status_code == 404:
        return False

    if response.status_code != 200:
        print(
            f"⚠️ Nezināma TikTok atbilde @{user}: "
            f"HTTP {response.status_code}"
        )
        return None

    html = response.text

    if not html:
        print(f"⚠️ Tukša TikTok atbilde @{user}.")
        return None

    html_lower = html.lower()
    final_url = response.url.lower()

    # --------------------------------------------------------
    # CAPTCHA / login / challenge
    # --------------------------------------------------------

    blocked_markers = [
        "/login",
        "/captcha",
        "/challenge",
        "verify to continue",
        "security verification"
    ]

    for marker in blocked_markers:
        if marker in final_url:
            print(
                f"⚠️ TikTok novirzīja @{user} uz "
                f"pārbaudes/login lapu."
            )
            return None

    # --------------------------------------------------------
    # Spēcīgi LIVE indikatori
    # --------------------------------------------------------

    live_patterns = [
        r'"status"\s*:\s*2(?:,|\})',
        r'"isLive"\s*:\s*true',
        r'"is_live"\s*:\s*true',
        r'ROOM_STATUS_LIVING',
        r'"roomStatus"\s*:\s*2',
        r'"room_status"\s*:\s*2'
    ]

    for pattern in live_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            print(f"🔴 LIVE indikators atrasts @{user}: {pattern}")
            return True

    # --------------------------------------------------------
    # Room ID + LIVE lapas pārbaude
    # --------------------------------------------------------

    room_patterns = [
        r'"roomId"\s*:\s*"([1-9][0-9]{5,})"',
        r'"room_id"\s*:\s*"([1-9][0-9]{5,})"',
        r'"roomId"\s*:\s*([1-9][0-9]{5,})',
        r'"room_id"\s*:\s*([1-9][0-9]{5,})'
    ]

    room_id = None

    for pattern in room_patterns:
        match = re.search(pattern, html)

        if match:
            room_id = match.group(1)
            break

    if room_id:
        print(f"🏠 @{user} atrasts TikTok room ID: {room_id}")

        # Room ID kopā ar LIVE marķieriem ir labs indikators
        live_context_markers = [
            "live-player",
            "liveplayer",
            "live_room",
            "liveroom",
            "webcast"
        ]

        for marker in live_context_markers:
            if marker in html_lower:
                print(
                    f"🔴 @{user} LIVE telpa apstiprināta "
                    f"(room ID: {room_id})"
                )
                return True

    # --------------------------------------------------------
    # Ja TikTok novirzīja /live uz parasto profilu
    # --------------------------------------------------------

    expected_live_path = f"/@{user.lower()}/live"

    if expected_live_path not in final_url:
        print(
            f"💤 TikTok /live lapa @{user} novirzīta uz "
            f"{response.url}"
        )
        return False

    # LIVE indikatori netika atrasti
    print(f"💤 @{user} LIVE indikatori netika atrasti.")
    return False


# ============================================================
#                   DISCORD PAZIŅOJUMS
# ============================================================

def send_discord_notification(user, avatar_url=None):
    """
    Nosūta Discord Embed paziņojumu par jaunu TikTok LIVE.
    """

    if not DISCORD_WEBHOOK_URL:
        print("")
        print("❌ DISCORD_WEBHOOK_URL nav atrasts!")
        print("👉 Pārbaudi GitHub → Settings → Secrets and variables → Actions")
        print("")
        return False

    tiktok_url = f"https://www.tiktok.com/@{user}/live"

    timestamp = datetime.now(timezone.utc).isoformat()

    description_text = (
        f"📣 **@{user}** pašlaik ir tiešraidē TikTok!\n\n"
        f"🚜 **Nāc un pievienojies saimniecībai!**\n\n"
        f"👉 **[SKATĪTIES TIEŠRAIDI]({tiktok_url})**\n\n"
        f"🌾 Skaties strīmu, čato un atbalsti mūsējos!"
    )

    embed = {
        "title": "🔴 TIEŠRAIDE IR SĀKUSIES!",
        "url": tiktok_url,
        "description": description_text,

        # Sarkana krāsa
        "color": 15158332,

        "timestamp": timestamp,

        "fields": [
            {
                "name": "👤 TikTok",
                "value": f"[@{user}]({tiktok_url})",
                "inline": True
            },
            {
                "name": "📡 Statuss",
                "value": "🔴 LIVE",
                "inline": True
            }
        ],

        "footer": {
            "text": "Farming Vidzeme • TikTok LIVE Alerts"
        }
    }

    # Ja TikTok bilde atrasta
    if avatar_url:
        embed["thumbnail"] = {
            "url": avatar_url
        }

    payload = {
        "username": "Farming Vidzeme Alerts",
        "embeds": [embed],
        "allowed_mentions": {
            "parse": []
        }
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

    except requests.Timeout:
        print("❌ Discord webhook timeout.")
        return False

    except requests.RequestException as e:
        print(f"❌ Discord webhook kļūda: {e}")
        return False

    if 200 <= response.status_code < 300:
        print("")
        print("✅ =============================================")
        print(f"✅ Discord LIVE paziņojums nosūtīts par @{user}")
        print("✅ =============================================")
        print("")
        return True

    print(
        f"❌ Discord webhook kļūda: "
        f"HTTP {response.status_code}"
    )

    if response.text:
        print(f"Discord atbilde: {response.text[:500]}")

    return False


# ============================================================
#                     LIETOTĀJU PĀRBAUDE
# ============================================================

def check_all_users():
    """
    Pārbauda visus TikTok lietotājus vienu reizi.
    """

    current_status = load_status()

    print("")
    print("=" * 65)
    print("🔄 PĀRBAUDU TIKTOK TIEŠRAIDES")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 65)

    for user in TIKTOK_USERS:

        print("")
        print("-" * 65)
        print(f"👤 Pārbaudu @{user}")
        print("-" * 65)

        previous_status = bool(
            current_status.get(user, False)
        )

        print(
            f"📁 Iepriekšējais statuss: "
            f"{'LIVE' if previous_status else 'OFFLINE'}"
        )

        live_status = check_tiktok_live(user)

        # ----------------------------------------------------
        # Nevarējām droši noteikt
        # ----------------------------------------------------

        if live_status is None:

            print(
                f"⚠️ @{user} statusu nevarēja droši noteikt."
            )

            print(
                "ℹ️ Saglabāju iepriekšējo statusu, "
                "lai nerastos viltus paziņojumi."
            )

            continue

        # ----------------------------------------------------
        # JAUNS LIVE
        # ----------------------------------------------------

        if live_status is True and previous_status is False:

            print("")
            print(f"🚨 @{user} IR IEGĀJIS LIVE!")
            print("📣 Gatavoju Discord paziņojumu...")

            avatar_url = get_user_avatar(user)

            notification_sent = send_discord_notification(
                user,
                avatar_url
            )

            # Statusu uz LIVE mainām tikai tad,
            # ja Discord paziņojums tiešām nosūtījās.
            #
            # Ja webhook neizdodas, nākamajā cron reizē
            # bots mēģinās vēlreiz.
            if notification_sent:
                current_status[user] = True
            else:
                print(
                    f"⚠️ @{user} ir LIVE, bet Discord "
                    f"paziņojums neizdevās."
                )

                current_status[user] = False

        # ----------------------------------------------------
        # JOPROJĀM LIVE
        # ----------------------------------------------------

        elif live_status is True and previous_status is True:

            print(
                f"🎥 @{user} joprojām ir LIVE."
            )

            print(
                "🔕 Jauns Discord paziņojums netiks sūtīts."
            )

            current_status[user] = True

        # ----------------------------------------------------
        # LIVE BEIDZIES
        # ----------------------------------------------------

        elif live_status is False and previous_status is True:

            print(
                f"🛑 @{user} pabeidza tiešraidi."
            )

            current_status[user] = False

        # ----------------------------------------------------
        # OFFLINE
        # ----------------------------------------------------

        else:

            print(
                f"💤 @{user} pašlaik nav tiešraidē."
            )

            current_status[user] = False

    save_status(current_status)

    print("")
    print("=" * 65)
    print("💾 STATUSS SAGLABĀTS")
    print("=" * 65)

    for user in TIKTOK_USERS:

        status = current_status.get(user, False)

        print(
            f"{'🔴' if status else '⚫'} "
            f"@{user}: "
            f"{'LIVE' if status else 'OFFLINE'}"
        )

    print("=" * 65)


# ============================================================
#                       GALVENĀ FUNKCIJA
# ============================================================

def main():

    print("")
    print("🤖 Farming Vidzeme")
    print("📡 TikTok LIVE → Discord")
    print("⚙️ Cron režīms")
    print("=" * 65)

    if not DISCORD_WEBHOOK_URL:
        print("")
        print("❌ UZMANĪBU!")
        print("DISCORD_WEBHOOK_URL nav atrasts Environment Variables.")
        print("")
        print(
            "GitHub Actions gadījumā tam jābūt "
            "GitHub Secret ar nosaukumu:"
        )
        print("")
        print("DISCORD_WEBHOOK_URL")
        print("")

    check_all_users()

    print("")
    print("🚀 Pārbaude pabeigta.")
    print("⏰ Skripts izslēdzas līdz nākamajai Cron palaišanai.")
    print("")


if __name__ == "__main__":
    main()
