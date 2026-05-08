import logging
import os
import re
import json
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

# ========== تحميل معرفات الملفات ==========
try:
    with open("lecture_file_ids.json", "r", encoding="utf-8") as f:
        LECTURE_FILE_IDS = json.load(f)
    logging.info("تم تحميل lecture_file_ids.json بنجاح.")
except FileNotFoundError:
    logging.error("ملف lecture_file_ids.json غير موجود!")
    LECTURE_FILE_IDS = {}
except json.JSONDecodeError:
    logging.error("خطأ في صيغة lecture_file_ids.json")
    LECTURE_FILE_IDS = {}

# ========== إدارة المستخدمين ==========
USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

async def register_user_if_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "user_id": user.id,
            "first_name": user.first_name or "",
            "username": user.username or "",
            "chat_id": update.effective_chat.id,
        }
        save_users(users)
        logging.info(f"مستخدم جديد: {user.id} - @{user.username or ''}")

# ========== خادم وهمي لـ Render ==========
class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def start_fake_server():
    port = int(os.environ.get('PORT', 5000))
    server = HTTPServer(('0.0.0.0', port), FakeHandler)
    logging.info(f'Fake server on port {port}')
    server.serve_forever()

# ========== تعيينات الأسماء والعرض ==========
# عرض المراحل (يُضاف إليها عند الحاجة)
STAGE_DISPLAY = {
    "first_stage": "🔴 المرحلة الأولى 🔴",
    "second_stage": "🔵 المرحلة الثانية 🔵",
    "third_stage": "🟠 المرحلة الثالثة 🟠",
    "fourth_stage": "🟣 المرحلة الرابعة 🟣",
    "fifth_stage": "🟢 المرحلة الخامسة 🟢",
}

# عرض الكورسات بالإيموجي المرغوب (تعديل 1)
COURSE_DISPLAY = {
    "first_course": "🟧 First course 🟧",
    "second_course": "⬛ Second course ⬛",
    # أضف بقية الكورسات بنفس النمط إن وجدت
    "third_course": "🟫 Third course 🟫",
    "fourth_course": "🟪 Fourth course 🟪",
    "fifth_course": "🟩 Fifth course 🟩",
}

def course_display(course_key: str) -> str:
    return COURSE_DISPLAY.get(course_key, f"📘 {course_key.replace('_', ' ').title()} 📘")

# عرض المواد (الربط بين الاسم النظيف والاسم المُزيّن بالإيموجي)
MATERIAL_DISPLAY = {
    "Analytical Chemistry": "🧪 Analytical Chemistry 🧪",
    "Medical Physics": "📊 Medical Physics 📊",
    "حقوق الإنسان": "⚖️ حقوق الإنسان ⚖️",
    "Biostatistics": "📈 Biostatistics 📈",
    "Terminology": "📝 Terminology 📝",
    "Histology": "🔬 Histology 🔬",
    "Anatomy": "🦴 Anatomy 🦴",
    "Pharmaceutical Calculations": "🧮 Pharmaceutical Calculations 🧮",
    "Organic Chemistry I": "⚛️ Organic Chemistry I ⚛️",
    "Computer Sciences": "💻 Computer Sciences 💻",
    "Arabic Language": "🗣️ Arabic Language 🗣️",
    "Physiology": "🧠 Physiology 🧠",
}

# ========== دوال تحليل ملف المحاضرات ==========
KEY_PATTERN = re.compile(
    r'^(?P<stage>[a-z]+_stage)_'
    r'(?P<course>[a-z]+_course)_'
    r'(?P<material>.+?)_'
    r'(?P<section>نظري|عملي|مصادر)'
    r'(?:_(?P<number>\d+))?$'
)

def parse_key(key: str):
    """استخراج أجزاء المفتاح: المرحلة، الكورس، المادة، القسم، الرقم."""
    m = KEY_PATTERN.match(key)
    if not m:
        return None
    return m.groupdict()

def get_all_stages() -> list:
    stages = set()
    for key in LECTURE_FILE_IDS:
        p = parse_key(key)
        if p:
            stages.add(p["stage"])
    return sorted(stages)

def get_courses_in_stage(stage: str) -> list:
    prefix = stage + "_"
    courses = set()
    for key in LECTURE_FILE_IDS:
        if key.startswith(prefix):
            p = parse_key(key)
            if p and p["stage"] == stage:
                courses.add(p["course"])
    return sorted(courses)

def get_materials_in_course(stage: str, course: str) -> list:
    prefix = f"{stage}_{course}_"
    materials = set()
    for key in LECTURE_FILE_IDS:
        if key.startswith(prefix):
            p = parse_key(key)
            if p and p["stage"] == stage and p["course"] == course:
                materials.add(p["material"])
    # تعديل 3: ترتيب المواد تنازلياً حسب عدد الحروف (الأكبر فالأصغر)
    return sorted(materials, key=lambda m: len(m), reverse=True)

def material_has_practical(stage: str, course: str, material: str) -> bool:
    """هل توجد مفاتيح قسم عملي لهذه المادة؟"""
    prefix = f"{stage}_{course}_{material}_عملي"
    for key in LECTURE_FILE_IDS:
        if key.startswith(prefix):
            return True
    return False

def get_available_lecture_numbers(stage_course_material_section_prefix: str) -> list:
    """أرقام المحاضرات المتاحة لقسم معين."""
    numbers = []
    for key in LECTURE_FILE_IDS:
        if key.startswith(stage_course_material_section_prefix):
            p = parse_key(key)
            if p and p["number"]:
                numbers.append(int(p["number"]))
    return sorted(set(numbers))

# ========== دوال مساعدة ==========
def clean_material_name(raw: str) -> str:
    """إزالة الرموز والإيموجي من اسم المادة للحصول على الاسم النظيف."""
    return re.sub(r'[^a-zA-Z0-9\s\u0621-\u064A]', '', raw).strip()

def display_to_clean(display_name: str) -> str:
    """تحويل اسم المادة المعروض إلى الاسم النظيف باستخدام التنظيف."""
    # أسلوب بسيط وفعّال لأن الإيموجي والرموز تُحذف
    return clean_material_name(display_name)

def build_lecture_keyboard(numbers: list) -> list:
    keyboard = []
    for i in range(0, len(numbers), 3):
        row = [str(n) for n in numbers[i:i+3]]
        keyboard.append(row)
    keyboard.append(["⬅️ رجوع"])
    keyboard.append(["🔝 القائمة الرئيسية"])
    return keyboard

async def send_files_by_ids(update, context, file_ids, caption=""):
    if isinstance(file_ids, str):
        file_ids = [file_ids]
    for fid in file_ids:
        try:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=fid,
                caption=caption if caption else None,
            )
        except Exception as e:
            logging.error(f"خطأ في إرسال {fid}: {e}")
            await update.message.reply_text("⚠️ فشل إرسال أحد الملفات.")

# ========== أوامر البوت ==========
ADMIN_ID = 1686696869  # <-- غيّره إلى معرفك

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    context.user_data.clear()
    context.user_data["state"] = "main_menu"
    # تعديل 2: عرض جميع المراحل الخمسة دائماً
    stages = ["first_stage", "second_stage", "third_stage", "fourth_stage", "fifth_stage"]
    keyboard = []
    for s in stages:
        display = STAGE_DISPLAY.get(s, s)
        keyboard.append([display])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("🔝 القائمة الرئيسية", reply_markup=reply_markup)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 للمشرف فقط.")
        return
    users = load_users()
    count = len(users)
    if count == 0:
        await update.message.reply_text("لا يوجد مستخدمون بعد.")
        return
    msg = f"👥 عدد المستخدمين المسجلين: {count}\n\n"
    # msg += "\n".join([f"• {d['first_name']} (ID:{uid})" for uid,d in users.items()])
    await update.message.reply_text(msg)

# ========== معالجات القوائم ==========
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    text = update.message.text
    # ابحث عن المرحلة المختارة من خلال نص الزر
    chosen_stage = None
    for stage_key, display in STAGE_DISPLAY.items():
        if text == display:
            chosen_stage = stage_key
            break
    if not chosen_stage:
        await update.message.reply_text("الرجاء اختيار مرحلة موجودة.")
        await start(update, context)
        return

    context.user_data["current_stage"] = chosen_stage
    courses = get_courses_in_stage(chosen_stage)
    if not courses:
        await update.message.reply_text("لا توجد كورسات مضافة لهذه المرحلة بعد.")
        await start(update, context)
        return
    keyboard = []
    for c in courses:
        keyboard.append([course_display(c)])
    keyboard.append(["⬅️ رجوع إلى المراحل"])
    context.user_data["state"] = "course_menu"
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_course_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    text = update.message.text
    if "رجوع" in text:
        await start(update, context)
        return
    current_stage = context.user_data.get("current_stage")
    if not current_stage:
        await start(update, context)
        return
    courses = get_courses_in_stage(current_stage)
    chosen_course = None
    for c in courses:
        if course_display(c) == text:
            chosen_course = c
            break
    if not chosen_course:
        await update.message.reply_text("الرجاء اختيار كورس موجود.")
        # إعادة عرض الكورسات
        keyboard = [[course_display(c)] for c in courses] + [["⬅️ رجوع إلى المراحل"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("اختر كورس:", reply_markup=reply_markup)
        return

    context.user_data["current_course"] = chosen_course
    materials = get_materials_in_course(current_stage, chosen_course)
    if not materials:
        await update.message.reply_text("لا توجد مواد مضافة لهذا الكورس.")
        # رجوع
        return

    keyboard = []
    for mat in materials:
        display = MATERIAL_DISPLAY.get(mat, mat)
        keyboard.append([display])
    keyboard.append(["⬅️ رجوع"])
    context.user_data["state"] = "material_menu"
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_material_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    text = update.message.text
    if "رجوع" in text:
        # العودة إلى قائمة الكورسات
        current_stage = context.user_data.get("current_stage")
        if current_stage:
            courses = get_courses_in_stage(current_stage)
            keyboard = [[course_display(c)] for c in courses] + [["⬅️ رجوع إلى المراحل"]]
            context.user_data["state"] = "course_menu"
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
            return
        else:
            await start(update, context)
            return

    current_stage = context.user_data.get("current_stage")
    current_course = context.user_data.get("current_course")
    if not current_stage or not current_course:
        await start(update, context)
        return

    # تحديد الاسم النظيف للمادة
    clean_mat = display_to_clean(text)
    # التحقق من وجود المادة فعلاً
    materials = get_materials_in_course(current_stage, current_course)
    if clean_mat not in materials:
        await update.message.reply_text("المادة غير موجودة.")
        return

    context.user_data["current_material_clean"] = clean_mat
    context.user_data["current_material_display"] = text

    # هل يوجد عملي؟
    has_prac = material_has_practical(current_stage, current_course, clean_mat)

    if not has_prac:
        # الانتقال مباشرة إلى النظري
        context.user_data["last_section"] = "📖 نظري"
        context.user_data["skip_section_menu"] = True
        prefix = f"{current_stage}_{current_course}_{clean_mat}_نظري"
        numbers = get_available_lecture_numbers(prefix + "_")
        if numbers:
            context.user_data["state"] = "lecture_number_menu"
            keyboard = build_lecture_keyboard(numbers)
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("📖 نظري", reply_markup=reply_markup)
        else:
            await update.message.reply_text("لا توجد محاضرات متاحة حالياً.")
        return

    # عرض قائمة الأقسام
    context.user_data["skip_section_menu"] = False
    keyboard = [
        ["📖 نظري"],
        ["🔬 عملي"],
        ["🔗 مصادر"],
        ["⬅️ رجوع"],
    ]
    context.user_data["state"] = "section_menu"
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_section_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    text = update.message.text
    current_stage = context.user_data.get("current_stage")
    current_course = context.user_data.get("current_course")
    clean_mat = context.user_data.get("current_material_clean")
    if not all([current_stage, current_course, clean_mat]):
        await start(update, context)
        return

    if text == "⬅️ رجوع":
        # الرجوع إلى قائمة المواد
        materials = get_materials_in_course(current_stage, current_course)
        keyboard = []
        for mat in materials:
            display = MATERIAL_DISPLAY.get(mat, mat)
            keyboard.append([display])
        keyboard.append(["⬅️ رجوع"])
        context.user_data["state"] = "material_menu"
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        return

    if text in ["📖 نظري", "🔬 عملي"]:
        section = "نظري" if "نظري" in text else "عملي"
        context.user_data["last_section"] = text
        prefix = f"{current_stage}_{current_course}_{clean_mat}_{section}"
        numbers = get_available_lecture_numbers(prefix + "_")
        if numbers:
            context.user_data["state"] = "lecture_number_menu"
            keyboard = build_lecture_keyboard(numbers)
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"لا توجد محاضرات في قسم {section} حالياً.")
        return

    elif text == "🔗 مصادر":
        key = f"{current_stage}_{current_course}_{clean_mat}_مصادر"
        file_ids = LECTURE_FILE_IDS.get(key)
        if file_ids:
            display_mat = context.user_data.get("current_material_display", clean_mat)
            await send_files_by_ids(update, context, file_ids, f"📚 {display_mat} - مصادر")
        else:
            await update.message.reply_text("📭 لا توجد مصادر مرفقة.")
        return

    else:
        await update.message.reply_text("الرجاء اختيار قسم صحيح.")

async def handle_lecture_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    text = update.message.text
    if text == "⬅️ رجوع":
        if context.user_data.get("skip_section_menu"):
            # العودة إلى قائمة المواد
            current_stage = context.user_data.get("current_stage")
            current_course = context.user_data.get("current_course")
            materials = get_materials_in_course(current_stage, current_course)
            keyboard = []
            for mat in materials:
                display = MATERIAL_DISPLAY.get(mat, mat)
                keyboard.append([display])
            keyboard.append(["⬅️ رجوع"])
            context.user_data["state"] = "material_menu"
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        else:
            context.user_data["state"] = "section_menu"
            keyboard = [
                ["📖 نظري"],
                ["🔬 عملي"],
                ["🔗 مصادر"],
                ["⬅️ رجوع"],
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        return

    if text == "🔝 القائمة الرئيسية":
        await start(update, context)
        return

    if not text.isdigit():
        await update.message.reply_text("الرجاء اختيار رقم محاضرة صحيح.")
        return

    current_stage = context.user_data.get("current_stage")
    current_course = context.user_data.get("current_course")
    clean_mat = context.user_data.get("current_material_clean")
    last_section = context.user_data.get("last_section", "📖 نظري")
    section = "عملي" if "عملي" in last_section else "نظري"
    if not all([current_stage, current_course, clean_mat]):
        await start(update, context)
        return

    key = f"{current_stage}_{current_course}_{clean_mat}_{section}_{text}"
    file_ids = LECTURE_FILE_IDS.get(key)
    display_mat = context.user_data.get("current_material_display", clean_mat)

    if file_ids:
        await send_files_by_ids(update, context, file_ids,
                                f"{display_mat} - {last_section} - محاضرة {text}")
    else:
        await update.message.reply_text("❌ المحاضرة غير متوفرة حالياً. تأكد من الرقم.")

async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await register_user_if_new(update, context)
    state = context.user_data.get("state", "main_menu")
    if state == "main_menu":
        await handle_main_menu(update, context)
    elif state == "course_menu":
        await handle_course_menu(update, context)
    elif state == "material_menu":
        await handle_material_menu(update, context)
    elif state == "section_menu":
        await handle_section_menu(update, context)
    elif state == "lecture_number_menu":
        await handle_lecture_number(update, context)
    else:
        await start(update, context)

def main():
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        logging.critical("BOT_TOKEN غير مضبوط!")
        raise RuntimeError("BOT_TOKEN environment variable required.")
    threading.Thread(target=start_fake_server, daemon=True).start()
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(120)
        .read_timeout(120)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("✅ البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()