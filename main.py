import telebot
from PIL import Image
import io
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOKEN = '8459034854:AAFOvbK3i2jJS8fNkGP8TAS6F2yvW6c_UiE'
ADMIN_USERNAME = '@nazihboumahni'

# إحداثيات منطقة الصورة (لقالب 1000×1000)
PHOTO_X = 438
PHOTO_Y = 96
PHOTO_WIDTH = 507
PHOTO_HEIGHT = 522

bot = telebot.TeleBot(TOKEN)

try:
    admin_chat = bot.get_chat(ADMIN_USERNAME)
    ADMIN_ID = admin_chat.id
    logging.info(f"تم العثور على حساب الأدمن: {ADMIN_USERNAME}")
except Exception as e:
    logging.error(f"لم يتم العثور على حساب الأدمن {ADMIN_USERNAME}: {e}")
    ADMIN_ID = None

def has_transparency(img):
    """التحقق مما إذا كانت الصورة تحتوي على بكسلات شفافة"""
    if img.mode != 'RGBA':
        return False
    alpha = img.getchannel('A')
    # إذا كان هناك أي بكسل بقيمة alpha أقل من 255 (شفاف جزئياً أو كلياً)
    if alpha.getextrema() != (255, 255):
        return True
    return False

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "📌 في إطار حملة \"اصنع التغيير\" التي ينظمها المنتدى الشبابي للفكر والمشاركة المدنية - نزاهة، وضمن مساعينا لتمكين الشباب في العمل المدني، ندعوكم للمساهمة في بناء جيل واعٍ ومبادر.\n\n"
        "ندعو شبابنا ليكونوا سفراء لمنتدى نزاهة في توعية أقرانهم بأهمية الانخراط والمشاركة المدنية، حتى لا نترك الساحة فارغة، وليكون فكر الشباب حاضرًا في التأثير وصناعة المستقبل.\n\n"
        "📌 أرسل صورتك الآن وشارك في التوعية لتكون جزءًا من التغيير.\n\n"
        "🔴 ملاحظات:\n\n"
        "📌 إذا لم تنضم بعد لعائلة المنتدى، يمكنك التسجيل عبر الرابط التالي:\n"
        "https://nazaha-dz.vercel.app\n\n"
        "📌 للمشاركة وإضافة صورتك في القالب الرسمي:\n"
        "https://t.me/nazahadz_bot\n\n"
        "📌 شارك تصميمك الآن على حساباتك في مواقع التواصل الاجتماعي، وساهم في نشر الوعي بين أصدقائك.\n\n"
        "📌 كما سيتم نشر صور سفراء \"نزاهة\" عبر منصاتنا الرسمية تقديراً لمبادرتهم.\n\n"
        "المنتدى الشبابي للفكر والمشاركة المدنية – نزاهة\n"
        "نحو جيل واعٍ ومبادر"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    processing_msg = bot.reply_to(message, "جارٍ معالجة الصورة ودمجها مع قالب نزاهة، يرجى الانتظار...")
    
    try:
        # تحميل صورة المستخدم
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        user_img = Image.open(io.BytesIO(downloaded_file)).convert("RGBA")
        
        # تحميل القالب
        try:
            template = Image.open("nazaha_template.png").convert("RGBA")
        except FileNotFoundError:
            bot.edit_message_text(
                "خطأ تقني: لم يتم العثور على ملف القالب (nazaha_template.png). يرجى إبلاغ الإدارة.",
                message.chat.id,
                processing_msg.message_id
            )
            return
        
        # تغيير حجم صورة المستخدم لتتناسب مع المساحة المحددة
        user_img_resized = user_img.resize((PHOTO_WIDTH, PHOTO_HEIGHT))
        
        # التحقق من وجود شفافية في القالب
        if has_transparency(template):
            # طريقة الدمج مع الشفافية: صورة المستخدم خلف القالب
            background = Image.new('RGBA', template.size, (0, 0, 0, 0))
            background.paste(user_img_resized, (PHOTO_X, PHOTO_Y))
            final_img = Image.alpha_composite(background, template)
        else:
            # طريقة الدمج العادي: صورة المستخدم فوق القالب
            final_img = template.copy()
            final_img.paste(user_img_resized, (PHOTO_X, PHOTO_Y), user_img_resized if user_img_resized.mode == 'RGBA' else None)
        
        # تحويل الصورة النهائية إلى بايتات
        output = io.BytesIO()
        final_img.save(output, format="PNG")
        output.seek(0)
        
        caption_text = (
            "تم تجهيز بطاقتك.\n\n"
            "النص المقترح للنشر:\n"
            "—————————————————\n"
            "أنا سفير في المنتدى الشبابي للفكر والمشاركة المدنية (نزاهة)، ضمن حملة #اصنع_التغيير.\n\n"
            "للمشاركة والحصول على بطاقتك الخاصة:\n"
            "https://t.me/nazahadz_bot\n\n"
            "انضم إلينا وكن جزءاً من التغيير:\n"
            "https://nazaha-dz.vercel.app\n\n"
            "#نزاهة #اصنع_التغيير\n"
            "—————————————————\n"
            "@nazaha.dz"
        )
        
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.send_photo(message.chat.id, output, caption=caption_text)
        
        # إرسال نسخة إلى الأدمن
        if ADMIN_ID:
            output.seek(0)
            admin_caption = (
                f"مستخدم جديد:\n"
                f"الاسم: {message.from_user.first_name} {message.from_user.last_name or ''}\n"
                f"المعرف: {message.from_user.id}\n"
                f"اليوزرنيم: @{message.from_user.username if message.from_user.username else 'لا يوجد'}"
            )
            try:
                bot.send_photo(ADMIN_ID, output, caption=admin_caption)
                logging.info(f"تم إرسال الصورة إلى الأدمن للمستخدم {message.from_user.id}")
            except Exception as e:
                logging.error(f"فشل إرسال الصورة للأدمن: {e}")
        
    except Exception as e:
        bot.edit_message_text(
            f"حدث خطأ غير متوقع: {str(e)}",
            message.chat.id,
            processing_msg.message_id
        )
        logging.error(f"خطأ: {e}")

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
