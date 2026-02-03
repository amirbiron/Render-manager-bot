"""
ניהול הגדרות הבוט
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

# Render API
RENDER_API_KEY = os.getenv("RENDER_API_KEY")
RENDER_API_BASE = "https://api.render.com/v1"

# MongoDB
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "render_manager"

# בדיקת תקינות
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN חסר בקובץ .env")
if not RENDER_API_KEY:
    raise ValueError("RENDER_API_KEY חסר בקובץ .env")
if not MONGO_URI:
    raise ValueError("MONGO_URI חסר בקובץ .env")

# המרת ADMIN_USER_ID - תמיכה במספר מנהלים מופרדים בפסיקים
ADMIN_USER_IDS = []
if ADMIN_USER_ID:
    try:
        # אם יש פסיקים - זה רשימה של מנהלים
        if ',' in ADMIN_USER_ID:
            ADMIN_USER_IDS = [int(uid.strip()) for uid in ADMIN_USER_ID.split(',')]
        else:
            ADMIN_USER_IDS = [int(ADMIN_USER_ID)]
        print(f"✅ {len(ADMIN_USER_IDS)} מנהלים מורשים")
    except ValueError:
        print("⚠️ ADMIN_USER_ID לא תקין, כולם יוכלו להשתמש בבוט")
        ADMIN_USER_IDS = []
else:
    print("⚠️ ADMIN_USER_ID לא מוגדר, כולם יוכלו להשתמש בבוט")
    ADMIN_USER_IDS = []
