import requests
import hashlib
import os
import time
import json
import logging

# Професійне логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- ОТРИМУЄМО НАЛАШТУВАННЯ З GITHUB SECRETS ---
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
SOLARMAN_APP_ID = os.environ.get("SOLARMAN_APP_ID")
SOLARMAN_APP_SECRET = os.environ.get("SOLARMAN_APP_SECRET")
SOLARMAN_EMAIL = os.environ.get("SOLARMAN_EMAIL")
SOLARMAN_PASSWORD = os.environ.get("SOLARMAN_PASSWORD")
DEVICE_SN = os.environ.get("DEVICE_SN")

API_URL = "https://eu1-developer.deyecloud.com"

# ТВОЯ НОВА НАДІЙНА БАЗА ДАНИХ
JSONBLOB_ID = "019d1fde-f71e-7530-83fb-a58fe38ac1c7"
STORAGE_URL = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"

def send_telegram_message(text, silent=False):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_notification": silent}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Помилка відправки в Telegram: {e}")

# --- РОБОТА З НОВОЮ БАЗОЮ JSONBLOB ---
def get_state():
    default_state = {"state": 0, "token": "", "token_time": 0, "last_soc": 100.0, "last_soc_time": time.time()}
    try:
        res = requests.get(STORAGE_URL, timeout=10)
        if res.status_code == 200:
            data = res.json()
            # Якщо база зовсім порожня {}, підставляємо значення за замовчуванням
            if not data:
                return default_state
            return data
    except Exception as e:
        logging.warning(f"Помилка читання JSONBlob: {e}")
    return default_state

def save_state(state_dict):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    for attempt in range(3):
        try:
            res = requests.put(STORAGE_URL, json=state_dict, headers=headers, timeout=10)
            res.raise_for_status() 
            logging.info("Пам'ять бота успішно оновлено та збережено в JSONBlob!")
            return
        except Exception as e:
            logging.warning(f"Помилка запису в JSONBlob (спроба {attempt+1}/3): {e}")
        time.sleep(3)
    logging.error("КРИТИЧНО: Не вдалося зберегти стан.")

# --- ЛОГІКА API DEYE ---
def fetch_new_token():
    if not SOLARMAN_PASSWORD: return None
    pwd_hash = hashlib.sha256(SOLARMAN_PASSWORD.encode('utf-8')).hexdigest()
    auth_url = f"{API_URL}/v1.0/account/token?appId={SOLARMAN_APP_ID}"
    payload = {"appSecret": SOLARMAN_APP_SECRET, "email": SOLARMAN_EMAIL, "password": pwd_hash}
    try:
        res = requests.post(auth_url, json=payload, timeout=10).json()
        if res.get("success"):
            return res.get("accessToken", "")
    except Exception as e:
        logging.error(f"Помилка генерації токена: {e}")
    return None

def fetch_soc_data(token):
    if not token: return None
    url = f"{API_URL}/v1.0/device/latest?appId={SOLARMAN_APP_ID}"
    auth_header = token if token.lower().startswith("bearer") else f"Bearer {token}"
    headers = {"Authorization": auth_header, "Content-Type": "application/json"}
    payload = {"deviceList": [DEVICE_SN]}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10).json()
        if not res.get("success"):
            return "AUTH_ERROR"
            
        data_list = res.get("deviceDataList", [])
        if not data_list: return None
        device_data = data_list[0]
        if str(device_data.get("deviceState", "")) == "2": return None
            
        for item in device_data.get("dataList", []):
            key = str(item.get("key", "")).upper()
            if key in ["SOC", "BATTERY_SOC", "BMS_SOC"]:
                return float(item.get("value", 100))
        return None
    except Exception as e:
        logging.error(f"Помилка запиту даних: {e}")
        return None

def get_battery_soc_with_retry(state, max_retries=3, delay=15):
    for attempt in range(max_retries):
        token = state.get("token", "")
        token_time = state.get("token_time", 0)
        
        if not token or (time.time() - token_time) > 43200:
            logging.info("Отримуємо новий токен...")
            token = fetch_new_token()
            if token:
                state["token"] = token
                state["token_time"] = time.time()
                
        if token:
            soc = fetch_soc_data(token)
            if soc == "AUTH_ERROR":
                logging.info("Токен відхилено. Оновлюємо...")
                state["token"] = "" 
                continue
            elif soc is not None:
                return soc
                
        logging.warning(f"API Deye не відповів (спроба {attempt+1}/3). Чекаємо {delay} сек...")
        if attempt < max_retries - 1:
            time.sleep(delay)
            
    return "OFFLINE"

# --- ГОЛОВНА ЛОГІКА ---
def main():
    state = get_state()
    current_state_level = state.get("state", 0)
    
    soc = get_battery_soc_with_retry(state)
    logging.info(f"Отримано SOC: {soc}, Поточний рівень тривоги: {current_state_level}")

    if soc == "OFFLINE":
        if current_state_level != 4:
            msg = (f"⚠️ <b>Увага! Втрачено зв'язок з інвертором ліфта.</b>\n\n"
                   f"Дані про заряд не оновлюються (можливо, зник інтернет або живлення роутера). "
                   f"Будь ласка, будьте обережні з ліфтом!")
            send_telegram_message(msg)
            state["state"] = 4
        save_state(state)
        return

    if soc <= 30 and current_state_level != 3:
        msg = (f"🔴 ⛔️ <b>КРИТИЧНИЙ ЗАРЯД ({soc}%)! НЕ СІДАЙТЕ В ЛІФТ!</b> ⛔️\n\n"
               f"Є високий ризик зупинки кабіни між поверхами.")
        send_telegram_message(msg, silent=False)
        state["state"] = 3

    elif 30 < soc <=
