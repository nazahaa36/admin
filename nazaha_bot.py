import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import json
import requests
import datetime
import logging
import re
import os
import time
import threading
from collections import defaultdict

# ========== الإعدادات والأمان ==========
TOKEN = os.environ.get('NAZAHA_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')  # ضع التوكن الخاص بك هنا
ADMIN_PASSWORD = os.environ.get('NAZAHA_ADMIN_PASSWORD', 'nazaha2026')
JSON_MEMBERS_URL = 'https://raw.githubusercontent.com/nazahaa36/com/main/member.json'
BACKUP_DIR = 'backups'

bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# إنشاء مجلد النسخ الاحتياطي
os.makedirs(BACKUP_DIR, exist_ok=True)

# ========== قاعدة البيانات ==========
conn = sqlite3.connect('nazaha.db', check_same_thread=False)
c = conn.cursor()

# جدول الجلسات
c.execute('''CREATE TABLE IF NOT EXISTS sessions (
    chat_id INTEGER PRIMARY KEY,
    user_id TEXT,
    full_name TEXT,
    role TEXT,
    login_time TEXT
)''')

# جدول الطلبات
c.execute('''CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_number TEXT,
    user_id TEXT,
    user_name TEXT,
    request_type TEXT,
    details TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    handled_by TEXT,
    handled_at TEXT
)''')

# جدول الحضور
c.execute('''CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    user_name TEXT,
    date TEXT,
    time TEXT,
    note TEXT
)''')

# جدول المراسلات
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT,
    from_name TEXT,
    to_id TEXT,
    content TEXT,
    date TEXT,
    is_read INTEGER DEFAULT 0,
    reply_to INTEGER
)''')

# جدول المهام (للمتطوعين)
c.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    assigned_to TEXT,
    assigned_by TEXT,
    status TEXT DEFAULT 'pending',
    priority TEXT DEFAULT 'normal',
    created_at TEXT,
    due_date TEXT,
    completed_at TEXT
)''')

# جدول سجل النشاطات
c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT,
    details TEXT,
    created_at TEXT
)''')

conn.commit()

# ========== دوال مساعدة خاصة بالـ JSON (المصححة) ==========
def get_members():
    """جلب الأعضاء من JSON مع تصفية السجلات الفارغة - متوافق مع JSON الحقيقي"""
    try:
        resp = requests.get(JSON_MEMBERS_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        members = data if isinstance(data, list) else data.get('members', [])
        # تصفية السجلات التي تحتوي على id و fullName على الأقل
        valid_members = [m for m in members if m.get('id') and m.get('fullName')]
        return valid_members
    except Exception as e:
        logging.error(f"خطأ في جلب البيانات: {e}")
        return []

def get_member_by_id(user_id):
    for m in get_members():
        if str(m.get('id')) == str(user_id):
            return m
    return None

def get_member_by_name(name):
    name = name.strip().lower()
    for m in get_members():
        if name in m.get('fullName', '').lower():
            return m
    return None

def check_login(user_id, password):
    member = get_member_by_id(user_id)
    if not member:
        return False, None
    stored_password = member.get('password', '')
    if stored_password and stored_password == password:
        return True, member
    return False, None

def get_user_role(member):
    """تحديد دور المستخدم حسب JSON: 'عضو' أو 'موظف'"""
    user_type = member.get('type', 'عضو')
    # في JSON الخاص بك: 'موظف' = متطوع، 'عضو' = منخرط
    return 'volunteer' if user_type == 'موظف' else 'member'

def get_cell_display(member):
    """إرجاع نص الخلية مع التعامل مع القيم الفارغة"""
    cell = member.get('cell', '').strip()
    if cell:
        return cell
    member_type = member.get('type', 'عضو')
    if member_type == 'عضو':
        return "📌 غير مسند لخلية (منخرط عام)"
    return "📌 غير مسند لخلية"

def get_position_display(member):
    """إرجاع نص المنصب مع التعامل مع القيم الفارغة"""
    position = member.get('position', '').strip()
    if position:
        return position
    return "—"

def format_member_info(member):
    """تنسيق معلومات العضو بشكل جميل وآمن - متوافق مع JSON الحقيقي"""
    cell_display = get_cell_display(member)
    position_display = get_position_display(member)
    
    # تعيين النوع للعرض: 'عضو' -> منخرط، 'موظف' -> متطوع
    display_type = "منخرط" if member.get('type') == 'عضو' else "متطوع"
    
    text = f"""
👤 *البطاقة الشخصية*

🆔 *الرقم التعريفي:* `{member.get('id', '-')}`
📛 *الاسم الكامل:* {member.get('fullName', '-')}
🏷️ *الصفة:* {display_type}
📌 *الخلية:* {cell_display}
💼 *المنصب:* {position_display}

📞 *الهاتف:* `{member.get('phone', '-')}`
📧 *البريد:* {member.get('email', '-')}
🎂 *تاريخ الميلاد:* {member.get('birthDate', '-')}
🏠 *العنوان:* {member.get('address', '-')}

🎓 *المستوى الدراسي:* {member.get('education', '-')}
⚡ *الاهتمامات/التخصص:* {member.get('specialty', '-')}

📅 *تاريخ الانضمام:* {member.get('hiringDate', '-')}
⏰ *تاريخ الانتهاء:* {member.get('expiryDate', '-')}
    """
    return text

def get_all_cells():
    """جلب قائمة الخلايا الفريدة من الأعضاء"""
    cells = set()
    for m in get_members():
        cell = m.get('cell', '').strip()
        if cell:
            cells.add(cell)
    return sorted(list(cells))

def get_members_by_cell(cell_name):
    """جلب الأعضاء حسب الخلية"""
    return [m for m in get_members() if m.get('cell', '').strip() == cell_name]

def get_members_without_cell():
    """جلب المنخرطين (عضو) بدون خلية"""
    return [m for m in get_members() if not m.get('cell', '').strip() and m.get('type') == 'عضو']

def send_notification_to_admin(text, reply_markup=None):
    admins = c.execute("SELECT chat_id FROM sessions WHERE role='admin'").fetchall()
    for admin in admins:
        try:
            bot.send_message(admin[0], text, parse_mode='Markdown', reply_markup=reply_markup)
        except:
            pass

def generate_request_number():
    return f"REQ-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

def log_activity(user_id, action, details=""):
    c.execute("INSERT INTO activity_log (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
              (user_id, action, details, datetime.datetime.now().isoformat()))
    conn.commit()

def backup_database():
    """نسخ احتياطي لقاعدة البيانات"""
    try:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f'nazaha_backup_{timestamp}.db')
        import shutil
        shutil.copy2('nazaha.db', backup_path)
        # حذف النسخ القديمة (أكثر من 10)
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.db')])
        for old in backups[:-10]:
            os.remove(os.path.join(BACKUP_DIR, old))
        return backup_path
    except Exception as e:
        logging.error(f"Backup error: {e}")
        return None

def is_admin(chat_id):
    session = c.execute("SELECT role FROM sessions WHERE chat_id=?", (chat_id,)).fetchone()
    return session and session[0] == 'admin'

# ========== القوائم الرئيسية (مع حفظ جميع الميزات) ==========
def admin_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📋 الطلبات", callback_data="admin_requests"),
        InlineKeyboardButton("🔍 استعلام", callback_data="admin_search"),
        InlineKeyboardButton("👥 الأعضاء", callback_data="admin_members"),
        InlineKeyboardButton("🏛️ الخلايا", callback_data="admin_cells"),
        InlineKeyboardButton("✅ الحضور", callback_data="admin_attendance"),
        InlineKeyboardButton("📨 الرسائل", callback_data="admin_messages"),
        InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("📢 إشعار", callback_data="admin_broadcast"),
        InlineKeyboardButton("⚡ المهام", callback_data="admin_tasks"),
        InlineKeyboardButton("💾 نسخ احتياطي", callback_data="admin_backup"),
        InlineKeyboardButton("📜 السجل", callback_data="admin_logs"),
        InlineKeyboardButton("🚪 خروج", callback_data="admin_logout")
    )
    bot.send_message(chat_id, "🛡️ *لوحة تحكم الأدمن - نظام نزاهة*\n\nاختر الخدمة المطلوبة:", parse_mode='Markdown', reply_markup=markup)

def user_menu(chat_id, member):
    role = get_user_role(member)
    markup = InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        InlineKeyboardButton("👤 ملفي الشخصي", callback_data="user_profile"),
        InlineKeyboardButton("🔍 البحث عن عضو", callback_data="user_search"),
        InlineKeyboardButton("📨 مراسلة الإدارة", callback_data="user_message"),
        InlineKeyboardButton("✅ تسجيل حضور", callback_data="user_attendance"),
        InlineKeyboardButton("📝 طلب نشر مقال", callback_data="user_article"),
        InlineKeyboardButton("✏️ تعديل بياناتي", callback_data="user_update"),
        InlineKeyboardButton("📋 طلباتي", callback_data="user_my_requests"),
        InlineKeyboardButton("🚪 التخلي عن العضوية", callback_data="user_resign")
    ]
    
    if role == 'volunteer':
        buttons.insert(4, InlineKeyboardButton("⚡ مهامي", callback_data="volunteer_tasks"))
        buttons.insert(5, InlineKeyboardButton("📊 تقريري", callback_data="volunteer_report"))
    
    markup.add(*buttons)
    cell_info = get_cell_display(member)
    bot.send_message(chat_id, f"👋 أهلاً *{member.get('fullName')}!*\n🏷️ الصفة: {'منخرط' if member.get('type')=='عضو' else 'متطوع'}\n📌 {cell_info}\n\nاختر الخدمة:", parse_mode='Markdown', reply_markup=markup)

# ========== أوامر البداية والدخول ==========
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
    conn.commit()
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("/login"), KeyboardButton("/admin"), KeyboardButton("/help"))
    
    bot.send_message(chat_id, 
        "🏛️ *مرحباً في نظام نزاهة*\n"
        "المنتدى الشبابي للفكر والمشاركة المدنية\n\n"
        "🔑 *للأعضاء:* `/login`\n"
        "👑 *للأدمن:* `/admin`\n"
        "❓ *المساعدة:* `/help`\n\n"
        "📌 الدخول يتطلب رقم التعريف + كلمة المرور",
        parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['help'])
def help_cmd(message):
    chat_id = message.chat.id
    help_text = """
📖 *دليل استخدام بوت نزاهة*

*🔑 أوامر الدخول:*
`/login` - تسجيل الدخول كعضو/متطوع
`/admin` - دخول لوحة الأدمن
`/logout` - تسجيل الخروج

*🔍 أوامر البحث:*
`/search [رقم أو اسم]` - البحث السريع
`/cells` - عرض الخلايا والأقسام

*📊 أوامر المعلومات:*
`/about` - عن النظام
`/stats` - إحصائيات عامة

*💡 نصائح:*
• احفظ كلمة المرور في مكان آمن
• يمكنك مراسلة الإدارة في أي وقت
• سجل حضورك يومياً للحصول على نشاط
    """
    bot.send_message(chat_id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['about'])
def about_cmd(message):
    chat_id = message.chat.id
    members = get_members()
    volunteers = len([m for m in members if m.get('type') == 'موظف'])
    regular = len([m for m in members if m.get('type') == 'عضو'])
    cells = len(get_all_cells())
    
    about_text = f"""
🏛️ *عن نظام نزاهة*

المنتدى الشبابي للفكر والمشاركة المدنية

📊 *إحصائيات المنظمة:*
👥 إجمالي الأعضاء: {len(members)}
🔵 متطوعين: {volunteers}
🟢 منخرطين: {regular}
🏛️ عدد الخلايا: {cells}

🤖 *مميزات النظام:*
✅ تسجيل الحضور اليومي
✅ مراسلة الإدارة
✅ طلب نشر المقالات
✅ متابعة المهام (للمتطوعين)
✅ تقارير وإحصائيات

📅 *تاريخ التحديث:* {datetime.datetime.now().strftime('%Y-%m-%d')}
    """
    bot.send_message(chat_id, about_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    chat_id = message.chat.id
    members = get_members()
    volunteers = len([m for m in members if m.get('type') == 'موظف'])
    regular = len([m for m in members if m.get('type') == 'عضو'])
    no_cell = len(get_members_without_cell())
    cells = get_all_cells()
    
    text = f"""
📊 *إحصائيات نظام نزاهة*

👥 *الأعضاء:*
├ 🔵 متطوعين: {volunteers}
├ 🟢 منخرطين: {regular}
└ 📌 بدون خلية: {no_cell}

🏛️ *الخلايا النشطة:* {len(cells)}
"""
    for cell in cells[:10]:
        count = len(get_members_by_cell(cell))
        text += f"• {cell}: {count} عضو\n"
    
    today = datetime.date.today().isoformat()
    attendance = c.execute("SELECT COUNT(DISTINCT user_id) FROM attendance WHERE date=?", (today,)).fetchone()[0]
    text += f"\n✅ *الحضور اليوم:* {attendance} عضو"
    
    bot.send_message(chat_id, text, parse_mode='Markdown')

@bot.message_handler(commands=['cells'])
def cells_cmd(message):
    chat_id = message.chat.id
    cells = get_all_cells()
    no_cell_members = get_members_without_cell()
    
    text = "🏛️ *الخلايا والأقسام*\n\n"
    for cell in cells:
        count = len(get_members_by_cell(cell))
        text += f"📌 *{cell}*\n└ 👥 {count} عضو\n\n"
    
    if no_cell_members:
        text += f"📌 *منخرطين عامين (بدون خلية)*\n└ 👥 {len(no_cell_members)} عضو\n\n"
    
    text += "💡 استخدم `/search [اسم الخلية]` للبحث"
    bot.send_message(chat_id, text, parse_mode='Markdown')

@bot.message_handler(commands=['admin'])
def admin_login(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "🔐 *أدخل كلمة مرور الأدمن:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, check_admin_password)

def check_admin_password(message):
    chat_id = message.chat.id
    if message.text == ADMIN_PASSWORD:
        c.execute("REPLACE INTO sessions (chat_id, user_id, full_name, role, login_time) VALUES (?, ?, ?, ?, ?)",
                  (chat_id, 'ADMIN', 'مدير النظام', 'admin', datetime.datetime.now().isoformat()))
        conn.commit()
        log_activity('ADMIN', 'admin_login', f'chat_id: {chat_id}')
        bot.send_message(chat_id, "✅ *تم الدخول كأدمن بنجاح*\n\n🛡️ لوحة التحكم جاهزة", parse_mode='Markdown')
        admin_menu(chat_id)
    else:
        bot.send_message(chat_id, "❌ *كلمة المرور خاطئة*\nاستخدم /admin للمحاولة مجدداً", parse_mode='Markdown')

@bot.message_handler(commands=['login'])
def login_step1(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "🔑 *أدخل رقم التعريف:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, login_step2)

def login_step2(message):
    chat_id = message.chat.id
    user_id = message.text.strip()
    member = get_member_by_id(user_id)
    
    if not member:
        bot.send_message(chat_id, "❌ *رقم التعريف غير موجود*\nتأكد من الرقم وأعد المحاولة باستخدام /login", parse_mode='Markdown')
        return
    
    c.execute("INSERT OR REPLACE INTO sessions (chat_id, user_id, full_name, role, login_time) VALUES (?, ?, ?, ?, ?)",
              (chat_id, user_id, member.get('fullName'), 'temp', datetime.datetime.now().isoformat()))
    conn.commit()
    
    msg = bot.send_message(chat_id, f"🔐 *أدخل كلمة المرور للعضو {member.get('fullName')}:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, login_step3, user_id)

def login_step3(message, user_id):
    chat_id = message.chat.id
    password = message.text.strip()
    
    success, member = check_login(user_id, password)
    
    if not success:
        bot.send_message(chat_id, "❌ *كلمة المرور غير صحيحة*\nاستخدم /login للمحاولة مجدداً", parse_mode='Markdown')
        c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
        conn.commit()
        return
    
    role = get_user_role(member)
    c.execute("REPLACE INTO sessions (chat_id, user_id, full_name, role, login_time) VALUES (?, ?, ?, ?, ?)",
              (chat_id, user_id, member.get('fullName'), role, datetime.datetime.now().isoformat()))
    conn.commit()
    
    log_activity(user_id, 'login', f"{member.get('fullName')} - {member.get('type')}")
    
    cell_info = get_cell_display(member)
    welcome_text = f"""✅ *مرحباً {member.get('fullName')}!*

🏷️ *الصفة:* {'منخرط' if member.get('type')=='عضو' else 'متطوع'}
📌 *الخلية:* {cell_info}
💼 *المنصب:* {get_position_display(member)}

تم تسجيل الدخول بنجاح 🎉"""
    
    bot.send_message(chat_id, welcome_text, parse_mode='Markdown')
    user_menu(chat_id, member)

@bot.message_handler(commands=['logout'])
def logout(message):
    chat_id = message.chat.id
    session = c.execute("SELECT user_id FROM sessions WHERE chat_id=?", (chat_id,)).fetchone()
    if session:
        log_activity(session[0], 'logout')
    c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
    conn.commit()
    bot.send_message(chat_id, "👋 *تم تسجيل الخروج بنجاح*\nاستخدم /login للدخول مجدداً", parse_mode='Markdown')

# ========== أوامر البحث السريع ==========
@bot.message_handler(func=lambda m: m.text and m.text.startswith('/search'))
def quick_search(message):
    chat_id = message.chat.id
    keyword = message.text.replace('/search', '').strip()
    
    if not keyword:
        bot.send_message(chat_id, "🔍 *أرسل رقم التعريف أو الاسم بعد الأمر*\nمثال: `/search 1270738` أو `/search نزيه`", parse_mode='Markdown')
        return
    
    # البحث برقم التعريف أولاً
    member = get_member_by_id(keyword)
    if not member:
        member = get_member_by_name(keyword)
    
    # البحث حسب الخلية
    if not member:
        cell_members = get_members_by_cell(keyword)
        if cell_members:
            text = f"🏛️ *أعضاء خلية: {keyword}*\n\n"
            for m in cell_members[:20]:
                text += f"• `{m.get('id')}` - {m.get('fullName')} ({'متطوع' if m.get('type')=='موظف' else 'منخرط'})\n"
            bot.send_message(chat_id, text, parse_mode='Markdown')
            return
    
    if member:
        bot.send_message(chat_id, format_member_info(member), parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "❌ *لم يتم العثور على عضو أو خلية بهذا الاسم/الرقم*", parse_mode='Markdown')

# ========== معالجة الكولباك (جميع الميزات) ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    session = c.execute("SELECT user_id, full_name, role FROM sessions WHERE chat_id=?", (chat_id,)).fetchone()
    
    if not session and not call.data.startswith(('admin_search', 'admin_logout')):
        bot.answer_callback_query(call.id, "الرجاء تسجيل الدخول أولاً", show_alert=True)
        return
    
    data = call.data
    
    # ========== أوامر الأدمن ==========
    if data == "admin_search":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔍 *أدخل رقم التعريف أو الاسم للبحث:*", parse_mode='Markdown')
        bot.register_next_step_handler(msg, admin_search_member)
    
    elif data == "admin_members":
        bot.answer_callback_query(call.id)
        show_members_filter(chat_id)
    
    elif data == "admin_cells":
        bot.answer_callback_query(call.id)
        show_cells_menu(chat_id)
    
    elif data == "admin_requests":
        bot.answer_callback_query(call.id)
        show_requests_admin(chat_id)
    
    elif data == "admin_messages":
        bot.answer_callback_query(call.id)
        show_messages_admin(chat_id)
    
    elif data == "admin_attendance":
        bot.answer_callback_query(call.id)
        show_attendance_admin(chat_id)
    
    elif data == "admin_stats":
        bot.answer_callback_query(call.id)
        show_detailed_stats(chat_id)
    
    elif data == "admin_broadcast":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📢 *أدخل نص الإشعار لجميع المستخدمين:*", parse_mode='Markdown')
        bot.register_next_step_handler(msg, send_broadcast)
    
    elif data == "admin_tasks":
        bot.answer_callback_query(call.id)
        show_tasks_menu(chat_id)
    
    elif data == "admin_backup":
        bot.answer_callback_query(call.id)
        path = backup_database()
        if path:
            bot.send_message(chat_id, f"✅ *تم إنشاء نسخة احتياطية*\n📁 `{path}`", parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "❌ *فشل إنشاء النسخة الاحتياطية*", parse_mode='Markdown')
        admin_menu(chat_id)
    
    elif data == "admin_logs":
        bot.answer_callback_query(call.id)
        show_activity_logs(chat_id)
    
    elif data == "admin_logout":
        bot.answer_callback_query(call.id)
        c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
        conn.commit()
        bot.send_message(chat_id, "👋 *تم تسجيل الخروج من وضع الأدمن*", parse_mode='Markdown')
    
    # ========== أوامر المستخدم ==========
    elif data == "user_profile":
        if session:
            member = get_member_by_id(session[0])
            if member:
                bot.send_message(chat_id, format_member_info(member), parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك", parse_mode='Markdown')
        bot.answer_callback_query(call.id)
    
    elif data == "user_search":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "🔍 *أدخل رقم التعريف أو الاسم للبحث:*", parse_mode='Markdown')
        bot.register_next_step_handler(msg, user_search_member)
    
    elif data == "user_message":
        if session:
            msg = bot.send_message(chat_id, "📨 *اكتب رسالتك للإدارة:*", parse_mode='Markdown')
            bot.register_next_step_handler(msg, save_user_message, session)
        bot.answer_callback_query(call.id)
    
    elif data == "user_attendance":
        if session:
            today = datetime.date.today().isoformat()
            now_time = datetime.datetime.now().strftime("%H:%M")
            existing = c.execute("SELECT id FROM attendance WHERE user_id=? AND date=?", (session[0], today)).fetchone()
            if existing:
                bot.answer_callback_query(call.id, "❌ لقد سجلت حضورك اليوم مسبقاً", show_alert=True)
                return
            
            c.execute("INSERT INTO attendance (user_id, user_name, date, time) VALUES (?, ?, ?, ?)",
                      (session[0], session[1], today, now_time))
            conn.commit()
            log_activity(session[0], 'attendance', f"date: {today}, time: {now_time}")
            bot.answer_callback_query(call.id, "✅ تم تسجيل حضورك بنجاح", show_alert=True)
            bot.send_message(chat_id, f"✅ *شكراً {session[1]}*\n📅 تاريخ: {today}\n⏰ الساعة: {now_time}", parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id)
    
    elif data == "user_article":
        if session:
            msg = bot.send_message(chat_id, "✍️ *أرسل عنوان المقال:*", parse_mode='Markdown')
            bot.register_next_step_handler(msg, get_article_title, session)
        bot.answer_callback_query(call.id)
    
    elif data == "user_update":
        if session:
            msg = bot.send_message(chat_id, "✏️ *أرسل البيانات التي تريد تعديلها*\nمثال: أريد تغيير رقم هاتفي إلى 0555123456", parse_mode='Markdown')
            bot.register_next_step_handler(msg, save_update_request, session)
        bot.answer_callback_query(call.id)
    
    elif data == "user_my_requests":
        if session:
            show_user_requests(chat_id, session[0])
        bot.answer_callback_query(call.id)
    
    elif data == "user_resign":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ نعم، أتأكد", callback_data="confirm_resign"),
            InlineKeyboardButton("❌ لا، إلغاء", callback_data="cancel_resign")
        )
        bot.send_message(chat_id, "⚠️ *هل أنت متأكد من رغبتك في التخلي عن العضوية؟*\n\nهذا الإجراء نهائي ولا يمكن التراجع عنه. سيتم إرسال طلب للإدارة للموافقة.", parse_mode='Markdown', reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    elif data == "volunteer_tasks":
        if session:
            show_volunteer_tasks(chat_id, session[0])
        bot.answer_callback_query(call.id)
    
    elif data == "volunteer_report":
        if session:
            generate_volunteer_report(chat_id, session[0], session[1])
        bot.answer_callback_query(call.id)
    
    elif data == "confirm_resign":
        if session:
            req_number = generate_request_number()
            c.execute("INSERT INTO requests (request_number, user_id, user_name, request_type, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (req_number, session[0], session[1], 'تخلي عن العضوية', 'طلب مغادرة المنتدى وإنهاء العضوية', datetime.datetime.now().isoformat()))
            conn.commit()
            
            admin_text = f"⚠️ *طلب تخلي عن العضوية*\n\n📋 *رقم الطلب:* `{req_number}`\n👤 *العضو:* {session[1]}\n🆔 *الرقم:* `{session[0]}`"
            send_notification_to_admin(admin_text, InlineKeyboardMarkup().add(InlineKeyboardButton("📋 عرض الطلب", callback_data=f"view_req_{req_number}")))
            
            bot.send_message(chat_id, "✅ *تم إرسال طلب التخلي عن العضوية إلى الإدارة*\nسيتم التواصل معك قريباً", parse_mode='Markdown')
            log_activity(session[0], 'resign_request', req_number)
        bot.answer_callback_query(call.id)
    
    elif data == "cancel_resign":
        bot.answer_callback_query(call.id, "❌ تم إلغاء طلب التخلي عن العضوية", show_alert=True)
    
    # ========== عرض تفاصيل الطلب ==========
    elif data.startswith("view_req_"):
        req_id = data.split("_")[2]
        show_request_detail(chat_id, req_id)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("done_req_"):
        req_id = data.split("_")[2]
        c.execute("UPDATE requests SET status='completed', handled_by=?, handled_at=? WHERE id=?", 
                  (session[1] if session else 'ADMIN', datetime.datetime.now().isoformat(), req_id))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تم تحديث حالة الطلب إلى مكتمل", show_alert=True)
        show_request_detail(chat_id, req_id)
    
    elif data.startswith("reply_msg_"):
        msg_id = data.split("_")[2]
        msg_data = c.execute("SELECT from_id, from_name, content FROM messages WHERE id=?", (msg_id,)).fetchone()
        if msg_data:
            bot.answer_callback_query(call.id)
            msg = bot.send_message(chat_id, f"✉️ *الرد على {msg_data[1]}*\n\nالرسالة الأصلية: {msg_data[2][:100]}...\n\nأكتب ردك:", parse_mode='Markdown')
            bot.register_next_step_handler(msg, send_reply, msg_data[0], msg_data[1])
    
    # ========== فلترة الأعضاء ==========
    elif data.startswith("filter_type_"):
        member_type = data.replace("filter_type_", "")
        show_members_by_type(chat_id, member_type)
        bot.answer_callback_query(call.id)
    
    elif data.startswith("filter_cell_"):
        cell_name = data.replace("filter_cell_", "")
        show_members_by_cell(chat_id, cell_name)
        bot.answer_callback_query(call.id)
    
    elif data == "filter_no_cell":
        show_members_no_cell(chat_id)
        bot.answer_callback_query(call.id)
    
    elif data == "back_to_admin":
        bot.answer_callback_query(call.id)
        admin_menu(chat_id)
    
    # ========== مهام المتطوعين ==========
    elif data.startswith("task_done_"):
        task_id = data.split("_")[2]
        c.execute("UPDATE tasks SET status='completed', completed_at=? WHERE id=?", 
                  (datetime.datetime.now().isoformat(), task_id))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تم إكمال المهمة", show_alert=True)
        if session:
            show_volunteer_tasks(chat_id, session[0])
    
    elif data.startswith("admin_assign_task_"):
        bot.answer_callback_query(call.id)
        msg = bot.send_message(chat_id, "📝 *أدخل تفاصيل المهمة بالشكل:*\n`رقم_المتطوع|عنوان|وصف|أولوية (high/normal/low)|تاريخ_الاستحقاق`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, assign_task_admin)

# ========== دوال العرض (جميع الميزات) ==========
def show_members_filter(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔵 المتطوعين", callback_data="filter_type_موظف"),
        InlineKeyboardButton("🟢 المنخرطين", callback_data="filter_type_عضو"),
        InlineKeyboardButton("📌 بدون خلية", callback_data="filter_no_cell"),
        InlineKeyboardButton("🏛️ حسب الخلية", callback_data="show_cells_filter")
    )
    bot.send_message(chat_id, "👥 *فلترة الأعضاء*\nاختر نوع الفلترة:", parse_mode='Markdown', reply_markup=markup)

def show_cells_menu(chat_id):
    cells = get_all_cells()
    markup = InlineKeyboardMarkup(row_width=1)
    for cell in cells:
        count = len(get_members_by_cell(cell))
        markup.add(InlineKeyboardButton(f"{cell} ({count})", callback_data=f"filter_cell_{cell}"))
    markup.add(InlineKeyboardButton("📌 المنخرطين بدون خلية", callback_data="filter_no_cell"))
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin"))
    bot.send_message(chat_id, "🏛️ *الخلايا والأقسام*\nاختر خلية لعرض أعضائها:", parse_mode='Markdown', reply_markup=markup)

def show_members_by_type(chat_id, member_type):
    # member_type قد يكون 'موظف' أو 'عضو'
    members = [m for m in get_members() if m.get('type') == member_type]
    icon = "🔵" if member_type == "موظف" else "🟢"
    type_name = "متطوع" if member_type == "موظف" else "منخرط"
    if members:
        text = f"{icon} *قائمة {type_name}ين* ({len(members)})\n\n"
        for m in members[:30]:
            cell = m.get('cell', '') or "بدون خلية"
            text += f"• `{m.get('id')}` - {m.get('fullName')}\n  └ 📌 {cell}\n"
        if len(members) > 30:
            text += f"\n*... و {len(members)-30} آخرين*"
    else:
        text = f"📭 لا يوجد {type_name}ين"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_members_by_cell(chat_id, cell_name):
    members = get_members_by_cell(cell_name)
    if members:
        text = f"🏛️ *أعضاء خلية: {cell_name}* ({len(members)})\n\n"
        for m in members:
            type_icon = "🔵" if m.get('type') == 'موظف' else "🟢"
            text += f"{type_icon} `{m.get('id')}` - {m.get('fullName')}\n  └ 💼 {get_position_display(m)}\n"
    else:
        text = "📭 لا يوجد أعضاء في هذه الخلية"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_members_no_cell(chat_id):
    members = get_members_without_cell()
    if members:
        text = f"📌 *المنخرطين بدون خلية* ({len(members)})\n\n"
        for m in members:
            text += f"🟢 `{m.get('id')}` - {m.get('fullName')}\n  └ 📞 {m.get('phone', '-')}\n"
    else:
        text = "✅ جميع المنخرطين مسندون لخلايا"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_requests_admin(chat_id):
    requests = c.execute("SELECT id, request_number, user_name, request_type, status, created_at FROM requests ORDER BY id DESC LIMIT 15").fetchall()
    if requests:
        bot.send_message(chat_id, f"📋 *الطلبات الواردة* ({len(requests)} أخيرة)\n", parse_mode='Markdown')
        for req in requests:
            status_icon = "🟡" if req[4] == 'pending' else "✅"
            status_text = "قيد المعالجة" if req[4] == 'pending' else "مكتمل"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📖 عرض التفاصيل", callback_data=f"view_req_{req[0]}"))
            if req[4] == 'pending':
                markup.add(InlineKeyboardButton("✅ تمت المعالجة", callback_data=f"done_req_{req[0]}"))
            bot.send_message(chat_id, f"{status_icon} *طلب #{req[1]}*\n👤 {req[2]}\n📌 {req[3]}\n📅 {req[5][:16]}\n🏷️ {status_text}", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(chat_id, "📭 *لا توجد طلبات حالياً*", parse_mode='Markdown')

def show_messages_admin(chat_id):
    msgs = c.execute("SELECT id, from_name, content, date, is_read FROM messages ORDER BY id DESC LIMIT 10").fetchall()
    if msgs:
        bot.send_message(chat_id, "📨 *الرسائل الواردة*\n", parse_mode='Markdown')
        for m in msgs:
            status = "🔴 جديدة" if not m[4] else "✅ مقروءة"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📖 رد", callback_data=f"reply_msg_{m[0]}"))
            bot.send_message(chat_id, f"{status}\n*من:* {m[1]}\n*الرسالة:* {m[2][:200]}...\n*التاريخ:* {m[3][:16]}", parse_mode='Markdown', reply_markup=markup)
            if not m[4]:
                c.execute("UPDATE messages SET is_read=1 WHERE id=?", (m[0],))
                conn.commit()
    else:
        bot.send_message(chat_id, "📭 *لا توجد رسائل*", parse_mode='Markdown')

def show_attendance_admin(chat_id):
    today = datetime.date.today().isoformat()
    records = c.execute("SELECT user_name, time FROM attendance WHERE date=? ORDER BY time DESC", (today,)).fetchall()
    if records:
        text = f"✅ *سجل الحضور - {today}*\n\n"
        for r in records:
            text += f"• {r[0]} - الساعة {r[1]}\n"
        text += f"\n📊 الإجمالي: {len(records)} عضو"
    else:
        text = f"📭 *لا يوجد حضور مسجل لليوم {today}*"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_detailed_stats(chat_id):
    members = get_members()
    members_count = len(members)
    volunteers_count = len([m for m in members if m.get('type') == 'موظف'])
    regular_count = len([m for m in members if m.get('type') == 'عضو'])
    no_cell_count = len(get_members_without_cell())
    cells = get_all_cells()
    
    requests_count = c.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    pending_requests = c.execute("SELECT COUNT(*) FROM requests WHERE status='pending'").fetchone()[0]
    attendance_count = c.execute("SELECT COUNT(*) FROM attendance WHERE date=?", (datetime.date.today().isoformat(),)).fetchone()[0]
    unread_messages = c.execute("SELECT COUNT(*) FROM messages WHERE is_read=0").fetchone()[0]
    total_tasks = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    pending_tasks = c.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0]
    
    text = f"""
📊 *إحصائيات شاملة - نظام نزاهة*

👥 *الأعضاء:*
├ 🔵 متطوعين: {volunteers_count}
├ 🟢 منخرطين: {regular_count}
├ 📌 بدون خلية: {no_cell_count}
└ 🏛️ الخلايا: {len(cells)}

📋 *الطلبات:*
├ 📝 الواردة: {requests_count}
└ 🟡 قيد المعالجة: {pending_requests}

⚡ *المهام:*
├ 📊 الإجمالي: {total_tasks}
└ 🟡 قيد التنفيذ: {pending_tasks}

✅ *الحضور اليوم:* {attendance_count}
📨 *رسائل غير مقروءة:* {unread_messages}

📅 *آخر تحديث:* {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
    """
    bot.send_message(chat_id, text, parse_mode='Markdown')
    
    # إحصائيات حسب الخلايا
    if cells:
        cell_text = "🏛️ *توزيع الأعضاء حسب الخلايا*\n\n"
        for cell in cells:
            count = len(get_members_by_cell(cell))
            cell_text += f"• {cell}: {count} عضو\n"
        bot.send_message(chat_id, cell_text, parse_mode='Markdown')

def show_activity_logs(chat_id):
    logs = c.execute("SELECT user_id, action, details, created_at FROM activity_log ORDER BY id DESC LIMIT 20").fetchall()
    if logs:
        text = "📜 *سجل النشاطات الأخيرة*\n\n"
        for log in logs:
            text += f"• `{log[0]}` | {log[1]}\n  └ {log[2][:50]} - {log[3][:16]}\n"
    else:
        text = "📭 لا يوجد سجلات نشاط"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_request_detail(chat_id, req_id):
    req = c.execute("SELECT * FROM requests WHERE id=? OR request_number=?", (req_id, req_id)).fetchone()
    if req:
        status_icon = "🟡" if req[6] == 'pending' else "✅"
        status_text = "قيد المعالجة" if req[6] == 'pending' else "مكتمل"
        handled_info = ""
        if req[8]:
            handled_info = f"\n👤 *معالج:* {req[8]}\n📅 *تاريخ المعالجة:* {req[9][:16] if req[9] else '-'}"
        
        text = f"""
📋 *تفاصيل الطلب #{req[1]}*

{status_icon} *الحالة:* {status_text}

👤 *مقدم الطلب:* {req[3]}
🆔 *رقمه:* `{req[2]}`
📌 *نوع الطلب:* {req[4]}

📝 *التفاصيل:*
{req[5]}

📅 *تاريخ التقديم:* {req[7][:16]}{handled_info}
        """
        markup = InlineKeyboardMarkup()
        if req[6] == 'pending':
            markup.add(InlineKeyboardButton("✅ تمت المعالجة", callback_data=f"done_req_{req[0]}"))
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

def show_user_requests(chat_id, user_id):
    requests = c.execute("SELECT request_number, request_type, status, created_at FROM requests WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
    if requests:
        text = "📋 *طلباتك*\n\n"
        for req in requests:
            status_icon = "🟡" if req[2] == 'pending' else "✅"
            text += f"{status_icon} *#{req[0]}* - {req[1]}\n📅 {req[3][:16]}\n\n"
    else:
        text = "📭 *ليس لديك طلبات مسجلة*"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_tasks_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 جميع المهام", callback_data="admin_all_tasks"),
        InlineKeyboardButton("➕ إسناد مهمة", callback_data="admin_assign_task_new"),
        InlineKeyboardButton("🔙 رجوع", callback_data="back_to_admin")
    )
    bot.send_message(chat_id, "⚡ *إدارة المهام*", parse_mode='Markdown', reply_markup=markup)

def show_volunteer_tasks(chat_id, user_id):
    tasks = c.execute("SELECT id, title, description, status, priority, due_date FROM tasks WHERE assigned_to=? ORDER BY id DESC", (user_id,)).fetchall()
    if tasks:
        bot.send_message(chat_id, f"⚡ *مهامك* ({len(tasks)})\n", parse_mode='Markdown')
        for task in tasks:
            status_icon = "🟡" if task[3] == 'pending' else "✅"
            priority_icon = "🔴" if task[4] == 'high' else "🟡" if task[4] == 'normal' else "🟢"
            markup = InlineKeyboardMarkup()
            if task[3] == 'pending':
                markup.add(InlineKeyboardButton("✅ إكمال", callback_data=f"task_done_{task[0]}"))
            text = f"{status_icon} *{task[1]}*\n{priority_icon} أولوية: {task[4]}\n📅 استحقاق: {task[5] or 'غير محدد'}\n\n{task[2][:200]}"
            bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(chat_id, "📭 *ليس لديك مهام مسندة حالياً*\nسيتم إسناد مهام لك قريباً", parse_mode='Markdown')

def generate_volunteer_report(chat_id, user_id, user_name):
    current_month = datetime.date.today().strftime("%Y-%m")
    attendance_count = c.execute("SELECT COUNT(*) FROM attendance WHERE user_id=? AND date LIKE ?", (user_id, f"{current_month}%")).fetchone()[0]
    total_tasks = c.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (user_id,)).fetchone()[0]
    completed_tasks = c.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='completed'", (user_id,)).fetchone()[0]
    total_requests = c.execute("SELECT COUNT(*) FROM requests WHERE user_id=?", (user_id,)).fetchone()[0]
    
    text = f"""
📊 *تقريرك الشخصي - {user_name}*

📅 *الشهر الحالي:* {current_month}

✅ *الحضور:*
├ هذا الشهر: {attendance_count} يوم
└ اليوم: {"✅" if c.execute("SELECT id FROM attendance WHERE user_id=? AND date=?", (user_id, datetime.date.today().isoformat())).fetchone() else "❌"}

⚡ *المهام:*
├ الإجمالي: {total_tasks}
└ المنجزة: {completed_tasks}

📋 *الطلبات المرسلة:* {total_requests}

📈 *نسبة الإنجاز:* {round((completed_tasks/max(total_tasks,1))*100)}%
    """
    bot.send_message(chat_id, text, parse_mode='Markdown')

# ========== دوال الخطوات ==========
def admin_search_member(message):
    chat_id = message.chat.id
    keyword = message.text.strip()
    
    member = get_member_by_id(keyword)
    if not member:
        member = get_member_by_name(keyword)
    
    if member:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📨 إرسال رسالة", callback_data=f"admin_msg_{member.get('id')}"))
        markup.add(InlineKeyboardButton("➕ إسناد مهمة", callback_data=f"admin_assign_task_{member.get('id')}"))
        bot.send_message(chat_id, format_member_info(member), parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(chat_id, "❌ *لم يتم العثور على عضو بهذا الاسم أو الرقم*", parse_mode='Markdown')
    admin_menu(chat_id)

def user_search_member(message):
    chat_id = message.chat.id
    keyword = message.text.strip()
    
    member = get_member_by_id(keyword)
    if not member:
        member = get_member_by_name(keyword)
    
    if member:
        bot.send_message(chat_id, format_member_info(member), parse_mode='Markdown')
    else:
        bot.send_message(chat_id, "❌ *لم يتم العثور على عضو بهذا الاسم أو الرقم*", parse_mode='Markdown')

def save_user_message(message, session):
    if session:
        content = message.text
        c.execute("INSERT INTO messages (from_id, from_name, to_id, content, date, is_read) VALUES (?, ?, ?, ?, ?, ?)",
                  (session[0], session[1], 'ADMIN', content, datetime.datetime.now().isoformat(), 0))
        conn.commit()
        
        admin_text = f"📨 *رسالة جديدة من {session[1]}*\n🆔 `{session[0]}`\n\n{content[:300]}"
        send_notification_to_admin(admin_text, InlineKeyboardMarkup().add(InlineKeyboardButton("📖 رد", callback_data=f"reply_{session[0]}")))
        
        bot.send_message(message.chat.id, "✅ *تم إرسال رسالتك للإدارة*\nسيتم الرد عليك قريباً", parse_mode='Markdown')
        log_activity(session[0], 'send_message')

def get_article_title(message, session):
    title = message.text
    msg = bot.send_message(message.chat.id, "📝 *أرسل محتوى المقال:*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_article, session, title)

def save_article(message, session, title):
    content = message.text
    req_number = generate_request_number()
    details = f"**العنوان:** {title}\n\n**المحتوى:**\n{content}"
    
    c.execute("INSERT INTO requests (request_number, user_id, user_name, request_type, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (req_number, session[0], session[1], 'نشر مقال', details, datetime.datetime.now().isoformat()))
    conn.commit()
    
    admin_text = f"📝 *طلب نشر مقال جديد*\n\n📋 *الرقم:* `{req_number}`\n👤 *من:* {session[1]}\n📌 *العنوان:* {title}"
    send_notification_to_admin(admin_text, InlineKeyboardMarkup().add(InlineKeyboardButton("📋 عرض", callback_data=f"view_req_{req_number}")))
    
    bot.send_message(message.chat.id, "✅ *تم إرسال طلب نشر المقال للإدارة*\nسيتم مراجعته ونشره قريباً", parse_mode='Markdown')
    log_activity(session[0], 'article_request', title)

def save_update_request(message, session):
    details = message.text
    req_number = generate_request_number()
    
    c.execute("INSERT INTO requests (request_number, user_id, user_name, request_type, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (req_number, session[0], session[1], 'تعديل بيانات', details, datetime.datetime.now().isoformat()))
    conn.commit()
    
    admin_text = f"✏️ *طلب تعديل بيانات*\n\n📋 *الرقم:* `{req_number}`\n👤 *من:* {session[1]}\n📝 *التفاصيل:* {details[:200]}"
    send_notification_to_admin(admin_text, InlineKeyboardMarkup().add(InlineKeyboardButton("📋 عرض", callback_data=f"view_req_{req_number}")))
    
    bot.send_message(message.chat.id, "✅ *تم إرسال طلب تعديل البيانات للإدارة*\nسيتم مراجعته", parse_mode='Markdown')
    log_activity(session[0], 'update_request')

def send_broadcast(message):
    chat_id = message.chat.id
    broadcast_text = message.text
    
    users = c.execute("SELECT chat_id FROM sessions WHERE role != 'admin' AND role != 'temp'").fetchall()
    sent = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 *إشعار من الإدارة*\n\n{broadcast_text}", parse_mode='Markdown')
            sent += 1
        except:
            pass
    
    bot.send_message(chat_id, f"✅ *تم إرسال الإشعار إلى {sent} مستخدم*", parse_mode='Markdown')
    log_activity('ADMIN', 'broadcast', f"sent_to: {sent}")
    admin_menu(chat_id)

def send_reply(message, to_user_id, to_name):
    reply_content = message.text
    
    c.execute("INSERT INTO messages (from_id, from_name, to_id, content, date, is_read) VALUES (?, ?, ?, ?, ?, ?)",
              ('ADMIN', 'مدير النظام', to_user_id, reply_content, datetime.datetime.now().isoformat(), 0))
    conn.commit()
    
    user_chat = c.execute("SELECT chat_id FROM sessions WHERE user_id=?", (to_user_id,)).fetchone()
    if user_chat:
        try:
            bot.send_message(user_chat[0], f"📨 *رد من الإدارة*\n\n{reply_content}", parse_mode='Markdown')
        except:
            pass
    
    bot.send_message(message.chat.id, f"✅ *تم إرسال الرد إلى {to_name}*", parse_mode='Markdown')
    log_activity('ADMIN', 'reply_message', f"to: {to_name}")
    admin_menu(message.chat.id)

def assign_task_admin(message):
    chat_id = message.chat.id
    try:
        parts = message.text.split("|")
        if len(parts) >= 3:
            user_id = parts[0].strip()
            title = parts[1].strip()
            description = parts[2].strip()
            priority = parts[3].strip() if len(parts) > 3 else 'normal'
            due_date = parts[4].strip() if len(parts) > 4 else None
            
            member = get_member_by_id(user_id)
            if not member:
                bot.send_message(chat_id, "❌ *رقم المتطوع غير موجود*", parse_mode='Markdown')
                return
            
            c.execute("INSERT INTO tasks (title, description, assigned_to, assigned_by, priority, created_at, due_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (title, description, user_id, 'ADMIN', priority, datetime.datetime.now().isoformat(), due_date))
            conn.commit()
            
            bot.send_message(chat_id, f"✅ *تم إسناد المهمة*\n\n👤 للمتطوع: {member.get('fullName')}\n📌 العنوان: {title}\n🔴 الأولوية: {priority}", parse_mode='Markdown')
            
            # إشعار المتطوع
            user_chat = c.execute("SELECT chat_id FROM sessions WHERE user_id=?", (user_id,)).fetchone()
            if user_chat:
                try:
                    bot.send_message(user_chat[0], f"⚡ *مهمة جديدة مسندة إليك*\n\n📌 {title}\n🔴 أولوية: {priority}\n📅 استحقاق: {due_date or 'غير محدد'}\n\n{description[:200]}", parse_mode='Markdown')
                except:
                    pass
            log_activity('ADMIN', 'assign_task', f"to: {user_id}, title: {title}")
        else:
            bot.send_message(chat_id, "❌ *صيغة غير صحيحة*\nاستخدم: `رقم|عنوان|وصف|أولوية|تاريخ`", parse_mode='Markdown')
    except Exception as e:
        bot.send_message(chat_id, f"❌ *خطأ:* {str(e)}", parse_mode='Markdown')
    admin_menu(chat_id)

# ========== تشغيل البوت ==========
def start_bot():
    while True:
        try:
            logging.info("✅ بوت نزاهة يعمل الآن...")
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            logging.error(f"❌ توقف البوت: {e}. إعادة التشغيل خلال 5 ثوانٍ...")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
