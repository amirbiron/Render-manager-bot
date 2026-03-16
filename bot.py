"""
בוט טלגרם לניהול שירותי Render
"""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from database import db
from render_api import render_api
import config

# הגדרת לוגים
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class _HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler קטן ל-Render (healthcheck + פתיחת PORT)."""

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler naming)
        if self.path in ("/", "/health", "/healthz", "/_health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"not found")

    def do_HEAD(self):  # noqa: N802 (BaseHTTPRequestHandler naming)
        # UptimeRobot ושירותי ניטור אחרים לפעמים עושים HEAD במקום GET.
        # אם אין do_HEAD, BaseHTTPRequestHandler יחזיר 501 Not Implemented.
        if self.path in ("/", "/health", "/healthz", "/_health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            return

        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        # למנוע ספאם בלוגים של Render
        return


def _start_health_server():
    """
    Render Web Service מצפה שייפתח פורט. אם לא נפתח, יופיע:
    'No open ports detected, continuing to scan...'
    """
    port = int(os.getenv("PORT", "10000"))
    host = os.getenv("HOST", "0.0.0.0")

    server = HTTPServer((host, port), _HealthHandler)
    logger.info("🌐 Health server listening on %s:%s", host, port)
    server.serve_forever()


def is_admin(user_id: int) -> bool:
    """בדיקה אם המשתמש הוא מנהל"""
    # אם הרשימה ריקה - כולם מנהלים
    if not config.ADMIN_USER_IDS:
        return True
    # בדיקה אם המשתמש ברשימת המנהלים
    return user_id in config.ADMIN_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /start"""
    user = update.effective_user
    
    welcome_text = f"""
👋 שלום {user.first_name}!

אני בוט לניהול שירותי Render.
אוכל לעזור לך להשעות, להמשיך ולהפעיל מחדש שירותים בלחיצת כפתור.

**פקודות זמינות:**
/manage - רשימת כל השירותים
/add_service - הוספת שירות חדש
/groups - ניהול קבוצות שירותים
/create_group - יצירת קבוצה חדשה
/refresh - רענון סטטוסים
/link - קישור לדשבורד Render

בחר /manage כדי להתחיל!
"""
    
    await update.message.reply_text(welcome_text)


async def manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /manage - הצגת רשימת שירותים"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ אין לך הרשאה להשתמש בפקודה זו")
        return
    
    text, reply_markup = await _render_manage_view(user_id)
    if not reply_markup:
        await update.message.reply_text(
            "📭 אין שירותים רשומים.\n"
            "השתמש ב-/add_service כדי להוסיף שירות."
        )
        return

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def _get_services_with_refreshed_statuses(owner_id: int):
    """שליפת שירותים + רענון סטטוסים מול Render."""
    services = await db.get_services(owner_id=owner_id)
    for service in services:
        status = await render_api.get_service_status(service["service_id"])
        await db.update_service_status(service["service_id"], status)
        service["status"] = status
    return services


async def _render_manage_view(owner_id: int):
    """
    בניית מסך /manage: רשימת שירותים ככפתורים, ומתחת כפתור השעה הכל/המשך הכל.
    מחזיר (text, reply_markup). אם אין שירותים, reply_markup=None.
    """
    services = await _get_services_with_refreshed_statuses(owner_id)
    if not services:
        return "📭 אין שירותים רשומים.", None

    keyboard = []
    for service in services:
        emoji = render_api.status_emoji(service.get("status", "unknown"))
        button_text = f"{emoji} {service['name']}"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=f"view_{service['service_id']}")]
        )

    has_active = any(s.get("status") == "active" for s in services)
    has_suspended = any(s.get("status") == "suspended" for s in services)

    if has_active:
        keyboard.append([InlineKeyboardButton("⏸ השעה הכל", callback_data="suspend_all")])
    if has_suspended:
        keyboard.append([InlineKeyboardButton("▶️ המשך הכל", callback_data="resume_all")])

    keyboard.append([InlineKeyboardButton("📁 קבוצות", callback_data="groups_back")])
    keyboard.append([InlineKeyboardButton("🔄 רענון", callback_data="refresh")])

    return "🎛 **בחר שירות לניהול:**", InlineKeyboardMarkup(keyboard)


async def add_service_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /add_service"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ אין לך הרשאה להשתמש בפקודה זו")
        return
    
    # בדיקה אם יש ארגומנטים
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "📝 שימוש:\n"
            "`/add_service <service_id> <שם_השירות>`\n\n"
            "דוגמה:\n"
            "`/add_service srv-abc123xyz MyBot`",
            parse_mode="Markdown"
        )
        return
    
    service_id = context.args[0]
    service_name = " ".join(context.args[1:])
    
    # בדיקה אם השירות קיים ב-Render
    service_data = await render_api.get_service(service_id)
    if not service_data:
        await update.message.reply_text(
            f"❌ לא נמצא שירות עם המזהה `{service_id}`\n"
            "ודא שה-Service ID נכון ושיש לך הרשאות גישה.",
            parse_mode="Markdown"
        )
        return
    
    # הוספה למסד נתונים
    await db.add_service(service_id, service_name, user_id)
    
    await update.message.reply_text(
        f"✅ השירות **{service_name}** נוסף בהצלחה!\n"
        f"🆔 `{service_id}`",
        parse_mode="Markdown"
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בלחיצות על כפתורים"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("⛔ אין לך הרשאה")
        return
    
    data = query.data

    # טיפול בקבוצות
    if await _handle_group_callbacks(query, data, user_id):
        return

    # רענון
    if data == "refresh":
        text, reply_markup = await _render_manage_view(user_id)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return

    # השעה הכל / המשך הכל
    if data in ("suspend_all", "resume_all"):
        services = await db.get_services(owner_id=user_id)
        if not services:
            await query.edit_message_text("📭 אין שירותים רשומים")
            return

        if data == "suspend_all":
            await query.edit_message_text("⏳ משעה את כל השירותים...")
        else:
            await query.edit_message_text("⏳ ממשיך את כל השירותים...")

        attempted = 0
        succeeded = 0
        failed = 0
        skipped = 0

        for service in services:
            service_id = service["service_id"]

            status = await render_api.get_service_status(service_id)
            await db.update_service_status(service_id, status)

            if data == "suspend_all":
                if status != "active":
                    skipped += 1
                    continue
                attempted += 1
                success = await render_api.suspend_service(service_id)
                if success:
                    succeeded += 1
                    await db.update_service_status(service_id, "suspended")
                    await db.log_action(service_id, "suspend", user_id, True)
                else:
                    failed += 1
                    await db.log_action(service_id, "suspend", user_id, False, "API request failed")
            else:
                if status != "suspended":
                    skipped += 1
                    continue
                attempted += 1
                success = await render_api.resume_service(service_id)
                if success:
                    succeeded += 1
                    await db.update_service_status(service_id, "active")
                    await db.log_action(service_id, "resume", user_id, True)
                else:
                    failed += 1
                    await db.log_action(service_id, "resume", user_id, False, "API request failed")

        text, reply_markup = await _render_manage_view(user_id)
        summary = (
            f"✅ בוצע.\n"
            f"ניסיון: {attempted} | הצליח: {succeeded} | נכשל: {failed} | דולג: {skipped}\n\n"
        )
        await query.edit_message_text(summary + text, reply_markup=reply_markup, parse_mode="Markdown")
        return
    
    # הצגת שירות
    if data.startswith("view_"):
        service_id = data.split("_", 1)[1]
        service = await db.get_service(service_id)
        
        if not service:
            await query.edit_message_text("❌ שירות לא נמצא")
            return
        
        # קבלת סטטוס עדכני
        status = await render_api.get_service_status(service_id)
        await db.update_service_status(service_id, status)
        
        emoji = render_api.status_emoji(status)
        status_hebrew = "פעיל" if status == "active" else "מושעה" if status == "suspended" else "לא ידוע"
        
        text = f"""
🤖 **{service['name']}**
🆔 `{service_id}`
📊 סטטוס: {emoji} {status_hebrew}

בחר פעולה:
"""
        
        # כפתורי פעולה
        keyboard = []
        
        if status == "suspended":
            keyboard.append([InlineKeyboardButton("▶️ המשך", callback_data=f"resume_{service_id}")])
        else:
            keyboard.append([InlineKeyboardButton("⏸ השעה", callback_data=f"suspend_{service_id}")])
        
        keyboard.append([InlineKeyboardButton("🔄 הפעל מחדש", callback_data=f"restart_{service_id}")])
        keyboard.append([InlineKeyboardButton("🗑 הסר שירות", callback_data=f"confirmremove_{service_id}")])
        keyboard.append([InlineKeyboardButton("◀️ חזור", callback_data="back")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return
    
    # פעולות
    if data.startswith("suspend_"):
        service_id = data.split("_", 1)[1]
        service = await db.get_service(service_id)
        
        await query.edit_message_text("⏳ משעה את השירות...")
        
        success = await render_api.suspend_service(service_id)
        
        if success:
            await db.update_service_status(service_id, "suspended")
            await db.log_action(service_id, "suspend", user_id, True)
            await query.edit_message_text(
                f"✅ השירות **{service['name']}** הושעה בהצלחה!",
                parse_mode="Markdown"
            )
        else:
            await db.log_action(service_id, "suspend", user_id, False, "API request failed")
            await query.edit_message_text("❌ שגיאה בהשעיית השירות")
        return
    
    if data.startswith("resume_"):
        service_id = data.split("_", 1)[1]
        service = await db.get_service(service_id)
        
        await query.edit_message_text("⏳ מפעיל את השירות...")
        
        success = await render_api.resume_service(service_id)
        
        if success:
            await db.update_service_status(service_id, "active")
            await db.log_action(service_id, "resume", user_id, True)
            await query.edit_message_text(
                f"✅ השירות **{service['name']}** חזר לפעול!",
                parse_mode="Markdown"
            )
        else:
            await db.log_action(service_id, "resume", user_id, False, "API request failed")
            await query.edit_message_text("❌ שגיאה בהמשך השירות")
        return
    
    if data.startswith("restart_"):
        service_id = data.split("_", 1)[1]
        service = await db.get_service(service_id)
        
        await query.edit_message_text("⏳ מפעיל מחדש את השירות...")
        
        success = await render_api.restart_service(service_id)
        
        if success:
            await db.log_action(service_id, "restart", user_id, True)
            await query.edit_message_text(
                f"✅ השירות **{service['name']}** הופעל מחדש!",
                parse_mode="Markdown"
            )
        else:
            await db.log_action(service_id, "restart", user_id, False, "API request failed")
            await query.edit_message_text("❌ שגיאה בהפעלה מחדש")
        return
    
    # אישור הסרת שירות
    if data.startswith("confirmremove_"):
        service_id = data.split("_", 1)[1]
        service = await db.get_service(service_id)

        if not service:
            await query.edit_message_text("❌ שירות לא נמצא")
            return

        text = (
            f"🗑 **האם להסיר את השירות?**\n\n"
            f"🤖 {service['name']}\n"
            f"🆔 `{service_id}`\n\n"
            f"השירות יוסר מרשימת הניהול בלבד — הוא לא יימחק מ-Render."
        )

        keyboard = [
            [InlineKeyboardButton("✅ כן, הסר", callback_data=f"remove_{service_id}")],
            [InlineKeyboardButton("◀️ ביטול", callback_data=f"view_{service_id}")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    # הסרת שירות
    if data.startswith("remove_"):
        service_id = data.split("_", 1)[1]
        service = await db.get_service(service_id)
        service_name = service["name"] if service else service_id

        deleted = await db.delete_service(service_id)
        if deleted:
            await db.log_action(service_id, "remove", user_id, True)
            await query.edit_message_text(
                f"✅ השירות **{service_name}** הוסר מרשימת הניהול.",
                parse_mode="Markdown"
            )
        else:
            await db.log_action(service_id, "remove", user_id, False, "Service not found")
            await query.edit_message_text("❌ שגיאה בהסרת השירות")
        return

    # חזרה לתפריט ראשי
    if data == "back":
        text, reply_markup = await _render_manage_view(user_id)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")



# ===== ניהול קבוצות =====

async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /groups - הצגת רשימת קבוצות"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ אין לך הרשאה להשתמש בפקודה זו")
        return

    text, reply_markup = await _render_groups_view(user_id)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def create_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /create_group - יצירת קבוצה חדשה"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("⛔ אין לך הרשאה להשתמש בפקודה זו")
        return

    if not context.args:
        await update.message.reply_text(
            "📝 שימוש:\n"
            "`/create_group <שם_הקבוצה>`\n\n"
            "דוגמה:\n"
            "`/create_group בוטים-ראשיים`",
            parse_mode="Markdown"
        )
        return

    group_name = " ".join(context.args)
    await db.create_group(group_name, user_id)
    await update.message.reply_text(
        f"✅ הקבוצה **{group_name}** נוצרה בהצלחה!\n"
        f"השתמש ב-/groups כדי לנהל אותה ולהוסיף שירותים.",
        parse_mode="Markdown"
    )


async def _render_groups_view(owner_id: int):
    """בניית מסך /groups: רשימת קבוצות ככפתורים."""
    groups = await db.get_groups(owner_id)

    if not groups:
        keyboard = [[InlineKeyboardButton("➕ צור קבוצה חדשה", callback_data="group_help_create")]]
        return "📭 אין קבוצות.\nהשתמש ב-/create\\_group כדי ליצור קבוצה.", InlineKeyboardMarkup(keyboard)

    keyboard = []
    for group in groups:
        count = len(group.get("service_ids", []))
        button_text = f"📁 {group['name']} ({count} שירותים)"
        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=f"grpview_{group['_id']}")]
        )

    keyboard.append([InlineKeyboardButton("🔄 רענון", callback_data="groups_refresh")])

    return "📁 **הקבוצות שלך:**", InlineKeyboardMarkup(keyboard)


async def _render_group_detail_view(group_id: str, owner_id: int):
    """בניית מסך פרטי קבוצה עם כפתורי פעולה."""
    group = await db.get_group(group_id)
    if not group:
        return "❌ קבוצה לא נמצאה", None

    service_ids = group.get("service_ids", [])
    services_info = []
    has_active = False
    has_suspended = False

    for sid in service_ids:
        service = await db.get_service(sid)
        if service:
            status = await render_api.get_service_status(sid)
            await db.update_service_status(sid, status)
            emoji = render_api.status_emoji(status)
            services_info.append(f"  {emoji} {service['name']}")
            if status == "active":
                has_active = True
            elif status == "suspended":
                has_suspended = True

    text = f"📁 **{group['name']}**\n\n"
    if services_info:
        text += "**שירותים בקבוצה:**\n" + "\n".join(services_info) + "\n"
    else:
        text += "_(אין שירותים בקבוצה)_\n"

    keyboard = []

    if has_active:
        keyboard.append([InlineKeyboardButton("⏸ השעה קבוצה", callback_data=f"grpsuspend_{group_id}")])
    if has_suspended:
        keyboard.append([InlineKeyboardButton("▶️ המשך קבוצה", callback_data=f"grpresume_{group_id}")])

    keyboard.append([InlineKeyboardButton("➕ הוסף שירות", callback_data=f"grpadd_{group_id}")])

    if service_ids:
        keyboard.append([InlineKeyboardButton("➖ הסר שירות", callback_data=f"grpremservice_{group_id}")])

    keyboard.append([InlineKeyboardButton("🗑 מחק קבוצה", callback_data=f"grpconfirmdelete_{group_id}")])
    keyboard.append([InlineKeyboardButton("◀️ חזור לקבוצות", callback_data="groups_back")])

    return text, InlineKeyboardMarkup(keyboard)


async def _handle_group_callbacks(query, data, user_id):
    """טיפול בכל ה-callbacks של קבוצות. מחזיר True אם טופל."""

    # רענון רשימת קבוצות
    if data == "groups_refresh":
        text, reply_markup = await _render_groups_view(user_id)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    # חזרה לרשימת קבוצות
    if data == "groups_back":
        text, reply_markup = await _render_groups_view(user_id)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    # עזרה ליצירת קבוצה
    if data == "group_help_create":
        await query.edit_message_text(
            "📝 כדי ליצור קבוצה, שלח:\n`/create_group <שם_הקבוצה>`",
            parse_mode="Markdown"
        )
        return True

    # צפייה בקבוצה
    if data.startswith("grpview_"):
        group_id = data.split("_", 1)[1]
        text, reply_markup = await _render_group_detail_view(group_id, user_id)
        if reply_markup:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await query.edit_message_text(text)
        return True

    # השעיית קבוצה
    if data.startswith("grpsuspend_"):
        group_id = data.split("_", 1)[1]
        group = await db.get_group(group_id)
        if not group:
            await query.edit_message_text("❌ קבוצה לא נמצאה")
            return True

        await query.edit_message_text(f"⏳ משעה את הקבוצה **{group['name']}**...", parse_mode="Markdown")

        attempted = succeeded = failed = skipped = 0
        for sid in group.get("service_ids", []):
            status = await render_api.get_service_status(sid)
            await db.update_service_status(sid, status)
            if status != "active":
                skipped += 1
                continue
            attempted += 1
            success = await render_api.suspend_service(sid)
            if success:
                succeeded += 1
                await db.update_service_status(sid, "suspended")
                await db.log_action(sid, "suspend", user_id, True)
            else:
                failed += 1
                await db.log_action(sid, "suspend", user_id, False, "API request failed")

        text, reply_markup = await _render_group_detail_view(group_id, user_id)
        summary = (
            f"✅ הקבוצה **{group['name']}** הושעתה.\n"
            f"ניסיון: {attempted} | הצליח: {succeeded} | נכשל: {failed} | דולג: {skipped}\n\n"
        )
        await query.edit_message_text(summary + text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    # המשך קבוצה
    if data.startswith("grpresume_"):
        group_id = data.split("_", 1)[1]
        group = await db.get_group(group_id)
        if not group:
            await query.edit_message_text("❌ קבוצה לא נמצאה")
            return True

        await query.edit_message_text(f"⏳ ממשיך את הקבוצה **{group['name']}**...", parse_mode="Markdown")

        attempted = succeeded = failed = skipped = 0
        for sid in group.get("service_ids", []):
            status = await render_api.get_service_status(sid)
            await db.update_service_status(sid, status)
            if status != "suspended":
                skipped += 1
                continue
            attempted += 1
            success = await render_api.resume_service(sid)
            if success:
                succeeded += 1
                await db.update_service_status(sid, "active")
                await db.log_action(sid, "resume", user_id, True)
            else:
                failed += 1
                await db.log_action(sid, "resume", user_id, False, "API request failed")

        text, reply_markup = await _render_group_detail_view(group_id, user_id)
        summary = (
            f"✅ הקבוצה **{group['name']}** חזרה לפעול.\n"
            f"ניסיון: {attempted} | הצליח: {succeeded} | נכשל: {failed} | דולג: {skipped}\n\n"
        )
        await query.edit_message_text(summary + text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    # הוספת שירות לקבוצה - הצגת רשימת שירותים
    if data.startswith("grpadd_"):
        group_id = data.split("_", 1)[1]
        group = await db.get_group(group_id)
        if not group:
            await query.edit_message_text("❌ קבוצה לא נמצאה")
            return True

        services = await db.get_services(owner_id=user_id)
        existing_ids = set(group.get("service_ids", []))
        available = [s for s in services if s["service_id"] not in existing_ids]

        if not available:
            keyboard = [[InlineKeyboardButton("◀️ חזור", callback_data=f"grpview_{group_id}")]]
            await query.edit_message_text(
                "📭 אין שירותים זמינים להוספה.\nכל השירותים כבר בקבוצה.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return True

        keyboard = []
        for s in available:
            emoji = render_api.status_emoji(s.get("status", "unknown"))
            keyboard.append([InlineKeyboardButton(
                f"{emoji} {s['name']}",
                callback_data=f"grpaddsvc_{group_id}_{s['service_id']}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ חזור", callback_data=f"grpview_{group_id}")])

        await query.edit_message_text(
            f"➕ **בחר שירות להוספה לקבוצה {group['name']}:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return True

    # ביצוע הוספת שירות לקבוצה
    if data.startswith("grpaddsvc_"):
        parts = data.split("_", 2)
        group_id = parts[1]
        service_id = parts[2]
        await db.add_service_to_group(group_id, service_id)
        service = await db.get_service(service_id)
        service_name = service["name"] if service else service_id

        text, reply_markup = await _render_group_detail_view(group_id, user_id)
        msg = f"✅ **{service_name}** נוסף לקבוצה!\n\n"
        await query.edit_message_text(msg + text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    # הסרת שירות מקבוצה - הצגת רשימת שירותים
    if data.startswith("grpremservice_"):
        group_id = data.split("_", 1)[1]
        group = await db.get_group(group_id)
        if not group:
            await query.edit_message_text("❌ קבוצה לא נמצאה")
            return True

        keyboard = []
        for sid in group.get("service_ids", []):
            service = await db.get_service(sid)
            if service:
                emoji = render_api.status_emoji(service.get("status", "unknown"))
                keyboard.append([InlineKeyboardButton(
                    f"❌ {emoji} {service['name']}",
                    callback_data=f"grpremsvc_{group_id}_{sid}"
                )])
        keyboard.append([InlineKeyboardButton("◀️ חזור", callback_data=f"grpview_{group_id}")])

        await query.edit_message_text(
            f"➖ **בחר שירות להסרה מהקבוצה {group['name']}:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return True

    # ביצוע הסרת שירות מקבוצה
    if data.startswith("grpremsvc_"):
        parts = data.split("_", 2)
        group_id = parts[1]
        service_id = parts[2]
        await db.remove_service_from_group(group_id, service_id)
        service = await db.get_service(service_id)
        service_name = service["name"] if service else service_id

        text, reply_markup = await _render_group_detail_view(group_id, user_id)
        msg = f"✅ **{service_name}** הוסר מהקבוצה!\n\n"
        await query.edit_message_text(msg + text, reply_markup=reply_markup, parse_mode="Markdown")
        return True

    # אישור מחיקת קבוצה
    if data.startswith("grpconfirmdelete_"):
        group_id = data.split("_", 1)[1]
        group = await db.get_group(group_id)
        if not group:
            await query.edit_message_text("❌ קבוצה לא נמצאה")
            return True

        keyboard = [
            [InlineKeyboardButton("✅ כן, מחק", callback_data=f"grpdelete_{group_id}")],
            [InlineKeyboardButton("◀️ ביטול", callback_data=f"grpview_{group_id}")],
        ]
        await query.edit_message_text(
            f"🗑 **האם למחוק את הקבוצה {group['name']}?**\n\n"
            f"השירותים עצמם לא יימחקו, רק הקבוצה.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return True

    # מחיקת קבוצה
    if data.startswith("grpdelete_"):
        group_id = data.split("_", 1)[1]
        group = await db.get_group(group_id)
        group_name = group["name"] if group else "?"
        deleted = await db.delete_group(group_id)
        if deleted:
            text, reply_markup = await _render_groups_view(user_id)
            msg = f"✅ הקבוצה **{group_name}** נמחקה!\n\n"
            await query.edit_message_text(msg + text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ שגיאה במחיקת הקבוצה")
        return True

    return False


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /link - קישור לדשבורד Render"""
    await update.message.reply_text(
        "🔗 https://dashboard.render.com/web/srv-d60o4jvpm1nc73ctkoqg"
    )


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /refresh - רענון סטטוסים"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ אין לך הרשאה")
        return
    
    services = await db.get_services(owner_id=user_id)
    
    if not services:
        await update.message.reply_text("📭 אין שירותים רשומים")
        return
    
    await update.message.reply_text("🔄 מרענן סטטוסים...")
    
    updated = 0
    for service in services:
        status = await render_api.get_service_status(service["service_id"])
        await db.update_service_status(service["service_id"], status)
        updated += 1
    
    await update.message.reply_text(f"✅ {updated} שירותים עודכנו!")


def main():
    """הרצת הבוט"""
    # Render: פתיחת PORT כדי שהדיפלוי לא ייתקע.
    # רץ ברקע כדי לא להפריע ל-run_polling.
    if os.getenv("DISABLE_HEALTH_SERVER", "").lower() not in ("1", "true", "yes"):
        threading.Thread(target=_start_health_server, daemon=True).start()

    # יצירת Application
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # רישום handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("manage", manage))
    application.add_handler(CommandHandler("add_service", add_service_command))
    application.add_handler(CommandHandler("link", link_command))
    application.add_handler(CommandHandler("refresh", refresh_command))
    application.add_handler(CommandHandler("groups", groups_command))
    application.add_handler(CommandHandler("create_group", create_group_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # התחלת הבוט
    logger.info("🚀 הבוט מתחיל...")
    
    # חיבור למסד נתונים
    import asyncio
    asyncio.get_event_loop().run_until_complete(db.connect())
    
    # הרצה
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
