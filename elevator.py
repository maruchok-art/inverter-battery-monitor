import requests
import hashlib

# --- НАЛАШТУВАННЯ ---
TG_BOT_TOKEN = "8659050146:AAFITUNhH7EszRBi6t7z_u0EBUTuNfnWcRQ"  
TG_CHAT_ID = "-1003504537820"     
SOLARMAN_APP_ID = "202603201120002"         
SOLARMAN_APP_SECRET = "33c41fc10f04d5f9facd577d34d56b36" 
SOLARMAN_EMAIL = "vitaliy.maruk@gmail.com"           
SOLARMAN_PASSWORD = "Maruk1985"
DEVICE_SN = "3586493872"    
API_URL = "https://api.deyecloud.com"

def main():
    pwd_hash = hashlib.sha256(SOLARMAN_PASSWORD.encode('utf-8')).hexdigest()
    try:
        # Отримуємо токен
        auth_url = f"{API_URL}/account/v1.0/token?appId={SOLARMAN_APP_ID}"
        auth_payload = {"appSecret": SOLARMAN_APP_SECRET, "email": SOLARMAN_EMAIL, "password": pwd_hash}
        auth_res = requests.post(auth_url, json=auth_payload, timeout=15).json()
        token = auth_res["access_token"]
        
        # Отримуємо дані
        data_url = f"{API_URL}/device/v1.0/currentData?appId={SOLARMAN_APP_ID}"
        headers = {"Authorization": f"Bearer {token}"}
        data_res = requests.post(data_url, headers=headers, json={"deviceSn": DEVICE_SN}, timeout=15).json()
        
        soc = 100
        for item in data_res.get("dataList", []):
            if item.get("key", "").upper() in ["SOC", "BATTERY_SOC", "BATTERY CAPACITY"]:
                soc = float(item.get("value", 100))
        
        # Надсилаємо в ТГ тільки при низькому заряді
        url_tg = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        if soc <= 30:
            msg = f"🔴 <b>КРИТИЧНИЙ ЗАРЯД ЛІФТА: {soc}%</b>\nНЕ СІДАЙТЕ В ЛІФТ!"
            requests.post(url_tg, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        elif soc <= 50:
            msg = f"🟠 <b>Заряд акумулятора ліфта: {soc}%</b>\nОбмежте використання."
            requests.post(url_tg, json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"})
        print(f"Check done. SOC: {soc}%")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
  
