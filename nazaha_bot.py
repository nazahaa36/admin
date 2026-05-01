import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import json
import requests
import datetime
import re
import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
import time
import logging

# ------------------- الإعدادات -------------------
TOKEN = '8459034854:AAFOvbK3i2jJS8fNkGP8TAS6F2yvW6c_UiE'
ADMIN_PASSWORD = 'nazaha2026'            # كلمة مرور الدخول إلى وضع الإدارة
JSON_URL = 'https://raw.githubusercontent.com/nazahaa36/com/main/member.json'

bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# جلسات المستخدمين (chat_id -> user_id)
user_sessions = {}

# ------------------- قاعدة البيانات -------------------
conn = sqlite3.connect('nazaha_bot.db', check_same_thread=False)
c = conn.cursor()

# جدول الجلسات (من سجل الدخول)
c.execute('''CREATE TABLE IF NOT EXISTS sessions (
    chat_id INTEGER PRIMARY KEY,
    user_id TEXT,
    full_name TEXT,
    role TEXT,
    status TEXT DEFAULT 'active'
)''')

# جدول الرسائل
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id TEXT,
    from_name TEXT,
    to_user_id TEXT,
    subject TEXT,
    body TEXT,
    date TEXT,
    is_read INTEGER DEFAULT 0,
    reply_to INTEGER DEFAULT NULL
)''')

# جدول الحضور
c.execute('''CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    full_name TEXT,
    date TEXT,
    time TEXT,
    activity TEXT DEFAULT 'حضور عام'
)''')

# جدول الشهادات
c.execute('''CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    full_name TEXT,
    title TEXT,
    reason TEXT,
    date TEXT,
    place TEXT,
    issued_by TEXT DEFAULT 'إدارة المنتدى'
)''')

# جدول الخطابات
c.execute('''CREATE TABLE IF NOT EXISTS letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_whom TEXT,
    subject TEXT,
    body TEXT,
    date TEXT,
    created_by TEXT
)''')

# جدول التقارير
c.execute('''CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    type TEXT,
    content TEXT,
    date TEXT,
    created_by TEXT
)''')

# جدول المبادرات (من الـ JSON أو يضاف يدوياً)
c.execute('''CREATE TABLE IF NOT EXISTS initiatives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    date TEXT,
    link TEXT,
    status TEXT DEFAULT 'نشطة'
)''')

# جدول النشاطات
c.execute('''CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    date TEXT,
    time TEXT,
    location TEXT,
    description TEXT,
    type TEXT
)''')

# جدول طلبات الأعضاء (مثل طلب تغيير بيانات، طلب شهادة، إلخ)
c.execute('''CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id TEXT,
    from_name TEXT,
    request_type TEXT,
    details TEXT,
    date TEXT,
    status TEXT DEFAULT 'pending'
)''')

conn.commit()

# ------------------- دوال مساعدة -------------------
def get_members_from_json():
    """تحميل بيانات الأعضاء من الرابط مع محاولة إعادة المحاولة"""
    try:
        resp = requests.get(JSON_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'members' in data:
            return data['members']
        else:
            return []
    except Exception as e:
        logging.error(f"خطأ في تحميل JSON: {e}")
        return []

def get_member_by_id(user_id):
    """البحث عن عضو (عادي أو متطوع) من JSON"""
    members = get_members_from_json()
    for m in members:
        if str(m.get('id')) == str(user_id):
            return m
    return None

def get_user_role_from_json(user_id):
    """تحديد الدور: 'member' أو 'volunteer' (موظف)"""
    member = get_member_by_id(user_id)
    if not member:
        return None
    # افتراض أن حقل 'type' أو 'cadreType' يحتوي على 'موظف' للمتطوع
    user_type = member.get('type') or member.get('cadreType') or 'عضو'
    if user_type == 'موظف' or user_type == 'متطوع':
        return 'volunteer'
    else:
        return 'member'

def is_admin_mode(chat_id):
    """هل المستخدم في وضع الإدارة؟ نتحقق من الجلسة"""
    session = c.execute("SELECT role FROM sessions WHERE chat_id=?", (chat_id,)).fetchone()
    return session and session[0] == 'admin'

def generate_member_card(user_record):
    """إنشاء بطاقة عضوية كصورة مع باركود وبيانات"""
    # user_record هو قاموس من JSON
    img = Image.new('RGB', (650, 400), color='#f8f9fa')
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("arial.ttf", 22)
        font_normal = ImageFont.truetype("arial.ttf", 16)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except:
        font_title = font_normal = font_small = ImageFont.load_default()

    # خلفية ملوّنة
    draw.rectangle([(0,0), (650,100)], fill='#2ecc71')
    draw.text((30, 30), user_record.get('fullName', 'لا يوجد'), fill='white', font=font_title)
    draw.text((30, 70), f"رقم العضوية: {user_record.get('id')}", fill='white', font=font_normal)

    # معلومات إضافية
    y = 120
    info_lines = [
        f"النوع: {user_record.get('type', 'عضو')}",
        f"الخلية: {user_record.get('cell', '-')}",
        f"المنصب: {user_record.get('position', '-')}",
        f"تاريخ الميلاد: {user_record.get('birthDate', '-')}",
        f"تاريخ التسجيل: {user_record.get('hiringDate', '-')}",
        f"تاريخ الانتهاء: {user_record.get('expiryDate', '-')}",
        f"الهاتف: {user_record.get('phone', '-')}",
        f"البريد: {user_record.get('email', '-')}"
    ]
    for line in info_lines:
        draw.text((30, y), line, fill='#333', font=font_normal)
        y += 28

    # باركود
    qr = qrcode.make(user_record.get('id'))
    qr = qr.resize((120, 120))
    img.paste(qr, (500, 250))

    output = io.BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output

# ------------------- واجهة الأدمن الرئيسية -------------------
def admin_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👥 إدارة الأعضاء", callback_data="admin_members"),
        InlineKeyboardButton("➕ إضافة عضو/متطوع", callback_data="admin_add_user"),
        InlineKeyboardButton("📨 الرسائل الواردة", callback_data="admin_inbox"),
        InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("📜 الشهادات", callback_data="admin_certs"),
        InlineKeyboardButton("✉️ الخطابات", callback_data="admin_letters"),
        InlineKeyboardButton("📄 التقارير", callback_data="admin_reports"),
        InlineKeyboardButton("✅ الحضور والغياب", callback_data="admin_attendance"),
        InlineKeyboardButton("📢 إشعار جماعي", callback_data="admin_broadcast"),
        InlineKeyboardButton("💡 المبادرات", callback_data="admin_initiatives"),
        InlineKeyboardButton("📅 النشاطات", callback_data="admin_activities"),
        InlineKeyboardButton("📋 طلبات الأعضاء", callback_data="admin_requests"),
        InlineKeyboardButton("🚪 تسجيل الخروج", callback_data="admin_logout")
    )
    bot.send_message(chat_id, "*🛡️ لوحة تحكم الأدمن - نزاهة*\nاختر الخدمة المطلوبة:", parse_mode='Markdown', reply_markup=markup)

# ------------------- واجهة العضو / المتطوع -------------------
def user_main_menu(chat_id, user_record):
    role = get_user_role_from_json(user_record.get('id'))
    is_volunteer = (role == 'volunteer')
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👤 ملفي الشخصي", callback_data="user_profile"),
        InlineKeyboardButton("📨 إرسال رسالة للإدارة", callback_data="user_send_message"),
        InlineKeyboardButton("✅ تسجيل حضور", callback_data="user_attendance_self"),
        InlineKeyboardButton("💡 اقتراح فكرة أو مبادرة", callback_data="user_idea"),
        InlineKeyboardButton("🤝 التبرع للمنتدى", callback_data="user_donate"),
        InlineKeyboardButton("🔄 تجديد العهدة", callback_data="user_renew"),
        InlineKeyboardButton("✏️ طلب تعديل بياناتي", callback_data="user_update_data"),
        InlineKeyboardButton("📜 طلب شهادة تقدير", callback_data="user_request_cert"),
        InlineKeyboardButton("📧 طلب خطاب رسمي", callback_data="user_request_letter")
    )
    if is_volunteer:
        markup.add(InlineKeyboardButton("📋 مهامي", callback_data="volunteer_tasks"))
    bot.send_message(chat_id, f"*أهلاً بك {user_record.get('fullName')}*\nنرحب بانضمامك إلى منصة نزاهة. يمكنك استخدام الأزرار التالية:", parse_mode='Markdown', reply_markup=markup)

# ------------------- أوامر البوت الرئيسية -------------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_sessions.pop(chat_id, None)
    c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
    conn.commit()
    bot.send_message(chat_id, "مرحباً بك في *المنتدى الشبابي للفكر والمشاركة المدنية - نزاهة*.\n\nللحصول على الخدمات، يُرجى تسجيل الدخول باستخدام الأمر /login\n\nإذا كنت أدمن، استخدم /admin", parse_mode='Markdown')

@bot.message_handler(commands=['admin'])
def admin_login_prompt(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "أدخل كلمة مرور الأدمن:")
    bot.register_next_step_handler(msg, admin_login_check)

def admin_login_check(message):
    chat_id = message.chat.id
    if message.text.strip() == ADMIN_PASSWORD:
        # تسجيل الدخول كأدمن
        c.execute("REPLACE INTO sessions (chat_id, user_id, full_name, role, status) VALUES (?, ?, ?, ?, ?)",
                  (chat_id, 'ADMIN', 'مدير النظام', 'admin', 'active'))
        conn.commit()
        user_sessions[chat_id] = 'ADMIN'
        bot.send_message(chat_id, "✅ تم تسجيل الدخول بنجاح كأدمن.")
        admin_main_menu(chat_id)
    else:
        bot.send_message(chat_id, "❌ كلمة المرور غير صحيحة. استخدم /admin للمحاولة مجدداً.")

@bot.message_handler(commands=['login'])
def login_step1(message):
    chat_id = message.chat.id
    msg = bot.send_message(chat_id, "أدخل *رقم التعريف* الخاص بك (الرقم الموجود في بطاقتك):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, login_step2)

def login_step2(message):
    chat_id = message.chat.id
    user_id = message.text.strip()
    # نتحقق من وجود الرقم في JSON
    member = get_member_by_id(user_id)
    if not member:
        bot.send_message(chat_id, "❌ رقم التعريف غير موجود. تأكد من الرقم ثم أعد المحاولة باستخدام /login")
        return
    msg = bot.send_message(chat_id, "أدخل *كلمة المرور* الخاصة بك:", parse_mode='Markdown')
    bot.register_next_step_handler(msg, lambda m: login_step3(m, user_id, member))

def login_step3(message, user_id, member):
    chat_id = message.chat.id
    password = message.text.strip()
    # مقارنة كلمة المرور من JSON (يفترض وجود حقل 'password')
    if member.get('password') != password:
        bot.send_message(chat_id, "❌ كلمة المرور غير صحيحة. استخدم /login للمحاولة مجدداً.")
        return
    # تسجيل الجلسة
    role = get_user_role_from_json(user_id)  # 'member' أو 'volunteer'
    c.execute("REPLACE INTO sessions (chat_id, user_id, full_name, role, status) VALUES (?, ?, ?, ?, ?)",
              (chat_id, user_id, member.get('fullName'), role, 'active'))
    conn.commit()
    user_sessions[chat_id] = user_id
    bot.send_message(chat_id, f"✅ مرحباً {member.get('fullName')}، لقد تم تسجيل دخولك بنجاح.")
    # عرض القائمة المناسبة
    user_main_menu(chat_id, member)

# ------------------- معالجة أزرار العضو/المتطوع -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("user_") or call.data.startswith("volunteer_"))
def user_callbacks(call):
    chat_id = call.message.chat.id
    user_id = user_sessions.get(chat_id)
    if not user_id or is_admin_mode(chat_id):
        bot.answer_callback_query(call.id, "يرجى تسجيل الدخول أولاً باستخدام /login", show_alert=True)
        return
    member = get_member_by_id(user_id)
    if not member:
        bot.answer_callback_query(call.id, "بياناتك غير موجودة، يرجى التواصل مع الإدارة", show_alert=True)
        return

    data = call.data
    if data == "user_profile":
        # إرسال صورة البطاقة مع البيانات
        card_img = generate_member_card(member)
        caption = f"*بطاقة العضوية*\nالاسم: {member.get('fullName')}\nالنوع: {member.get('type', 'عضو')}\nرقم العضوية: {member.get('id')}\nالخلية: {member.get('cell', '-')}\nالمنصب: {member.get('position', '-')}\nتاريخ الانتهاء: {member.get('expiryDate', 'غير محدد')}"
        bot.send_photo(chat_id, card_img, caption=caption, parse_mode='Markdown')
        bot.answer_callback_query(call.id)

    elif data == "user_send_message":
        msg = bot.send_message(chat_id, "✏️ أدخل *عنوان* الرسالة:")
        bot.register_next_step_handler(msg, process_message_subject, member)

    elif data == "user_attendance_self":
        # تسجيل حضور ذاتي
        today = datetime.date.today().isoformat()
        now_time = datetime.datetime.now().strftime("%H:%M")
        c.execute("INSERT INTO attendance (user_id, full_name, date, time) VALUES (?, ?, ?, ?)",
                  (member.get('id'), member.get('fullName'), today, now_time))
        conn.commit()
        bot.answer_callback_query(call.id, "تم تسجيل حضورك بنجاح ✅", show_alert=True)
        bot.send_message(chat_id, f"شكراً لك {member.get('fullName')}، تم تسجيل حضورك اليوم {today} الساعة {now_time}.")

    elif data == "user_idea":
        msg = bot.send_message(chat_id, "💡 شاركنا فكرتك أو مبادرتك المقترحة (نص حر):")
        bot.register_next_step_handler(msg, save_idea_request, member)

    elif data == "user_donate":
        msg = bot.send_message(chat_id, "🤝 كم ترغب في التبرع؟ (أدخل المبلغ بالدينار الجزائري):")
        bot.register_next_step_handler(msg, save_donation_request, member)

    elif data == "user_renew":
        # إرسال طلب تجديد للإدارة
        c.execute("INSERT INTO requests (from_user_id, from_name, request_type, details, date) VALUES (?, ?, ?, ?, ?)",
                  (member.get('id'), member.get('fullName'), 'تجديد العهدة', f"طلب تجديد العهدة المنتهية في {member.get('expiryDate')}", datetime.datetime.now().isoformat()))
        conn.commit()
        bot.answer_callback_query(call.id, "تم إرسال طلب تجديد العهدة إلى الإدارة.", show_alert=True)

    elif data == "user_update_data":
        msg = bot.send_message(chat_id, "أرسل البيانات الجديدة التي تريد تعديلها (مثال: الهاتف القديم/الجديد، العنوان، البريد الإلكتروني):")
        bot.register_next_step_handler(msg, save_update_request, member)

    elif data == "user_request_cert":
        msg = bot.send_message(chat_id, "أدخل سبب طلب الشهادة (مثلاً: شهادة تقدير لمشاركتك في ورشة العمل):")
        bot.register_next_step_handler(msg, save_cert_request, member)

    elif data == "user_request_letter":
        msg = bot.send_message(chat_id, "أدخل الجهة المراد إرسال الخطاب إليها وسبب الطلب:")
        bot.register_next_step_handler(msg, save_letter_request, member)

    elif data == "volunteer_tasks":
        # عرض المهام الموكلة للمتطوع (يمكن توسيعها حسب قاعدة بيانات)
        bot.send_message(chat_id, "📋 قائمة مهامك الحالية:\n- متابعة ملفات الأعضاء الجدد\n- تجهيز تقرير النشاط الأسبوعي\nيمكنك إضافة مهام جديدة عن طريق إرسال طلب للإدارة.")

def process_message_subject(message, member):
    subject = message.text
    msg = bot.send_message(message.chat.id, "أدخل *نص* الرسالة:")
    bot.register_next_step_handler(msg, lambda m: save_message(m, member, subject))

def save_message(message, member, subject):
    body = message.text
    c.execute("INSERT INTO messages (from_user_id, from_name, to_user_id, subject, body, date, is_read) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (member.get('id'), member.get('fullName'), 'ADMIN', subject, body, datetime.datetime.now().isoformat(), 0))
    conn.commit()
    bot.send_message(message.chat.id, "✅ تم إرسال رسالتك إلى الإدارة. ستتلقى رداً عند مراجعة الأدمن.")

def save_idea_request(message, member):
    idea = message.text
    c.execute("INSERT INTO requests (from_user_id, from_name, request_type, details, date) VALUES (?, ?, ?, ?, ?)",
              (member.get('id'), member.get('fullName'), 'مبادرة مقترحة', idea, datetime.datetime.now().isoformat()))
    conn.commit()
    bot.send_message(message.chat.id, "شكراً لمقترحك. سيتم دراسته من قبل الإدارة.")

def save_donation_request(message, member):
    amount = message.text
    c.execute("INSERT INTO requests (from_user_id, from_name, request_type, details, date) VALUES (?, ?, ?, ?, ?)",
              (member.get('id'), member.get('fullName'), 'تبرع', f"مبلغ {amount} دج", datetime.datetime.now().isoformat()))
    conn.commit()
    bot.send_message(message.chat.id, "جزيل الشكر على تبرعك. سيتم التواصل معك لتأكيد البيانات.")

def save_update_request(message, member):
    details = message.text
    c.execute("INSERT INTO requests (from_user_id, from_name, request_type, details, date) VALUES (?, ?, ?, ?, ?)",
              (member.get('id'), member.get('fullName'), 'تعديل بيانات', details, datetime.datetime.now().isoformat()))
    conn.commit()
    bot.send_message(message.chat.id, "تم تسجيل طلب تعديل البيانات. سيتم المراجعة.")

def save_cert_request(message, member):
    reason = message.text
    c.execute("INSERT INTO requests (from_user_id, from_name, request_type, details, date) VALUES (?, ?, ?, ?, ?)",
              (member.get('id'), member.get('fullName'), 'شهادة تقدير', reason, datetime.datetime.now().isoformat()))
    conn.commit()
    bot.send_message(message.chat.id, "تم طلب شهادة تقدير. ستتلقى رداً من الإدارة قريباً.")

def save_letter_request(message, member):
    details = message.text
    c.execute("INSERT INTO requests (from_user_id, from_name, request_type, details, date) VALUES (?, ?, ?, ?, ?)",
              (member.get('id'), member.get('fullName'), 'خطاب رسمي', details, datetime.datetime.now().isoformat()))
    conn.commit()
    bot.send_message(message.chat.id, "تم طلب خطاب رسمي. سيتم الرد عليك.")

# ------------------- معالجة أزرار الأدمن -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callbacks(call):
    chat_id = call.message.chat.id
    if not is_admin_mode(chat_id):
        bot.answer_callback_query(call.id, "ليس لديك صلاحية", show_alert=True)
        return
    data = call.data
    if data == "admin_members":
        show_all_members(chat_id)
    elif data == "admin_add_user":
        add_user_start(call)
    elif data == "admin_inbox":
        show_inbox(chat_id)
    elif data == "admin_stats":
        show_stats(chat_id)
    elif data == "admin_certs":
        show_certificates(chat_id)
    elif data == "admin_letters":
        show_letters(chat_id)
    elif data == "admin_reports":
        show_reports(chat_id)
    elif data == "admin_attendance":
        show_attendance_menu(chat_id)
    elif data == "admin_broadcast":
        msg = bot.send_message(chat_id, "أدخل نص الإشعار الجماعي الذي تريد إرساله لجميع الأعضاء المسجلين:")
        bot.register_next_step_handler(msg, broadcast_message)
    elif data == "admin_initiatives":
        show_initiatives(chat_id)
    elif data == "admin_activities":
        show_activities(chat_id)
    elif data == "admin_requests":
        show_requests(chat_id)
    elif data == "admin_logout":
        c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
        conn.commit()
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, "تم تسجيل الخروج من وضع الإدارة. استخدم /login أو /admin للدخول مجدداً.")

def show_all_members(chat_id):
    members = get_members_from_json()
    if not members:
        bot.send_message(chat_id, "لا توجد بيانات أعضاء حالياً.")
        return
    text = "📋 *قائمة الأعضاء والمتطوعين*\n\n"
    for m in members:
        role = "متطوع" if (m.get('type') == 'موظف' or m.get('cadreType') == 'موظف') else "عضو"
        text += f"• {m.get('fullName')} ({role}) - رقم: {m.get('id')}\n"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def add_user_start(call):
    chat_id = call.message.chat.id
    msg = bot.send_message(chat_id, "أدخل نوع المستخدم (عضو / متطوع):")
    bot.register_next_step_handler(msg, add_user_type)

def add_user_type(message):
    user_type = message.text.strip()
    if user_type not in ['عضو', 'متطوع']:
        bot.send_message(message.chat.id, "نوع غير صحيح. أعد المحاولة باستخدام /admin ثم اختر إضافة مستخدم")
        return
    msg = bot.send_message(message.chat.id, "أدخل الاسم الكامل:")
    bot.register_next_step_handler(msg, add_user_name, user_type)

def add_user_name(message, user_type):
    full_name = message.text
    msg = bot.send_message(message.chat.id, "أدخل رقم الهاتف (اختياري):")
    bot.register_next_step_handler(msg, add_user_phone, user_type, full_name)

def add_user_phone(message, user_type, full_name):
    phone = message.text
    msg = bot.send_message(message.chat.id, "أدخل تاريخ الانتهاء (مثال: 2026-12-31) أو اكتب 'بدون':")
    bot.register_next_step_handler(msg, add_user_expiry, user_type, full_name, phone)

def add_user_expiry(message, user_type, full_name, phone):
    expiry = message.text if message.text != 'بدون' else ''
    # توليد رقم تعريف فريد
    new_id = f"NZ{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    # إضافة إلى قاعدة البيانات المحلية فقط (نحتفظ بها للمزامنة لاحقاً، لكن JSON خارجي)
    # ننشئ سجل عضو في جدول sessions (للسماح بدخوله لاحقاً) ونضيفه أيضاً إلى ملف JSON؟ نكتفي بقاعدة البيانات المحلية للجلسات
    c.execute("INSERT INTO sessions (chat_id, user_id, full_name, role, status) VALUES (?, ?, ?, ?, ?)",
              (0, new_id, full_name, ('volunteer' if user_type=='متطوع' else 'member'), 'active'))
    conn.commit()
    # نضيف أيضاً طلب إضافة إلى JSON؟ يمكن إضافة طلب للإدارة ليتم رفعه يدوياً.
    bot.send_message(message.chat.id, f"✅ تم إضافة {user_type}:\nالاسم: {full_name}\nالرقم: {new_id}\nكلمة المرور مؤقتة: 123456\n(يجب إضافة هذه البيانات إلى ملف JSON يدوياً لتفعيل الدخول الكامل)")

def show_inbox(chat_id):
    msgs = c.execute("SELECT id, from_user_id, from_name, subject, date, is_read FROM messages WHERE to_user_id='ADMIN' ORDER BY id DESC").fetchall()
    if not msgs:
        bot.send_message(chat_id, "📭 لا توجد رسائل حالياً.")
        return
    for m in msgs:
        read_status = "✅ مقروءة" if m[5] else "🆕 جديدة"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📖 عرض الرسالة والرد", callback_data=f"admin_view_msg_{m[0]}"))
        bot.send_message(chat_id, f"*من:* {m[2]} ({m[1]})\n*الموضوع:* {m[3]}\n*التاريخ:* {m[4]}\n*الحالة:* {read_status}", parse_mode='Markdown', reply_markup=markup)
        if not m[5]:
            c.execute("UPDATE messages SET is_read=1 WHERE id=?", (m[0],))
            conn.commit()

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_view_msg_"))
def view_message_details(call):
    msg_id = int(call.data.split("_")[3])
    msg = c.execute("SELECT from_user_id, from_name, subject, body, date FROM messages WHERE id=?", (msg_id,)).fetchone()
    if not msg:
        bot.answer_callback_query(call.id, "الرسالة غير موجودة")
        return
    text = f"*من:* {msg[1]} ({msg[0]})\n*الموضوع:* {msg[2]}\n*التاريخ:* {msg[4]}\n\n*النص:*\n{msg[3]}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✉️ رد على هذه الرسالة", callback_data=f"admin_reply_{msg_id}_{msg[0]}_{msg[1]}"))
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reply_"))
def reply_to_message(call):
    parts = call.data.split("_")
    original_msg_id = int(parts[2])
    to_user_id = parts[3]
    to_name = parts[4]
    msg = bot.send_message(call.message.chat.id, f"أكتب ردك على العضو {to_name} ({to_user_id}):")
    bot.register_next_step_handler(msg, send_reply_to_member, original_msg_id, to_user_id, to_name)

def send_reply_to_member(message, original_msg_id, to_user_id, to_name):
    reply_body = message.text
    c.execute("INSERT INTO messages (from_user_id, from_name, to_user_id, subject, body, date, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?)",
              ('ADMIN', 'مدير النظام', to_user_id, f"رد على رسالتك", reply_body, datetime.datetime.now().isoformat(), original_msg_id))
    conn.commit()
    bot.send_message(message.chat.id, "✅ تم إرسال الرد.")
    # محاولة إرسال الرد للمستخدم الأصلي إذا كان لديه جلسة مفتوحة
    # نبحث عن chat_id الخاص به
    user_chat = c.execute("SELECT chat_id FROM sessions WHERE user_id=?", (to_user_id,)).fetchone()
    if user_chat:
        try:
            bot.send_message(user_chat[0], f"📩 *لديك رد جديد من الإدارة*\n\n{reply_body}", parse_mode='Markdown')
        except:
            pass

def show_stats(chat_id):
    total_members = len(get_members_from_json())
    total_msgs = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_attendance = c.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    total_requests = c.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    text = f"📊 *إحصائيات منصة نزاهة*\n\n👥 عدد الأعضاء المسجلين: {total_members}\n📨 عدد الرسائل المتبادلة: {total_msgs}\n✅ عدد تسجيلات الحضور: {total_attendance}\n📋 عدد الطلبات المقدمة: {total_requests}"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_certificates(chat_id):
    certs = c.execute("SELECT id, full_name, title, date FROM certificates ORDER BY id DESC").fetchall()
    if not certs:
        bot.send_message(chat_id, "لا توجد شهادات بعد.")
        return
    text = "📜 *قائمة الشهادات الصادرة*\n\n"
    for cert in certs:
        text += f"#{cert[0]} - {cert[1]} : {cert[2]} (تاريخ {cert[3]})\n"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_letters(chat_id):
    letters = c.execute("SELECT id, to_whom, subject, date FROM letters ORDER BY id DESC").fetchall()
    if not letters:
        bot.send_message(chat_id, "لا توجد خطابات مسجلة.")
        return
    text = "✉️ *الخطابات الرسمية*\n\n"
    for l in letters:
        text += f"#{l[0]} - إلى: {l[1]} ، الموضوع: {l[2]} (تاريخ {l[3]})\n"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_reports(chat_id):
    reports = c.execute("SELECT id, title, type, date FROM reports ORDER BY id DESC").fetchall()
    if not reports:
        bot.send_message(chat_id, "لا توجد تقارير مسجلة.")
        return
    text = "📄 *التقارير الصادرة*\n\n"
    for r in reports:
        text += f"#{r[0]} - {r[1]} ({r[2]}) - تاريخ {r[3]}\n"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_attendance_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("تسجيل حضور يدوي (برقم العضوية)", callback_data="admin_attendance_manual"))
    markup.add(InlineKeyboardButton("عرض سجل الحضور اليومي", callback_data="admin_view_attendance"))
    bot.send_message(chat_id, "اختر خدمة الحضور:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "admin_attendance_manual")
def manual_attendance(call):
    msg = bot.send_message(call.message.chat.id, "أدخل رقم العضوية للعضو الذي تريد تسجيل حضوره:")
    bot.register_next_step_handler(msg, manual_attendance_record)

def manual_attendance_record(message):
    user_id = message.text.strip()
    member = get_member_by_id(user_id)
    if not member:
        bot.send_message(message.chat.id, "❌ رقم العضوية غير موجود.")
        return
    today = datetime.date.today().isoformat()
    now_time = datetime.datetime.now().strftime("%H:%M")
    c.execute("INSERT INTO attendance (user_id, full_name, date, time) VALUES (?, ?, ?, ?)",
              (user_id, member.get('fullName'), today, now_time))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم تسجيل حضور {member.get('fullName')} بنجاح.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_view_attendance")
def view_attendance(call):
    today = datetime.date.today().isoformat()
    records = c.execute("SELECT full_name, time FROM attendance WHERE date=? ORDER BY time DESC", (today,)).fetchall()
    if not records:
        bot.send_message(call.message.chat.id, f"لا يوجد حضور مسجل لليوم {today}.")
        return
    text = f"✅ *سجل الحضور ليوم {today}*\n\n"
    for r in records:
        text += f"• {r[0]} - الساعة {r[1]}\n"
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

def broadcast_message(message):
    chat_id = message.chat.id
    text = message.text
    # الحصول على جميع المستخدمين المسجلين في الجلسات (الذين دخلوا مرة واحدة)
    users = c.execute("SELECT chat_id FROM sessions WHERE role != 'admin'").fetchall()
    sent = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 *إشعار من الإدارة*\n\n{text}", parse_mode='Markdown')
            sent += 1
        except:
            pass
    bot.send_message(chat_id, f"تم إرسال الإشعار إلى {sent} مستخدم.")

def show_initiatives(chat_id):
    # يمكن جلب المبادرات من JSON آخر، أو نعرض نموذج
    bot.send_message(chat_id, "💡 المبادرات الحالية:\n- مبادرة تعزيز النزاهة في الجامعات\n- حملة 'شباب بلا فساد'\n- برنامج تدريب سفراء النزاهة")
    # يمكن توسيعها باستخدام قاعدة بيانات

def show_activities(chat_id):
    activities = c.execute("SELECT title, date, location FROM activities ORDER BY date DESC").fetchall()
    if not activities:
        bot.send_message(chat_id, "لا توجد نشاطات مسجلة حالياً.")
        return
    text = "📅 *النشاطات القادمة والسابقة*\n\n"
    for a in activities:
        text += f"• {a[0]} - {a[1]} - {a[2]}\n"
    bot.send_message(chat_id, text, parse_mode='Markdown')

def show_requests(chat_id):
    reqs = c.execute("SELECT id, from_name, request_type, details, date, status FROM requests ORDER BY id DESC").fetchall()
    if not reqs:
        bot.send_message(chat_id, "لا توجد طلبات حالياً.")
        return
    for r in reqs:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ تم المعالجة", callback_data=f"admin_req_done_{r[0]}"))
        text = f"📋 *طلب #{r[0]}*\nمن: {r[1]}\nالنوع: {r[2]}\nالتفاصيل: {r[3]}\nالتاريخ: {r[4]}\nالحالة: {r[5]}"
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_req_done_"))
def mark_request_done(call):
    req_id = int(call.data.split("_")[3])
    c.execute("UPDATE requests SET status='completed' WHERE id=?", (req_id,))
    conn.commit()
    bot.answer_callback_query(call.id, "تم تحديث حالة الطلب إلى مكتمل.")

# ------------------- تشغيل البوت مع إعادة تشغيل تلقائي -------------------
def start_bot():
    while True:
        try:
            logging.info("بوت نزاهة يعمل الآن...")
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            logging.error(f"توقف البوت: {e}. إعادة التشغيل خلال 5 ثوانٍ...")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
