# Render Manager Bot

בוט טלגרם לניהול שירותי Render - השעיה, המשך והפעלה מחדש של שירותים בלחיצת כפתור.

## התקנה

```bash
pip install -r requirements.txt
```

## הגדרה

צור קובץ `.env` עם המשתנים הבאים:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
RENDER_API_KEY=your_render_api_key_here
MONGO_URI=your_mongodb_connection_string
ADMIN_USER_ID=your_telegram_user_id
```

## הרצה

```bash
python bot.py
```

## פקודות

- `/start` - הודעת פתיחה
- `/manage` - רשימת כל השירותים
- `/add_service <service_id> <name>` - הוספת שירות למעקב
- `/refresh` - רענון סטטוסים

## Deployment על Render

1. צור Web Service חדש ב-Render
2. חבר את הריפוזיטורי
3. הגדר את משתני הסביבה
4. הרץ: `python bot.py`
