import requests
import hashlib
import time
import uuid

# --- НАЛАШТУВАННЯ ---
TG_BOT_TOKEN = "8659050146:AAFITUNhH7EszRBi6t7z_u0EBUTuNfnWcRQ"
TG_CHAT_ID = "-1003504537820"
APP_ID = "202603201120002"
APP_SECRET = "33c41fc10f04d5f9facd577d34d56b36"
EMAIL = "vitaliy.maruk@gmail.com"
PASSWORD = "Maruk1985"
DEVICE_SN = "3586493872"
API_URL = "https://openapi.deyecloud.com" # Офіційна адреса з вашого посилання
# -------------------------

def get_signature(params, secret):
    """Генерує підпис X-Sign згідно з документацією Deye"""
    sorted_params = sorted(params.items())
    query_string = "".join(f"{k}{v}" for k, v in sorted_params)
    sign_str = query_string + secret
    return hashlib.sha256(sign_str.encode('utf-8')).hexdigest()

def main():
    pwd_hash = hashlib.sha256(PASSWORD.encode('utf-8')).hexdigest()
    
    # 1. Авторизація (Отримання токена)
    timestamp = str(int(time.time()))
    nonce = str(uuid.uuid4())[:8]
    
    auth_params = {
        "appId": APP_ID,
        "timestamp": timestamp,
        "nonce": nonce,
        "email": EMAIL,
        "password": pwd_hash
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Sign": get_signature(auth_params, APP_SECRET),
        "X-Timestamp": timestamp,
        "X-Nonce": nonce
    }

    try:
        # Запит токена
        auth_res = requests.post(f"{API_URL}/account/v1.0/token", json=auth_params, headers=headers, timeout=15).json()
        if not auth_res.get("success"):
            print(f"Auth error: {auth_res}")
            return
        
        token = auth_res["access_token"]

        # 2. Отримання даних про заряд (SOC)
        data_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        data_payload = {"deviceSn": DEVICE_SN}
        data_res = requests.post(f"{API_URL}/device/v1.0/currentData", json=data_payload, headers=data_headers, timeout=15).json()
        
        soc = None
        for item in data_res.get("dataList", []):
            if item.get("key", "").upper() in ["SOC", "BATTERY_SOC", "BATTERY CAPACITY"]:
                soc = float(item.get("value"))
                break
        
        if soc is None:
            print("SOC not found in data list")
            return

        print(f"Check done. SOC: {soc}%")

        # 3. Надсилання в Telegram
        url_tg = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        if soc <= 30:
            msg = f"🔴 ⛔️ <b>КРИТИЧНИЙ ЗАРЯД ЛІФТА: {soc}%</b>\nНЕ СІДАЙТЕ В ЛІФТ!"
            requests.post(url_tg, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        elif soc <= 50:
            msg = f"🟠 <b>Заряд акумулятора ліфта: {soc}%</b>\nОбмежте використання."
            requests.post(url_tg, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    main()
