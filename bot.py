import logging
import os
import re
import json
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.error import TimedOut, NetworkError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ========== تحميل معرفات الملفات من ملف JSON خارجي ==========
try:
    with open("lecture_file_ids.json", "r", encoding="utf-8") as f:
        LECTURE_FILE_IDS = json.load(f)
    logging.info("تم تحميل معرفات الملفات من lecture_file_ids.json بنجاح.")
except FileNotFoundError:
    logging.error("ملف lecture_file_ids.json غير موجود! تأكد من وجوده في مجلد المشروع.")
    LECTURE_FILE_IDS = {}
except json.JSONDecodeError:
    logging.error("ملف lecture_file_ids.json يحتوي على أخطاء في صيغة JSON.")
    LECTURE_FILE_IDS = {}

# ========== خادم وهمي لإشباع فحص المنفذ في Render ==========
class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def start_fake_server():
    port = int(os.environ.get('PORT', 5000))
    server = HTTPServer(('0.0.0.0', port), FakeHandler)
    logging.info(f'Fake server running on port {port}')
    server.serve_forever()

# مواد لا يوجد بها قسم عملي
MATERIALS_NO_PRACTICAL = [
    "⚖️ حقوق الإنسان ⚖️",
    "📈 Biostatistics 📈",
    "📝 Terminology 📝",
    "💻 Computer Sciences 💻",
    "🗣️ Arabic Language 🗣️",
]

def clean_material_name(raw_name: str) -> str:
    """إزالة الرموز والإيموجي من اسم المادة ليطابق المفاتيح في القاموس."""
    return re.sub(r'[^a-zA-Z0-9\s\u0621-\u064A]', '', raw_name).strip()

def build_course_keyboard(course_location: str) -> list:
    if course_location == 'first_course':
        return [
            ["🧪 Analytical Chemistry 🧪"],
            ["📊 Medical Physics 📊"],
            ["⚖️ حقوق الإنسان ⚖️"],
            ["📈 Biostatistics 📈"],
            ["📝 Terminology 📝"],
            ["🔬 Histology 🔬"],
            ["🦴 Anatomy 🦴"],
            ["⬅️ رجوع"]
        ]
    else:
        return [
            ["🧮 Pharmaceutical Calculations 🧮"],
            ["⚛️ Organic Chemistry I ⚛️"],
            ["💻 Computer Sciences 💻"],
            ["🗣️ Arabic Language 🗣️"],
            ["🧠 Physiology 🧠"],
            ["⬅️ رجوع"]
        ]

def get_available_lecture_numbers(material_key_base: str) -> list:
    numbers = []
    prefix = material_key_base + "_"
    for key in LECTURE_FILE_IDS:
        if key.startswith(prefix):
            try:
                num = int(key.split("_")[-1])
                numbers.append(num)
            except ValueError:
                continue
    return sorted(set(numbers))

def build_lecture_keyboard(numbers: list) -> list:
    keyboard = []
    for i in range(0, len(numbers), 3):
        row = [str(n) for n in numbers[i:i+3]]
        keyboard.append(row)
    keyboard.append(["⬅️ رجوع"])
    keyboard.append(["🔝 القائمة الرئيسية"])
    return keyboard

async def send_files_by_ids(update: Update, context: ContextTypes.DEFAULT_TYPE, file_ids, caption: str = ""):
    """إرسال الملفات باستخدام معرفاتها من تيليجرام، مع وصف."""
    if isinstance(file_ids, str):
        file_ids = [file_ids]
    for fid in file_ids:
        try:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=fid,
                caption=caption if caption else None
            )
        except Exception as e:
            logging.error(f"خطأ في إرسال الملف {fid}: {e}", exc_info=True)
            await update.message.reply_text("⚠️ فشل إرسال أحد الملفات. تأكد من صلاحية المعرف.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'main_menu'
    context.user_data.pop('skip_section_menu', None)
    reply_keyboard = [
        ["🔴 المرحلة الأولى 🔴"],
        ["🔵 المرحلة الثانية 🔵"],
        ["🟠 المرحلة الثالثة 🟠"],
        ["🟣 المرحلة الرابعة 🟣"],
        ["🟢 المرحلة الخامسة 🟢"],
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("🔝 القائمة الرئيسية", reply_markup=reply_markup)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "الأولى" in text:
        context.user_data['current_stage'] = 'first_stage'
        context.user_data['state'] = 'course_menu'
        reply_keyboard = [
            ["🟧 First course 🟧"],
            ["⬛ Second course ⬛"],
            ["⬅️ رجوع إلى المراحل"]
        ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text("قريباً، جاري إضافة باقي المراحل.")
        await start(update, context)

async def handle_course_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "First course" in text:
        context.user_data['current_location'] = 'first_course'
        context.user_data['state'] = 'material_menu'
        reply_keyboard = build_course_keyboard('first_course')
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif "Second course" in text:
        context.user_data['current_location'] = 'second_course'
        context.user_data['state'] = 'material_menu'
        reply_keyboard = build_course_keyboard('second_course')
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif "رجوع" in text:
        await start(update, context)
    else:
        await update.message.reply_text("الرجاء اختيار أحد الكورسات المتاحة.")

async def handle_material_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "رجوع" in text:
        current_stage = context.user_data.get('current_stage', 'first_stage')
        context.user_data['state'] = 'course_menu'
        if current_stage == 'first_stage':
            reply_keyboard = [
                ["🟧 First course 🟧"],
                ["⬛ Second course ⬛"],
                ["⬅️ رجوع إلى المراحل"]
            ]
        else:
            reply_keyboard = [
                ["🟧 First course 🟧"],
                ["⬅️ رجوع إلى المراحل"]
            ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        return

    context.user_data['current_material'] = text
    course_location = context.user_data.get('current_location', 'first_course')
    course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
    clean_name = clean_material_name(text)

    if text in MATERIALS_NO_PRACTICAL:
        context.user_data['last_section'] = "📖 نظري"
        context.user_data['skip_section_menu'] = True
        material_base = f"{course_prefix}_{clean_name}_نظري"
        numbers = get_available_lecture_numbers(material_base)
        if numbers:
            context.user_data['state'] = 'lecture_number_menu'
            reply_keyboard = build_lecture_keyboard(numbers)
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("📖 نظري", reply_markup=reply_markup)
        else:
            await update.message.reply_text("لا توجد محاضرات متاحة لهذه المادة حالياً.")
        return

    context.user_data['skip_section_menu'] = False
    context.user_data['state'] = 'section_menu'
    reply_keyboard = [
        ["📖 نظري"],
        ["🔬 عملي"],
        ["🔗 مصادر"],
        ["⬅️ رجوع"]
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_section_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📖 نظري" or text == "🔬 عملي":
        context.user_data['last_section'] = text
        material_name_raw = context.user_data.get('current_material', '')
        course_location = context.user_data.get('current_location', 'first_course')
        course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
        clean_name = clean_material_name(material_name_raw)
        section = "نظري" if "نظري" in text else "عملي"
        material_base = f"{course_prefix}_{clean_name}_{section}"
        numbers = get_available_lecture_numbers(material_base)
        if numbers:
            context.user_data['state'] = 'lecture_number_menu'
            reply_keyboard = build_lecture_keyboard(numbers)
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"لا توجد محاضرات في قسم {section} حالياً.")
        return

    elif text == "🔗 مصادر":
        material_name_raw = context.user_data.get('current_material', '')
        course_location = context.user_data.get('current_location', 'first_course')
        course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
        clean_name = clean_material_name(material_name_raw)
        key = f"{course_prefix}_{clean_name}_مصادر"
        file_ids = LECTURE_FILE_IDS.get(key)
        if file_ids:
            caption = f"📚 {material_name_raw} - مصادر"
            await send_files_by_ids(update, context, file_ids, caption)
        else:
            await update.message.reply_text("📭 لا توجد مصادر مرفقة لهذه المادة.")
        return

    elif text == "⬅️ رجوع":
        context.user_data['state'] = 'material_menu'
        course_location = context.user_data.get('current_location', 'first_course')
        reply_keyboard = build_course_keyboard(course_location)
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("الرجاء اختيار نظري أو عملي.")

async def handle_lecture_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ رجوع":
        if context.user_data.get('skip_section_menu'):
            context.user_data['state'] = 'material_menu'
            course_location = context.user_data.get('current_location', 'first_course')
            reply_keyboard = build_course_keyboard(course_location)
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        else:
            context.user_data['state'] = 'section_menu'
            reply_keyboard = [
                ["📖 نظري"],
                ["🔬 عملي"],
                ["🔗 مصادر"],
                ["⬅️ رجوع"]
            ]
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        return
    elif text == "🔝 القائمة الرئيسية":
        await start(update, context)
        return

    if not text.isdigit():
        await update.message.reply_text("الرجاء اختيار رقم محاضرة صحيح.")
        return

    material_name_raw = context.user_data.get('current_material', '')
    course_location = context.user_data.get('current_location', 'first_course')
    current_section_raw = context.user_data.get('last_section', '📖 نظري')
    course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
    clean_name = clean_material_name(material_name_raw)
    section = "عملي" if "عملي" in current_section_raw else "نظري"

    key = f"{course_prefix}_{clean_name}_{section}_{text}"
    file_ids = LECTURE_FILE_IDS.get(key)

    if file_ids:
        caption = f"{material_name_raw} - {current_section_raw} - محاضرة {text}"
        await send_files_by_ids(update, context, file_ids, caption)
    else:
        await update.message.reply_text("❌ المحاضرة غير متوفرة حالياً. تأكد من الرقم.")

async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', 'main_menu')
    if state == 'main_menu':
        await handle_main_menu(update, context)
    elif state == 'course_menu':
        await handle_course_menu(update, context)
    elif state == 'material_menu':
        await handle_material_menu(update, context)
    elif state == 'section_menu':
        await handle_section_menu(update, context)
    elif state == 'lecture_number_menu':
        await handle_lecture_number(update, context)
    else:
        await start(update, context)

def main():
    # الحصول على التوكن من متغير البيئة فقط (بدون قيمة افتراضية مكشوفة)
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        logging.critical("BOT_TOKEN غير مضبوط في متغيرات البيئة!")
        raise RuntimeError("BOT_TOKEN environment variable is required.")

    # بدء الخادم الوهمي في خيط منفصل
    threading.Thread(target=start_fake_server, daemon=True).start()

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(120)
        .read_timeout(120)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()