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

# המרת ADMIN_USER_ID למספר אם קיים
if ADMIN_USER_ID:
    try:
        ADMIN_USER_ID = int(ADMIN_USER_ID)
    except ValueError:
        print("⚠️ ADMIN_USER_ID לא תקין, כולם יוכלו להשתמש בבוט")
        ADMIN_USER_ID = None
else:
    ADMIN_USER_ID = None
