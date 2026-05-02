#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
نظام نزاهة الرقمي - المنتدى الشبابي للفكر والمشاركة المدنية
الإصدار 3.0 - مع التفريق الكامل بين الأدوار
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import datetime
import logging
import os
import time

# ========== الإعدادات ==========
TOKEN = '8459034854:AAFOvbK3i2jJS8fNkGP8TAS6F2yvW6c_UiE'
MASTER_ID = 6631351306  # معرف الرئيس (نزيه بومهدي)
SECRET_ADMIN_COMMAND = 'nazaha2026'  # الأمر السري الاحتياطي

bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ========== قاعدة البيانات ==========
conn = sqlite3.connect('nazaha.db', check_same_thread=False)
c = conn.cursor()

# جدول المستخدمين
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    full_name TEXT,
    status TEXT DEFAULT 'pending',   -- pending, activated, rejected
    role TEXT DEFAULT 'member',      -- member (منخرط), volunteer (متطوع), master (رئيس)
    registered_at TEXT,
    activated_by INTEGER
)''')

# جدول المهام
c.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    assigned_to INTEGER,
    assigned_by INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    completed_at TEXT
)''')

# جدول رسائل الدعم
c.execute('''CREATE TABLE IF NOT EXISTS support (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER,
    from_name TEXT,
    message TEXT,
    date TEXT,
    is_read INTEGER DEFAULT 0
)''')

# جدول الإعلانات
c.execute('''CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    created_by INTEGER,
    created_at TEXT
)''')

# جدول الجلسات المؤقتة
c.execute('''CREATE TABLE IF NOT EXISTS sessions (
    chat_id INTEGER PRIMARY KEY,
    step TEXT
)''')

# إضافة الرئيس إلى قاعدة البيانات إذا لم يكن موجوداً
c.execute("INSERT OR IGNORE INTO users (telegram_id, full_name, status, role, registered_at) VALUES (?, ?, ?, ?, ?)",
          (MASTER_ID, 'نزيه بومهدي', 'activated', 'master', datetime.datetime.now().isoformat()))
conn.commit()

# ========== دوال التحقق من الصلاحيات ==========
def is_master(telegram_id):
    """التحقق إذا كان المستخدم هو الرئيس"""
    return telegram_id == MASTER_ID

def is_volunteer(telegram_id):
    c.execute("SELECT role FROM users WHERE telegram_id=? AND status='activated'", (telegram_id,))
    row = c.fetchone()
    return row and row[0] == 'volunteer'

def is_member(telegram_id):
    c.execute("SELECT role FROM users WHERE telegram_id=? AND status='activated'", (telegram_id,))
    row = c.fetchone()
    return row and row[0] == 'member'

def is_activated(telegram_id):
    c.execute("SELECT status FROM users WHERE telegram_id=?", (telegram_id,))
    row = c.fetchone()
    return row and row[0] == 'activated'

def get_user_role(telegram_id):
    c.execute("SELECT role FROM users WHERE telegram_id=?", (telegram_id,))
    row = c.fetchone()
    return row[0] if row else None

# ========== دوال مساعدة ==========
def add_user(telegram_id, full_name):
    c.execute("INSERT OR IGNORE INTO users (telegram_id, full_name, registered_at) VALUES (?, ?, ?)",
              (telegram_id, full_name, datetime.datetime.now().isoformat()))
    conn.commit()

def update_user_status(telegram_id, status, role=None):
    if role:
        c.execute("UPDATE users SET status=?, role=? WHERE telegram_id=?", (status, role, telegram_id))
    else:
        c.execute("UPDATE users SET status=? WHERE telegram_id=?", (status, telegram_id))
    conn.commit()

def get_all_activated_users():
    c.execute("SELECT telegram_id, full_name, role FROM users WHERE status='activated'")
    return c.fetchall()

def get_volunteers():
    c.execute("SELECT telegram_id, full_name FROM users WHERE status='activated' AND role='volunteer'")
    return c.fetchall()

def get_pending_users():
    c.execute("SELECT telegram_id, full_name, registered_at FROM users WHERE status='pending'")
    return c.fetchall()

def add_task(assigned_to, title, description, assigned_by):
    c.execute("INSERT INTO tasks (assigned_to, title, description, assigned_by, created_at) VALUES (?, ?, ?, ?, ?)",
              (assigned_to, title, description, assigned_by, datetime.datetime.now().isoformat()))
    conn.commit()
    return c.lastrowid

def get_user_tasks(telegram_id):
    c.execute("SELECT id, title, description, status, created_at FROM tasks WHERE assigned_to=? ORDER BY id DESC", (telegram_id,))
    return c.fetchall()

def update_task_status(task_id, status):
    if status == 'completed':
        c.execute("UPDATE tasks SET status=?, completed_at=? WHERE id=?", (status, datetime.datetime.now().isoformat(), task_id))
    else:
        c.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
    conn.commit()

def add_support_message(from_user_id, from_name, message):
    c.execute("INSERT INTO support (from_user_id, from_name, message, date) VALUES (?, ?, ?, ?)",
              (from_user_id, from_name, message, datetime.datetime.now().isoformat()))
    conn.commit()
    return c.lastrowid

def get_unread_support_messages():
    c.execute("SELECT id, from_name, message, date FROM support WHERE is_read=0 ORDER BY id ASC")
    return c.fetchall()

def mark_support_as_read(msg_id):
    c.execute("UPDATE support SET is_read=1 WHERE id=?", (msg_id,))
    conn.commit()

def add_announcement(content, created_by):
    c.execute("INSERT INTO announcements (content, created_by, created_at) VALUES (?, ?, ?)",
              (content, created_by, datetime.datetime.now().isoformat()))
    conn.commit()

# ========== دوال واجهة المستخدم ==========
def start_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("/تسجيل"))
    markup.add(KeyboardButton("/مساعدة"))
    bot.send_message(chat_id, 
        "🏛️ *مرحباً بك في نظام نزاهة*\n"
        "المنتدى الشبابي للفكر والمشاركة المدنية\n\n"
        "للاستفادة من خدماتنا، يرجى تسجيل الدخول باستخدام الأمر `/تسجيل`",
        parse_mode='Markdown', reply_markup=markup)

def master_panel(chat_id):
    """لوحة الرئيس (تظهر تلقائياً للمعرف 6631351306 أو لمن يعرف الأمر السري)"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("👥 طلبات الانضمام", callback_data="master_pending"),
        InlineKeyboardButton("📋 المهام", callback_data="master_tasks"),
        InlineKeyboardButton("📨 رسائل الدعم", callback_data="master_support"),
        InlineKeyboardButton("📢 إعلان عام", callback_data="master_announce"),
        InlineKeyboardButton("➕ إسناد مهمة", callback_data="master_new_task"),
        InlineKeyboardButton("📊 الإحصائيات", callback_data="master_stats"),
        InlineKeyboardButton("🚪 خروج", callback_data="master_logout")
    )
    bot.send_message(chat_id, "🛡️ *لوحة تحكم الرئيس - نظام نزاهة*\nاختر الخدمة:", parse_mode='Markdown', reply_markup=markup)

def volunteer_panel(chat_id, full_name):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📋 مهامي", callback_data="volunteer_tasks"),
        InlineKeyboardButton("📥 تأكيد استلام مهمة", callback_data="volunteer_confirm"),
        InlineKeyboardButton("📊 رفع تقرير", callback_data="volunteer_report")
    )
    bot.send_message(chat_id, f"👋 أهلاً *{full_name}* (متطوع)\nاختر الخدمة:", parse_mode='Markdown', reply_markup=markup)

def member_panel(chat_id, full_name):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💬 دعم فني", callback_data="member_support"),
        InlineKeyboardButton("📜 طلباتي", callback_data="member_requests")
    )
    bot.send_message(chat_id, f"👋 أهلاً *{full_name}* (منخرط)\nاختر الخدمة:", parse_mode='Markdown', reply_markup=markup)

def route_to_panel(chat_id):
    """توجيه المستخدم إلى اللوحة المناسبة حسب دوره"""
    if is_master(chat_id):
        master_panel(chat_id)
        return
    c.execute("SELECT full_name, role FROM users WHERE telegram_id=? AND status='activated'", (chat_id,))
    row = c.fetchone()
    if row:
        if row[1] == 'volunteer':
            volunteer_panel(chat_id, row[0])
        else:
            member_panel(chat_id, row[0])
    else:
        bot.send_message(chat_id, "حسابك غير مفعل بعد. يرجى الانتظار حتى يتم تفعيله من قبل الإدارة.")

# ========== أوامر البوت ==========
@bot.message_handler(commands=['start'])
def cmd_start(message):
    start_menu(message.chat.id)

@bot.message_handler(commands=['تسجيل'])
def cmd_register(message):
    chat_id = message.chat.id
    user = c.execute("SELECT status FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
    if user and user[0] == 'activated':
        bot.send_message(chat_id, "✅ أنت مسجل بالفعل.")
        route_to_panel(chat_id)
        return
    if user and user[0] == 'pending':
        bot.send_message(chat_id, "⏳ طلبك قيد المراجعة، سيتم إعلامك عند التفعيل.")
        return
    msg = bot.send_message(chat_id, "📝 *تسجيل جديد*\nالرجاء إدخال اسمك الكامل (الاسم واللقب):", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_registration)

def process_registration(message):
    chat_id = message.chat.id
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        bot.send_message(chat_id, "❌ يرجى إدخال الاسم واللقب كاملين (مثال: أحمد محمد).")
        cmd_register(message)
        return
    add_user(chat_id, full_name)
    bot.send_message(chat_id, "✅ تم استلام طلبك. سيتم مراجعته من قبل الإدارة.")
    # إشعار الرئيس (Master)
    bot.send_message(MASTER_ID, f"🔔 *طلب انضمام جديد*\nالاسم: {full_name}\nالمعرف: `{chat_id}`\nاستخدم لوحة التحكم للموافقة أو الرفض.", parse_mode='Markdown')

@bot.message_handler(commands=['nazaha2026'])
def secret_master_login(message):
    """الأمر السري للوصول إلى لوحة الرئيس (احتياطي)"""
    chat_id = message.chat.id
    if is_master(chat_id):
        master_panel(chat_id)
    else:
        bot.send_message(chat_id, "⚠️ هذا الأمر غير معروف.")

@bot.message_handler(commands=['مساعدة'])
def cmd_help(message):
    help_text = """
📖 *دليل استخدام نظام نزاهة*

🔹 *للتسجيل:* استخدم الأمر `/تسجيل` وأدخل اسمك الكامل.
🔹 *بعد التفعيل:* ستظهر لك القائمة المناسبة حسب دورك (منخرط/متطوع).

*الخدمات المتاحة:*
- **المنخرط:** دعم فني، متابعة الطلبات.
- **المتطوع:** مهام، تأكيد استلام، رفع تقارير.
- **الرئيس:** لوحة تحكم كاملة (تظهر تلقائياً لصاحب الصلاحية).

للاستفسار، تواصل مع الإدارة.
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ========== معالجة أزرار الرئيس ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith('master_'))
def master_callbacks(call):
    chat_id = call.message.chat.id
    if not is_master(chat_id):
        bot.answer_callback_query(call.id, "غير مصرح", show_alert=True)
        return
    data = call.data

    if data == 'master_pending':
        pendings = get_pending_users()
        if not pendings:
            bot.send_message(chat_id, "📭 لا توجد طلبات معلقة.")
        else:
            for p in pendings:
                markup = InlineKeyboardMarkup()
                markup.add(
                    InlineKeyboardButton("✅ تفعيل كمنخرط", callback_data=f"activate_member_{p[0]}"),
                    InlineKeyboardButton("🔵 تفعيل كمتطوع", callback_data=f"activate_volunteer_{p[0]}"),
                    InlineKeyboardButton("❌ رفض", callback_data=f"reject_{p[0]}")
                )
                bot.send_message(chat_id, f"👤 *{p[1]}*\n🆔 {p[0]}\n📅 تاريخ التسجيل: {p[2][:10]}", parse_mode='Markdown', reply_markup=markup)
    elif data == 'master_tasks':
        c.execute("SELECT tasks.id, users.full_name, tasks.title, tasks.status FROM tasks JOIN users ON tasks.assigned_to=users.telegram_id ORDER BY tasks.id DESC")
        tasks = c.fetchall()
        if not tasks:
            bot.send_message(chat_id, "📭 لا توجد مهام.")
        else:
            text = "📋 *قائمة المهام*\n\n"
            for t in tasks:
                text += f"#{t[0]} - {t[1]} : {t[2]}\n   الحالة: {t[3]}\n\n"
            bot.send_message(chat_id, text[:4000], parse_mode='Markdown')
    elif data == 'master_support':
        msgs = get_unread_support_messages()
        if not msgs:
            bot.send_message(chat_id, "📭 لا توجد رسائل دعم جديدة.")
        else:
            for msg in msgs:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("✅ تم القراءة", callback_data=f"mark_read_{msg[0]}"))
                bot.send_message(chat_id, f"📨 *من:* {msg[1]}\n\n{msg[2]}\n📅 {msg[3][:16]}", parse_mode='Markdown', reply_markup=markup)
    elif data == 'master_announce':
        msg = bot.send_message(chat_id, "📢 *إعلان عام*\nأرسل نص الإعلان:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_master_announcement)
    elif data == 'master_new_task':
        volunteers = get_volunteers()
        if not volunteers:
            bot.send_message(chat_id, "⚠️ لا يوجد متطوعين مفعلين.")
        else:
            markup = InlineKeyboardMarkup()
            for v in volunteers:
                markup.add(InlineKeyboardButton(v[1], callback_data=f"select_vol_{v[0]}"))
            bot.send_message(chat_id, "🔹 اختر المتطوع:", reply_markup=markup)
    elif data == 'master_stats':
        c.execute("SELECT COUNT(*) FROM users WHERE status='activated' AND role='member'")
        members = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE status='activated' AND role='volunteer'")
        volunteers = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM tasks WHERE status='pending' OR status='received'")
        pending_tasks = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM support WHERE is_read=0")
        unread_support = c.fetchone()[0]
        text = f"📊 *الإحصائيات*\n\n👥 المنخرطين: {members}\n🔹 المتطوعين: {volunteers}\n📋 مهام قيد التنفيذ: {pending_tasks}\n📨 رسائل دعم جديدة: {unread_support}"
        bot.send_message(chat_id, text, parse_mode='Markdown')
    elif data == 'master_logout':
        bot.send_message(chat_id, "👋 تم تسجيل الخروج.")
        start_menu(chat_id)
    bot.answer_callback_query(call.id)

def process_master_announcement(message):
    chat_id = message.chat.id
    if not is_master(chat_id):
        return
    content = message.text
    add_announcement(content, MASTER_ID)
    users = get_all_activated_users()
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], f"📢 *إعلان من الرئيس*\n\n{content}", parse_mode='Markdown')
            count += 1
        except:
            pass
    bot.send_message(chat_id, f"✅ تم إرسال الإعلان إلى {count} مستخدم.")
    master_panel(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('activate_member_', 'activate_volunteer_', 'reject_')))
def handle_activation(call):
    chat_id = call.message.chat.id
    if not is_master(chat_id):
        bot.answer_callback_query(call.id, "غير مصرح", show_alert=True)
        return
    parts = call.data.split('_')
    action = parts[0]
    user_id = int(parts[2])
    if action == 'activate':
        role = 'member' if 'member' in call.data else 'volunteer'
        update_user_status(user_id, 'activated', role)
        bot.edit_message_text(f"✅ تم تفعيل المستخدم كـ {'منخرط' if role=='member' else 'متطوع'}.", chat_id, call.message.message_id)
        try:
            bot.send_message(user_id, f"🎉 *تم قبول طلبك!*\nمرحباً بك في منتدى نزاهة. استخدم `/start` للوصول إلى الخدمات.", parse_mode='Markdown')
        except:
            pass
    elif action == 'reject':
        update_user_status(user_id, 'rejected')
        bot.edit_message_text("❌ تم رفض الطلب.", chat_id, call.message.message_id)
        try:
            bot.send_message(user_id, "عذراً، لم يتم قبول طلبك حالياً. يمكنك التواصل مع الإدارة.")
        except:
            pass
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_vol_'))
def select_volunteer(call):
    chat_id = call.message.chat.id
    if not is_master(chat_id):
        bot.answer_callback_query(call.id, "غير مصرح", show_alert=True)
        return
    volunteer_id = int(call.data.split('_')[2])
    # تخزين المتطوع في الجلسة المؤقتة
    c.execute("REPLACE INTO sessions (chat_id, step) VALUES (?, ?)", (chat_id, f"task_desc_{volunteer_id}"))
    conn.commit()
    bot.send_message(chat_id, "📝 *إضافة مهمة*\nأرسل وصف المهمة (العنوان والتفاصيل):", parse_mode='Markdown')
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: c.execute("SELECT step FROM sessions WHERE chat_id=?", (message.chat.id,)).fetchone() and c.fetchone()[0].startswith('task_desc_'))
def process_task_description(message):
    chat_id = message.chat.id
    if not is_master(chat_id):
        return
    row = c.execute("SELECT step FROM sessions WHERE chat_id=?", (chat_id,)).fetchone()
    if not row:
        return
    step = row[0]
    volunteer_id = int(step.split('_')[2])
    description = message.text
    title = description[:50] if len(description) > 50 else description
    add_task(volunteer_id, title, description, MASTER_ID)
    c.execute("DELETE FROM sessions WHERE chat_id=?", (chat_id,))
    conn.commit()
    bot.send_message(chat_id, f"✅ تم إسناد المهمة إلى المتطوع.")
    try:
        bot.send_message(volunteer_id, "📂 *مهمة جديدة*\nتم إسناد مهمة إليك. استخدم القائمة لعرضها.", parse_mode='Markdown')
    except:
        pass
    master_panel(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('mark_read_'))
def mark_support_read(call):
    chat_id = call.message.chat.id
    if not is_master(chat_id):
        bot.answer_callback_query(call.id, "غير مصرح", show_alert=True)
        return
    msg_id = int(call.data.split('_')[2])
    mark_support_as_read(msg_id)
    bot.edit_message_text("✅ تمت القراءة", chat_id, call.message.message_id)
    bot.answer_callback_query(call.id)

# ========== معالجة أزرار المتطوعين والمنخرطين ==========
@bot.callback_query_handler(func=lambda call: call.data.startswith(('volunteer_', 'member_')))
def user_callbacks(call):
    chat_id = call.message.chat.id
    if not is_activated(chat_id):
        bot.answer_callback_query(call.id, "حسابك غير مفعل بعد.", show_alert=True)
        return
    data = call.data

    if data == 'volunteer_tasks':
        tasks = get_user_tasks(chat_id)
        if not tasks:
            bot.send_message(chat_id, "📭 لا توجد مهام حالياً.")
        else:
            for task in tasks:
                status_text = {'pending':'في الانتظار', 'received':'تم الاستلام', 'completed':'مكتمل'}.get(task[3], task[3])
                markup = InlineKeyboardMarkup()
                if task[3] == 'pending':
                    markup.add(InlineKeyboardButton("📥 تأكيد الاستلام", callback_data=f"task_receive_{task[0]}"))
                elif task[3] == 'received':
                    markup.add(InlineKeyboardButton("✅ تم الإنجاز", callback_data=f"task_complete_{task[0]}"))
                bot.send_message(chat_id, f"📌 *المهمة #{task[0]}*\n*العنوان:* {task[1]}\n*التفاصيل:* {task[2]}\n*الحالة:* {status_text}\n*تاريخ الإسناد:* {task[4][:16]}", parse_mode='Markdown', reply_markup=markup)
    elif data == 'volunteer_confirm':
        tasks = get_user_tasks(chat_id)
        pending = [t for t in tasks if t[3] == 'pending']
        if not pending:
            bot.send_message(chat_id, "لا توجد مهام جديدة لتأكيدها.")
        else:
            for task in pending:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("📥 استلام", callback_data=f"task_receive_{task[0]}"))
                bot.send_message(chat_id, f"مهمة #{task[0]}: {task[1]}", reply_markup=markup)
    elif data == 'volunteer_report':
        msg = bot.send_message(chat_id, "📊 *رفع تقرير إنجاز*\nأرسل تقريرك (نص):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_volunteer_report)
    elif data == 'member_support':
        msg = bot.send_message(chat_id, "💬 *الدعم الفني*\nاكتب رسالتك:", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_member_support)
    elif data == 'member_requests':
        c.execute("SELECT id, message, date, is_read FROM support WHERE from_user_id=? ORDER BY id DESC", (chat_id,))
        msgs = c.fetchall()
        if not msgs:
            bot.send_message(chat_id, "ليس لديك طلبات سابقة.")
        else:
            text = "📜 *طلباتك السابقة*\n\n"
            for m in msgs:
                text += f"#{m[0]} - {m[2][:16]}\n   {m[1][:100]}\n   الحالة: {'تمت القراءة' if m[3] else 'قيد المراجعة'}\n\n"
            bot.send_message(chat_id, text[:4000], parse_mode='Markdown')
    bot.answer_callback_query(call.id)

def process_volunteer_report(message):
    chat_id = message.chat.id
    report_text = message.text
    # إرسال التقرير إلى الرئيس
    bot.send_message(MASTER_ID, f"📊 *تقرير من متطوع*\nالمستخدم: {message.from_user.first_name}\n\n{report_text}", parse_mode='Markdown')
    bot.send_message(chat_id, "✅ تم إرسال تقريرك إلى الرئيس.")
    route_to_panel(chat_id)

def process_member_support(message):
    chat_id = message.chat.id
    support_text = message.text
    user = c.execute("SELECT full_name FROM users WHERE telegram_id=?", (chat_id,)).fetchone()
    name = user[0] if user else "مستخدم"
    add_support_message(chat_id, name, support_text)
    bot.send_message(chat_id, "✅ تم إرسال رسالتك. سيتم الرد عليك قريباً.")
    # إشعار الرئيس
    bot.send_message(MASTER_ID, f"📨 *رسالة دعم جديدة*\nمن: {name}\n\n{support_text[:300]}", parse_mode='Markdown')
    route_to_panel(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('task_receive_', 'task_complete_')))
def handle_task_status(call):
    chat_id = call.message.chat.id
    if not is_activated(chat_id):
        bot.answer_callback_query(call.id, "غير مصرح", show_alert=True)
        return
    action, task_id = call.data.split('_')[1], int(call.data.split('_')[2])
    if action == 'receive':
        update_task_status(task_id, 'received')
        bot.edit_message_text("✅ تم تأكيد استلام المهمة.", chat_id, call.message.message_id)
        bot.send_message(MASTER_ID, f"📢 المتطوع {call.from_user.first_name} استلم المهمة #{task_id}.")
    elif action == 'complete':
        update_task_status(task_id, 'completed')
        bot.edit_message_text("🎉 تم إكمال المهمة! شكراً لك.", chat_id, call.message.message_id)
        bot.send_message(MASTER_ID, f"✅ المتطوع {call.from_user.first_name} أتم المهمة #{task_id} بنجاح.")
    bot.answer_callback_query(call.id)

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
