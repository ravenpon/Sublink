"""
اسکریپت جمع‌آوری خودکار کانفیگ از کانال‌های عمومی تلگرام + تغییر اسم هر کانفیگ به فرمت اختصاصی:
🇩🇪 | RAV VPN • Germany ⚡️
"""

import base64
import json
import os
import re
import socket
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# اطلاعات اتصال تلگرام از Secrets گیت‌هاب خونده می‌شه
TG_API_ID = int(os.environ["TG_API_ID"])
TG_API_HASH = os.environ["TG_API_HASH"]
TG_SESSION = os.environ["TG_SESSION"]

TELEGRAM_CHANNELS = [
    "UnlimitConfig", "persianvpnhub", "proxy_kafee", "YamYamProxy",
    "JavidanNet", "ConfigFast", "Zed_NetMeli", "erfanandroid",
    "configshere", "cpy_teeL", "MARAMBASHI", "meliproxyy",
    "SRCVPN", "anty_filter", "DailyV2Proxy", "TheFreeConfigs",
    "OpenVpnUser", "Proxy_Station", "GH_v2rayng", "Net2Ray",
    "FreakConfig", "configraygan", "V2RAYROZ", "G0Dv2ray",
    "YamYamProxy2", "chat_naakon", "chat_nakoni", "directvvbh",
    "prrofile_purple", "NPV_78", "vpnplusee_free", "v2ray_free_conf",
    "vpns", "canfigv2ray", "v2ray26", "filembad", "TAK_VPN12",
    "V2rayEnglishGP", "canfige", "OmegaGR", "Dr_Npv", "v2ray_proxyz",
    "Badangellll",
]

MESSAGES_PER_CHANNEL = 80  # چند پیام آخر هر کانال بررسی بشه

MAX_CONFIGS = 100
RAW_POOL_SIZE = 500  # قبل از تست پینگ، این تعداد رو بررسی می‌کنیم تا بعد از حذف سرورهای خراب، به MAX_CONFIGS برسیم
PING_TIMEOUT = 3
PING_WORKERS = 40
VALID_PREFIXES = ("vless://", "vmess://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://")
BRAND_FORMAT = "{flag} | RAV VPN • {country} ⚡️"

# این کانفیگ نمایشی هیچ‌وقت وصل نمی‌شه، فقط به‌عنوان یادآوری همیشه ردیف اول لیست می‌مونه
PINNED_NOTICE_CONFIG = (
    "vless://00000000-0000-0000-0000-000000000000@127.0.0.1:1"
    "?security=none&type=tcp"
    "#%E2%9A%A0%EF%B8%8F%20%D9%87%D8%B1%20%D9%86%DB%8C%D9%85%20%D8%B3%D8%A7%D8%B9%D8%AA"
    "%20%D8%A2%D9%BE%D8%AF%DB%8C%D8%AA%20%DA%A9%D9%86%DB%8C%D8%AF%20%E2%9A%A0%EF%B8%8F"
)

CONFIG_REGEX = re.compile(
    r"(?:vless|vmess|trojan|ss|ssr|hysteria2|hy2|tuic)://[^\s`\"'<>]+"
)


def fetch_from_telegram() -> list[str]:
    """از لیست کانال‌های تلگرام، آخرین پیام‌ها رو می‌خونه و کانفیگ‌ها رو استخراج می‌کنه."""
    configs: list[str] = []
    with TelegramClient(StringSession(TG_SESSION), TG_API_ID, TG_API_HASH) as client:
        for channel in TELEGRAM_CHANNELS:
            try:
                count = 0
                for message in client.iter_messages(channel, limit=MESSAGES_PER_CHANNEL):
                    if not message.text:
                        continue
                    found = CONFIG_REGEX.findall(message.text)
                    configs.extend(found)
                    count += len(found)
                print(f"✅ {count} کانفیگ از @{channel}")
            except Exception as e:
                print(f"⚠️  خطا تو کانال @{channel}: {e}")
    return configs


def get_host(line: str):
    """آدرس سرور رو از هر نوع کانفیگ استخراج می‌کنه (برای پیدا کردن کشور و تست اتصال)."""
    scheme = line.split("://")[0]
    if scheme == "vmess":
        try:
            b64 = line[len("vmess://"):]
            padded = b64 + "=" * (-len(b64) % 4)
            data = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
            return data.get("add")
        except Exception:
            return None
    match = re.search(r"@([^:/?#]+)", line)
    return match.group(1) if match else None


def get_port(line: str):
    """پورت سرور رو از هر نوع کانفیگ استخراج می‌کنه."""
    scheme = line.split("://")[0]
    if scheme == "vmess":
        try:
            b64 = line[len("vmess://"):]
            padded = b64 + "=" * (-len(b64) % 4)
            data = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
            return int(data.get("port", 443))
        except Exception:
            return None
    match = re.search(r"@[^:/?#]+:(\d+)", line)
    return int(match.group(1)) if match else None


def check_alive(host: str, port: int) -> bool:
    """با یه اتصال TCP ساده بررسی می‌کنه سرور بالاست یا نه."""
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, port), timeout=PING_TIMEOUT):
            return True
    except Exception:
        return False


def filter_alive(configs: list[str]) -> list[str]:
    """موازی همه کانفیگ‌ها رو تست می‌کنه و فقط سرورهای زنده رو نگه می‌داره."""
    alive = []
    with ThreadPoolExecutor(max_workers=PING_WORKERS) as executor:
        futures = {}
        for line in configs:
            host, port = get_host(line), get_port(line)
            futures[executor.submit(check_alive, host, port)] = line
        for future in as_completed(futures):
            if future.result():
                alive.append(futures[future])
    return alive


def flag_emoji(country_code: str) -> str:
    if not country_code or len(country_code) != 2:
        return "🌐"
    code = country_code.upper()
    return chr(0x1F1E6 + ord(code[0]) - 65) + chr(0x1F1E6 + ord(code[1]) - 65)


def geolocate_hosts(hosts: list[str]) -> dict:
    """با سرویس رایگان ip-api.com، کشور هر هاست رو دسته‌جمعی پیدا می‌کنه."""
    unique_hosts = list(dict.fromkeys(hosts))
    result = {}
    for i in range(0, len(unique_hosts), 100):
        batch = unique_hosts[i:i + 100]
        try:
            resp = requests.post(
                "http://ip-api.com/batch?fields=query,countryCode,country",
                json=[{"query": h} for h in batch],
                timeout=20,
            )
            resp.raise_for_status()
            for item in resp.json():
                if item.get("countryCode"):
                    result[item["query"]] = (item["countryCode"], item.get("country", item["countryCode"]))
        except Exception as e:
            print(f"⚠️  خطا تو GeoIP دسته {i}: {e}")
    return result


def rename_config(line: str, flag: str, country: str) -> str:
    tag = BRAND_FORMAT.format(flag=flag, country=country)
    scheme = line.split("://")[0]
    if scheme == "vmess":
        try:
            b64 = line[len("vmess://"):]
            padded = b64 + "=" * (-len(b64) % 4)
            data = json.loads(base64.b64decode(padded).decode("utf-8", errors="ignore"))
            data["ps"] = tag
            new_b64 = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
            return f"vmess://{new_b64}"
        except Exception:
            return line
    base = line.split("#")[0]
    return f"{base}#{quote(tag, safe='')}"


def main():
    seen = set()
    all_configs: list[str] = []

    raw_configs = fetch_from_telegram()
    print(f"📥 مجموع {len(raw_configs)} کانفیگ خام از {len(TELEGRAM_CHANNELS)} کانال گرفته شد.")

    for line in raw_configs:
        line = line.strip()
        if not line.startswith(VALID_PREFIXES):
            continue
        key = line.split("#")[0]
        if key not in seen:
            seen.add(key)
            all_configs.append(line)

    if not all_configs:
        print("❌ هیچ کانفیگی گرفته نشد، فایل‌ها دست‌نخورده می‌مونن.")
        return

    candidate_pool = all_configs[:RAW_POOL_SIZE]
    print(f"🔎 در حال تست اتصال {len(candidate_pool)} کانفیگ...")
    alive_configs = filter_alive(candidate_pool)
    print(f"💚 {len(alive_configs)} کانفیگ زنده از {len(candidate_pool)} تا پیدا شد.")

    if not alive_configs:
        print("❌ هیچ سرور زنده‌ای پیدا نشد، فایل‌ها دست‌نخورده می‌مونن.")
        return

    final_list = alive_configs[:MAX_CONFIGS]

    # پیدا کردن کشور هر سرور
    hosts = [get_host(line) for line in final_list]
    geo_map = geolocate_hosts([h for h in hosts if h])

    renamed = []
    for line, host in zip(final_list, hosts):
        if host and host in geo_map:
            code, country = geo_map[host]
            renamed.append(rename_config(line, flag_emoji(code), country))
        else:
            renamed.append(rename_config(line, "🌐", "Unknown"))

    output = "\n".join(renamed) + "\n"
    final_output = PINNED_NOTICE_CONFIG + "\n" + output
    with open("RAVVPN2", "w", encoding="utf-8") as f:
        f.write(final_output)
    with open("RVVPN", "w", encoding="utf-8") as f:
        f.write(final_output)

    print(f"🎉 مجموع {len(renamed)} کانفیگ زنده و با اسم اختصاصی ذخیره شد.")


if __name__ == "__main__":
    main()
