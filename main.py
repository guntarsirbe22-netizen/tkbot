import requests
import json
import os
import re
from datetime import datetime, timezone
from html import unescape


# ============================================================
#                       KONFIGURĀCIJA
# ============================================================

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

TIKTOK_USERS = [
    "gun4atrakias",
    "sirmais28",
    "salvixs18"
]

STATUS_FILE = "live_status.json"

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
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "lv-LV,lv;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
})


# ============================================================
#                   STATUSA SAGLABĀŠANA
# ============================================================

def load_status():

    if not os.path.exists(STATUS_FILE):
        return {}

    try:

        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except (json.JSONDecodeError, OSError) as e:

        print(
            f"⚠️ Neizdevās nolasīt {STATUS_FILE}: {e}"
        )

    return {}


def save_status(status):

    try:

        temp_file = STATUS_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:

            json.dump(
                status,
                f,
                indent=4,
                ensure_ascii=False
            )

        os.replace(temp_file, STATUS_FILE)

    except OSError as e:

        print(
            f"⚠️ Neizdevās saglabāt {STATUS_FILE}: {e}"
        )


# ============================================================
#                 JSON / SIGI_STATE MEKLĒŠANA
# ============================================================

def extract_sigi_state(html):

    """
    Izvelk TikTok SIGI_STATE JSON.

    SVARĪGI:
    Mēs NEKAD vairs nemeklējam vienkārši
    '"status": 2' pa visu HTML.
    """

    if not html:
        return None

    patterns = [
        r'<script[^>]+id=["\']SIGI_STATE["\'][^>]*>(.*?)</script>',
        r'<script[^>]+id=["\']sigi-persisted-data["\'][^>]*>(.*?)</script>'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE | re.DOTALL
        )

        if not match:
            continue

        raw_json = match.group(1).strip()

        if not raw_json:
            continue

        raw_json = unescape(raw_json)

        try:

            data = json.loads(raw_json)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:

            # Dažkārt JSON ir papildus escapots
            try:

                cleaned = (
                    raw_json
                    .replace("\\/", "/")
                    .replace("\\u002F", "/")
                )

                data = json.loads(cleaned)

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                pass

    return None


# ============================================================
#               REKURSĪVA STATUSA MEKLĒŠANA
# ============================================================

def find_live_room_status(data):

    """
    Meklē tikai LiveRoom struktūrās.

    Atgriež:
        2       = LIVE
        cits    = OFFLINE / beigusies istaba
        None    = statusu nevarēja atrast
    """

    if not isinstance(data, dict):
        return None

    # --------------------------------------------------------
    # Precīzā TikTok SIGI_STATE struktūra
    # --------------------------------------------------------

    live_room = data.get("LiveRoom")

    if isinstance(live_room, dict):

        # LiveRoom.liveRoomStatus
        status = live_room.get("liveRoomStatus")

        if isinstance(status, (int, str)):

            try:
                return int(status)

            except (ValueError, TypeError):
                pass

        # LiveRoom.liveRoomUserInfo
        user_info = live_room.get(
            "liveRoomUserInfo"
        )

        if isinstance(user_info, dict):

            room = user_info.get("liveRoom")

            if isinstance(room, dict):

                status = room.get("status")

                if isinstance(status, (int, str)):

                    try:
                        return int(status)

                    except (ValueError, TypeError):
                        pass

            # Dažās TikTok versijās status atrodas user blokā
            user = user_info.get("user")

            if isinstance(user, dict):

                status = user.get("status")

                if isinstance(status, (int, str)):

                    try:
                        return int(status)

                    except (ValueError, TypeError):
                        pass

    # --------------------------------------------------------
    # CurrentRoom gadījumam
    # --------------------------------------------------------

    current_room = data.get("CurrentRoom")

    if isinstance(current_room, dict):

        status = current_room.get("status")

        if isinstance(status, (int, str)):

            try:
                return int(status)

            except (ValueError, TypeError):
                pass

    return None


# ============================================================
#                   AVATAR MEKLĒŠANA
# ============================================================

def get_avatar_from_sigi(data):

    if not isinstance(data, dict):
        return None

    try:

        live_room = data.get("LiveRoom", {})

        user_info = live_room.get(
            "liveRoomUserInfo",
            {}
        )

        user = user_info.get(
            "user",
            {}
        )

        avatar = (
            user.get("avatarLarger")
            or user.get("avatarMedium")
            or user.get("avatarThumb")
        )

        if avatar:
            return (
                avatar
                .replace("\\/", "/")
                .replace("\\u002F", "/")
                .replace("\\u0026", "&")
                .replace("\\u003D", "=")
            )

    except Exception:
        pass

    return None


def get_tiktok_avatar(html_text):

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

        match = re.search(
            pattern,
            html_text
        )

        if match:

            return (
                match.group(1)
                .replace("\\u002F", "/")
                .replace("\\/", "/")
                .replace("\\u0026", "&")
                .replace("\\u003D", "=")
            )

    return None


# ============================================================
#                 TIKTOK LIVE PĀRBAUDE
# ============================================================

def check_tiktok_live(user):

    """
    Droša TikTok LIVE pārbaude.

    True  = konkrētais lietotājs ir LIVE
    False = konkrētais lietotājs nav LIVE
    None  = TikTok atbildi nevar droši pārbaudīt
    """

    live_url = (
        f"https://www.tiktok.com/@{user}/live"
    )

    print(
        f"🌐 Pieprasu TikTok: {live_url}"
    )

    try:

        response = session.get(
            live_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

    except requests.Timeout:

        print(
            f"⚠️ TikTok timeout @{user}"
        )

        return None

    except requests.RequestException as e:

        print(
            f"⚠️ TikTok pieprasījuma kļūda @{user}: {e}"
        )

        return None

    print(
        f"🌐 HTTP {response.status_code} | "
        f"{response.url}"
    )

    # --------------------------------------------------------
    # TikTok bloķēšana / rate limit
    # --------------------------------------------------------

    if response.status_code in (403, 429):

        print(
            f"⚠️ TikTok bloķēja pieprasījumu @{user}"
        )

        return None

    if response.status_code >= 500:

        print(
            f"⚠️ TikTok servera kļūda @{user}"
        )

        return None

    if response.status_code == 404:

        print(
            f"❌ TikTok lietotājs @{user} nav atrasts."
        )

        return False

    if response.status_code != 200:

        print(
            f"⚠️ Nezināms TikTok HTTP statuss: "
            f"{response.status_code}"
        )

        return None

    html = response.text

    if not html:

        print(
            f"⚠️ TikTok atdeva tukšu HTML @{user}"
        )

        return None

    # --------------------------------------------------------
    # CAPTCHA / challenge
    # --------------------------------------------------------

    final_url = response.url.lower()

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
                f"login/challenge."
            )

            return None

    html_lower = html.lower()

    if (
        "captcha" in html_lower
        and "SIGI_STATE" not in html
    ):

        print(
            f"⚠️ TikTok CAPTCHA @{user}"
        )

        return None

    # --------------------------------------------------------
    # SIGI_STATE
    # --------------------------------------------------------

    sigi_state = extract_sigi_state(html)

    if sigi_state is not None:

        status = find_live_room_status(
            sigi_state
        )

        print(
            f"📊 @{user} LiveRoom status: {status}"
        )

        if status == 2:

            print(
                f"🔴 @{user} IR LIVE!"
            )

            return True

        if status is not None:

            print(
                f"💤 @{user} NAV LIVE "
                f"(status={status})"
            )

            return False

        print(
            f"ℹ️ @{user}: SIGI_STATE atrasts, "
            f"bet LiveRoom status nav pieejams."
        )

    else:

        print(
            f"⚠️ @{user}: SIGI_STATE nav atrasts."
        )

    # --------------------------------------------------------
    # ĻOTI SVARĪGI
    #
    # Ja nevaram droši noteikt LIVE,
    # NEKAD neatgriežam True.
    #
    # Tas pasargā no viltus Discord paziņojumiem.
    # --------------------------------------------------------

    print(
        f"⚠️ @{user}: LIVE statusu nevar droši noteikt."
    )

    return None


# ============================================================
#                  PROFILA BILDES IEGŪŠANA
# ============================================================

def get_user_avatar(user):

    profile_url = (
        f"https://www.tiktok.com/@{user}"
    )

    try:

        response = session.get(
            profile_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True
        )

        if response.status_code != 200:

            print(
                f"⚠️ Avataram HTTP "
                f"{response.status_code} @{user}"
            )

            return None

        sigi_state = extract_sigi_state(
            response.text
        )

        if sigi_state:

            avatar = get_avatar_from_sigi(
                sigi_state
            )

            if avatar:

                print(
                    f"🖼️ @{user} profila bilde atrasta."
                )

                return avatar

        avatar = get_tiktok_avatar(
            response.text
        )

        if avatar:

            print(
                f"🖼️ @{user} profila bilde atrasta."
            )

            return avatar

    except requests.RequestException as e:

        print(
            f"⚠️ Avatara kļūda @{user}: {e}"
        )

    return None


# ============================================================
#                   DISCORD PAZIŅOJUMS
# ============================================================

def send_discord_notification(
    user,
    avatar_url=None
):

    if not DISCORD_WEBHOOK_URL:

        print("")
        print(
            "❌ DISCORD_WEBHOOK_URL nav atrasts!"
        )
        print(
            "👉 GitHub → Settings → Secrets and variables "
            "→ Actions"
        )
        print("")

        return False

    tiktok_url = (
        f"https://www.tiktok.com/@{user}/live"
    )

    timestamp = (
        datetime.now(timezone.utc).isoformat()
    )

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

        "color": 15158332,

        "timestamp": timestamp,

        "fields": [

            {
                "name": "👤 TikTok",
                "value": (
                    f"[@{user}]({tiktok_url})"
                ),
                "inline": True
            },

            {
                "name": "📡 Statuss",
                "value": "🔴 LIVE",
                "inline": True
            }

        ],

        "footer": {
            "text": (
                "Farming Vidzeme • TikTok LIVE Alerts"
            )
        }
    }

    if avatar_url:

        embed["thumbnail"] = {
            "url": avatar_url
        }

    payload = {

        "username": "Farming Vidzeme Alerts",

        "embeds": [
            embed
        ],

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

        print(
            "❌ Discord webhook timeout."
        )

        return False

    except requests.RequestException as e:

        print(
            f"❌ Discord webhook kļūda: {e}"
        )

        return False

    if 200 <= response.status_code < 300:

        print("")
        print(
            "✅ ============================================="
        )
        print(
            f"✅ Discord LIVE paziņojums nosūtīts "
            f"par @{user}"
        )
        print(
            "✅ ============================================="
        )
        print("")

        return True

    print(
        f"❌ Discord webhook kļūda: "
        f"HTTP {response.status_code}"
    )

    if response.text:

        print(
            f"Discord atbilde: "
            f"{response.text[:500]}"
        )

    return False


# ============================================================
#                     LIETOTĀJU PĀRBAUDE
# ============================================================

def check_all_users():

    current_status = load_status()

    print("")
    print("=" * 65)
    print("🔄 PĀRBAUDU TIKTOK TIEŠRAIDES")
    print(
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
    print("=" * 65)

    for user in TIKTOK_USERS:

        print("")
        print("-" * 65)
        print(f"👤 Pārbaudu @{user}")
        print("-" * 65)

        previous_status = bool(
            current_status.get(
                user,
                False
            )
        )

        print(
            f"📁 Iepriekšējais statuss: "
            f"{'LIVE' if previous_status else 'OFFLINE'}"
        )

        live_status = check_tiktok_live(
            user
        )

        # ----------------------------------------------------
        # TikTok atbilde nav uzticama
        # ----------------------------------------------------

        if live_status is None:

            print(
                f"⚠️ @{user} statusu nevarēja "
                f"droši noteikt."
            )

            print(
                "ℹ️ Iepriekšējais statuss netiek mainīts."
            )

            continue

        # ----------------------------------------------------
        # JAUNS LIVE
        # ----------------------------------------------------

        if (
            live_status is True
            and previous_status is False
        ):

            print("")
            print(
                f"🚨 @{user} IR IEGĀJIS LIVE!"
            )

            print(
                "📣 Gatavoju Discord paziņojumu..."
            )

            avatar_url = get_user_avatar(
                user
            )

            notification_sent = (
                send_discord_notification(
                    user,
                    avatar_url
                )
            )

            if notification_sent:

                current_status[user] = True

            else:

                print(
                    f"⚠️ @{user} ir LIVE, "
                    f"bet Discord paziņojums neizdevās."
                )

                # Atstājam OFFLINE,
                # lai nākamajā reizē mēģinātu vēlreiz.
                current_status[user] = False

        # ----------------------------------------------------
        # JOPROJĀM LIVE
        # ----------------------------------------------------

        elif (
            live_status is True
            and previous_status is True
        ):

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

        elif (
            live_status is False
            and previous_status is True
        ):

            print(
                f"🛑 @{user} pabeidza tiešraidi."
            )

            current_status[user] = False

        # ----------------------------------------------------
        # OFFLINE
        # ----------------------------------------------------

        else:

            print(
                f"💤 @{user} pašlaik nav LIVE."
            )

            current_status[user] = False

    save_status(
        current_status
    )

    print("")
    print("=" * 65)
    print("💾 STATUSS SAGLABĀTS")
    print("=" * 65)

    for user in TIKTOK_USERS:

        status = bool(
            current_status.get(
                user,
                False
            )
        )

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
        print(
            "DISCORD_WEBHOOK_URL nav atrasts "
            "Environment Variables."
        )
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
    print(
        "⏰ Skripts izslēdzas līdz nākamajai Cron palaišanai."
    )
    print("")


if __name__ == "__main__":
    main()
