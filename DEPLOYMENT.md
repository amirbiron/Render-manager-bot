# הוראות Deployment על Render

## שלב 1: הכנת הפרויקט

1. העלה את הקוד ל-GitHub Repository
2. ודא שיש את הקבצים:
   - `bot.py`
   - `requirements.txt`
   - `config.py`
   - `database.py`
   - `render_api.py`

## שלב 2: יצירת MongoDB

אם אין לך MongoDB, יש שתי אפשרויות:

### אפשרות 1: MongoDB Atlas (מומלץ)
1. היכנס ל-https://cloud.mongodb.com
2. צור Cluster חינמי
3. צור משתמש ב-Database Access
4. הוסף IP ב-Network Access (0.0.0.0/0 לפיתוח)
5. העתק את ה-Connection String

### אפשרות 2: Render Postgres
אם אתה מעדיף SQL, תצטרך להתאים את הקוד.

## שלב 3: קבלת Render API Key

1. היכנס ל-https://dashboard.render.com
2. לחץ על Account Settings
3. לחץ על API Keys
4. צור API Key חדש
5. העתק את המפתח

## שלב 4: יצירת Telegram Bot

1. פתח שיחה עם @BotFather בטלגרם
2. שלח `/newbot`
3. עקוב אחרי ההוראות
4. שמור את ה-Token

## שלב 5: קבלת User ID שלך

1. פתח שיחה עם @userinfobot
2. שלח כל הודעה
3. העתק את ה-User ID

## שלב 6: יצירת Web Service ב-Render

1. היכנס ל-https://dashboard.render.com
2. לחץ על "New +" → "Web Service"
3. חבר את GitHub Repository
4. הגדרות:
   - **Name:** render-manager-bot
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Instance Type:** Free (או Starter)

## שלב 7: הגדרת משתני סביבה

ב-Environment Variables הוסף:

```
TELEGRAM_BOT_TOKEN=<הטוקן מ-BotFather>
RENDER_API_KEY=<ה-API Key מ-Render>
MONGO_URI=<Connection String מ-MongoDB Atlas>
ADMIN_USER_ID=<ה-User ID שלך>
```

## שלב 8: Deploy

1. לחץ על "Create Web Service"
2. Render יתחיל להתקין ולהריץ
3. המתן עד שהסטטוס יהיה "Live"

## שלב 9: בדיקה

1. פתח את הבוט בטלגרם
2. שלח `/start`
3. אם הכל עובד, תקבל הודעת ברוכים הבאים!

## שלב 10: הוספת שירות ראשון

```
/add_service srv-xxxxx MyService
```

החלף `srv-xxxxx` ב-Service ID האמיתי מ-Render.

## טיפים

### איך למצוא Service ID?
1. היכנס ל-Render Dashboard
2. לחץ על השירות
3. ה-URL יכיל את ה-Service ID:
   `https://dashboard.render.com/web/srv-xxxxx`

### הבוט לא עובד?
1. בדוק את הלוגים ב-Render Dashboard
2. ודא שכל משתני הסביבה מוגדרים
3. ודא שה-MongoDB פעיל

### שימוש במספר משתמשים
אם תרצה לאפשר למספר משתמשים:
1. הסר את `ADMIN_USER_ID` ממשתני הסביבה
2. או הוסף בדיקת הרשאות בקוד
