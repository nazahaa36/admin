import telebot
from PIL import Image
import io

# التوكن الخاص بك
TOKEN = '8459034854:AAFOvbK3i2jJS8fNkGP8TAS6F2yvW6c_UiE'
bot = telebot.TeleBot(TOKEN)

# 1. رسالة الترحيب والشرح عند الضغط على /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في بوت 'المنتدى الشبابي للفكر والمشاركة المدنية - نزاهة'! 🦅🇩🇿\n\n"
        "📌 **عن المبادرة:**\n"
        "في إطار حملة 'اصنع التغيير'، نسعى لتمكين الشباب وتعزيز حضورهم في العمل المدني ليكون صوتنا حاضراً في بناء المستقبل.\n\n"
        "📸 **كيف تشارك؟**\n"
        "أرسل صورتك الشخصية الآن، وسأقوم بدمجها فوراً في القالب الرسمي لتصبح سفيراً للمبادرة وتشاركها مع أصدقائك."
    )
    bot.reply_to(message, welcome_text)

# 2. استقبال الصورة ومعالجتها
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    processing_msg = bot.reply_to(message, "⏳ جاري معالجة صورتك ودمجها مع قالب 'نزاهة'...")
    
    try:
        # تحميل صورة المستخدم من تليجرام
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_img = Image.open(io.BytesIO(downloaded_file)).convert("RGBA")

        # فتح قالب المنتدى (يجب أن يكون موجوداً في المجلد)
        try:
            template = Image.open("nazaha_template.png").convert("RGBA")
        except FileNotFoundError:
            bot.edit_message_text("❌ خطأ: لم أجد ملف القالب (nazaha_template.png). يرجى رفعه أولاً.", message.chat.id, processing_msg.message_id)
            return
        
        # ضبط حجم صورة المستخدم لتطابق حجم القالب تماماً
        user_img = user_img.resize(template.size)
        
        # عملية الدمج (صورة المستخدم في الخلف والقالب الشفاف في الأمام)
        final_img = Image.alpha_composite(user_img, template)
        
        # تحويل الصورة النهائية إلى صيغة قابلة للإرسال
        output = io.BytesIO()
        final_img.save(output, format="PNG")
        output.seek(0)
        
        # 3. النص الذي سيظهر للمستخدم عند اكتمال الصورة (جاهز للنسخ)
        caption_text = (
            "✅ تم تجهيز بطاقتك بنجاح!\n\n"
            "📢 **انسخ هذا النص وانشره مع صورتك:**\n"
            "--------------------------\n"
            "أنا انضممت إلى المنتدى الشبابي للفكر والمشاركة المدنية (نزاهة).. 🦅\n\n"
            "لأكون جزءاً من مبادرة #اصنع_التغيير وأساهم في بناء مستقبل وطننا بفكر شبابي واعٍ ومبادر. 🇩🇿\n\n"
            "انضم إلينا الآن وكن سفيراً للتغيير عبر الرابط:\n"
            "https://nazaha-dz.vercel.app\n\n"
            "#نزاهة #رؤية_شباب_الجزائر2030 #اصنع_التغيير\n"
            "--------------------------\n\n"
            "📌 لا تنسَ منشن حسابنا @nazaha.dz لنعيد نشر صورتك!"
        )
        
        # حذف رسالة الانتظار وإرسال الصورة النهائية مع النص
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.send_photo(message.chat.id, output, caption=caption_text)
        
    except Exception as e:
        bot.edit_message_text(f"❌ حدث خطأ غير متوقع: {str(e)}", message.chat.id, processing_msg.message_id)

# تشغيل البوت باستمرار
print("✅ بوت منتدى نزاهة يعمل الآن بنجاح...")
bot.polling()

