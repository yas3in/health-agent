"""
ربات تلگرامی Health Agent
-------------------------
این ربات برای مدیریت اطلاعات سلامت کاربران طراحی شده است. کاربران می‌توانند ثبت‌نام کنند، اطلاعات خود را ویرایش کنند،
گزارش‌های روزانه سلامت ارسال کنند و ادمین‌ها قادرند کاربران و گزارش‌ها را مدیریت کنند.

وابستگی‌ها:
- telegram.ext: برای ارتباط با API تلگرام
- psycopg2: برای ارتباط با دیتابیس PostgreSQL
- langchain_openai: برای پردازش متن با مدل زبان
- pandas: برای تولید فایل‌های اکسل
- dotenv: برای بارگذاری متغیرهای محیطی

نحوه اجرا:
1. متغیرهای محیطی (TELEGRAM_API_KEY، AVALAI_API_KEY و ...) را در فایل .env تنظیم کنید.
2. دیتابیس PostgreSQL را با جداول user_profiles و daily_reports آماده کنید.
3. اسکریپت را با دستور `python script.py` اجرا کنید.
"""

###########################################ث
# بخش ۱: تعاریف اولیه، متغیرها و تنظیمات
###########################################

from langchain_openai import ChatOpenAI
import logging
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from dotenv import load_dotenv
import os
import json
import pandas as pd
import requests
import tempfile
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from logging.handlers import RotatingFileHandler

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

# متغیرهای سراسری برای تنظیمات ربات
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")  # کلید API تلگرام از متغیرهای محیطی
AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")      # کلید API مدل زبان AvalAI
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD") # رمز عبور دیتابیس PostgreSQL
ADMIN_TELEGRAM_IDS = os.getenv("ADMIN_TELEGRAM_IDS")  # لیست آیدی‌های عددی ادمین‌ها
BASE_URL = "https://api.avalai.ir/v1"              # آدرس پایه API مدل زبان
DATABASE_URL = f"postgresql://health_agent_user:{DATABASE_PASSWORD}@localhost/health_agent_db"  # URL اتصال به دیتابیس

# بررسی مقادیر متغیرهای محیطی
if not TELEGRAM_API_KEY or ":" not in TELEGRAM_API_KEY:
    raise ValueError("❌ TELEGRAM_API_KEY نامعتبر است! لطفاً فایل .env را بررسی کنید.")
if not AVALAI_API_KEY:
    raise ValueError("❌ AVALAI_API_KEY نامعتبر است! لطفاً فایل .env را بررسی کنید.")
if not DATABASE_PASSWORD:
    raise ValueError("❌ DATABASE_PASSWORD نامعتبر است! لطفاً فایل .env را بررسی کنید.")
if not ADMIN_TELEGRAM_IDS:
    raise ValueError("❌ ADMIN_TELEGRAM_IDS نامعتبر است! لطفاً فایل .env را بررسی کنید.")

# تبدیل ADMIN_TELEGRAM_IDS به لیست اعداد
ADMIN_IDS = [int(id.strip()) for id in ADMIN_TELEGRAM_IDS.split(",")]

# تنظیمات لاگ‌گیری با RotatingFileHandler
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR,  # تغییر از DEBUG به ERROR
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("health_agent.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# استخر اتصال به دیتابیس برای مدیریت درخواست‌ها
db_pool = SimpleConnectionPool(1, 20, dsn=DATABASE_URL)

# ثابت‌های وضعیت برای ConversationHandler
NAME, LAST_NAME, PHONE, GENDER, AGE, NATIONAL_ID = range(6)  # مراحل ثبت‌نام کاربر
GET_NATIONAL_ID, GET_DAYS = range(2)  # گزارش‌گیری ادمین
EDIT_MENU, EDIT_NAME, EDIT_LAST_NAME, EDIT_PHONE, EDIT_GENDER, EDIT_AGE, EDIT_NATIONAL_ID = range(7)  # ویرایش اطلاعات کاربر
GET_USER_NATIONAL_ID = 0  # استخراج اطلاعات کاربر توسط ادمین
SUPPORT_MESSAGE, ADMIN_REPLY, USER_REPLY = range(3)  # پشتیبانی
DELETE_USER_NATIONAL_ID = 0  # حذف کاربر
EDIT_USER_NATIONAL_ID, EDIT_USER_FIELD, EDIT_USER_VALUE = range(3)  # ویرایش کاربر توسط ادمین
DELETE_REPORT_ID = 0  # حذف گزارش
LOCK_USER_NATIONAL_ID = 0  # قفل کاربر
UNLOCK_USER_NATIONAL_ID = 0  # آزادسازی کاربر

def validate_national_id(nid: str) -> bool:
    """اعتبارسنجی کد ملی ۱۰ رقمی ایرانی.

    این تابع بررسی می‌کند که آیا کد ملی واردشده طبق الگوریتم استاندارد ایران معتبر است یا خیر.

    Args:
        nid (str): کد ملی واردشده توسط کاربر (باید ۱۰ رقم باشد).

    Returns:
        bool: True اگر کد ملی معتبر باشد، False در غیر این صورت.

    Examples:
        >>> validate_national_id("1234567890")
        False
        >>> validate_national_id("0073005708")  # یک کد ملی معتبر
        True
    """
    if not (nid.isdigit() and len(nid) == 10):
        return False
    check = int(nid[9])
    total = sum(int(nid[i]) * (10 - i) for i in range(9))
    remainder = total % 11
    return (remainder < 2 and check == remainder) or (remainder >= 2 and check == 11 - remainder)

def set_bot_commands() -> None:
    """تنظیم دستورات ربات در منوی تلگرام.

    این تابع دستورات عمومی برای همه کاربران و دستورات خاص برای ادمین‌ها را از طریق API تلگرام تنظیم می‌کند.

    Notes:
        - دستورات عمومی برای همه کاربران قابل مشاهده است.
        - دستورات ادمین فقط برای آیدی‌های موجود در ADMIN_IDS تنظیم می‌شود.
    """
    # دستورات برای همه کاربران
    general_commands = [
        {"command": "start", "description": "شروع ثبت‌نام یا ورود"},
        {"command": "edit_my_info", "description": "ویرایش اطلاعات پروفایل"},
        {"command": "help", "description": "آموزش و راهنمایی"},
        {"command": "support", "description": "ارتباط با پشتیبانی"}
    ]
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/setMyCommands",
        json={"commands": general_commands, "scope": {"type": "default"}}
    )
    logger.info("✅ دستورات عمومی برای همه کاربران تنظیم شد.")

    # دستورات برای ادمین‌ها
    admin_commands = [
        {"command": "get_report", "description": "دریافت گزارش روزانه کاربر"},
        {"command": "get_user_info", "description": "استخراج اطلاعات پروفایل کاربر"},
        {"command": "list_users", "description": "مشاهده لیست همه کاربران"},
        {"command": "delete_user", "description": "حذف یک کاربر"},
        {"command": "edit_user", "description": "ویرایش اطلاعات یک کاربر"},
        {"command": "stats", "description": "مشاهده آمار کل سیستم"},
        {"command": "delete_report", "description": "حذف یک گزارش خاص"},
        {"command": "all_reports", "description": "مشاهده همه گزارش‌های یک کاربر"},
        {"command": "lock_user", "description": "قفل کردن دسترسی یک کاربر"},
        {"command": "unlock_user", "description": "آزادسازی دسترسی یک کاربر"},
        {"command": "get_logs", "description": "مشاهده لاگ‌های ربات"}
    ]
    for admin_id in ADMIN_IDS:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/setMyCommands",
            json={"commands": admin_commands, "scope": {"type": "chat", "chat_id": admin_id}}
        )
        logger.info(f"✅ دستورات ادمین برای {admin_id} تنظیم شد.")
        
        
##############################################
# بخش ۲: توابع ثبت‌نام و ویرایش اطلاعات کاربر
##############################################

def start(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند ثبت‌نام یا خوش‌آمدگویی به کاربر ثبت‌شده.

    اگر کاربر قبلاً ثبت‌نام کرده باشد، خوش‌آمد می‌گوید و اطلاعات فعلی او را نمایش می‌دهد.
    در غیر این صورت، فرآیند ثبت‌نام را با درخواست نام شروع می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو و داده‌های موقت کاربر.

    Returns:
        int: وضعیت بعدی در ConversationHandler (NAME یا END).

    Raises:
        psycopg2.Error: اگر خطایی در ارتباط با دیتابیس رخ دهد.
        Exception: برای خطاهای عمومی غیرمنتظره.
    """
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT name, last_name FROM user_profiles WHERE telegram_id = %s", (user_id,))
            result = cur.fetchone()
            if result:
                name, last_name = result
                update.message.reply_text(
                    f"سلام {name} {last_name}! خوش آمدید.\n"
                    "شما قبلاً ثبت‌نام کرده‌اید. می‌توانید گزارش روزانه خود را ارسال کنید یا با /edit_my_info اطلاعات خود را ویرایش کنید."
                )
                return ConversationHandler.END
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در بررسی پروفایل کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در بررسی پروفایل. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"❌ خطای عمومی در بررسی پروفایل کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در بررسی پروفایل رخ داد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    finally:
        if conn:
            db_pool.putconn(conn)

    update.message.reply_text("سلام! به ربات ما خوش آمدید. لطفاً برای ثبت‌نام اطلاعات خود را وارد کنید.")
    update.message.reply_text("لطفاً نام خود را وارد کنید:")
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    """دریافت نام کاربر در فرآیند ثبت‌نام.

    نام واردشده را بررسی می‌کند و در صورت معتبر بودن، به مرحله بعدی (نام خانوادگی) می‌رود.

    Args:
        update (telegram.Update): شیء آپدیت حاوی نام واردشده.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره موقت نام.

    Returns:
        int: وضعیت بعدی (LAST_NAME یا NAME اگر نام نامعتبر باشد).
    """
    name = update.message.text.strip()
    if not name or len(name) < 2:
        update.message.reply_text("❌ نام نامعتبر است. لطفاً نام خود را به‌درستی وارد کنید.")
        return NAME
    context.user_data['name'] = name
    update.message.reply_text("لطفاً نام خانوادگی خود را وارد کنید:")
    return LAST_NAME

def get_last_name(update: Update, context: CallbackContext) -> int:
    """دریافت نام خانوادگی کاربر در فرآیند ثبت‌نام.

    نام خانوادگی را بررسی می‌کند و در صورت معتبر بودن، به مرحله بعدی (شماره موبایل) می‌رود.

    Args:
        update (telegram.Update): شیء آپدیت حاوی نام خانوادگی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره موقت نام خانوادگی.

    Returns:
        int: وضعیت بعدی (PHONE یا LAST_NAME اگر نام خانوادگی نامعتبر باشد).
    """
    last_name = update.message.text.strip()
    if not last_name or len(last_name) < 2:
        update.message.reply_text("❌ نام خانوادگی نامعتبر است. لطفاً نام خانوادگی خود را به‌درستی وارد کنید.")
        return LAST_NAME
    context.user_data['last_name'] = last_name
    update.message.reply_text("لطفاً شماره موبایل خود را وارد کنید:")
    return PHONE

def get_phone(update: Update, context: CallbackContext) -> int:
    """دریافت شماره موبایل کاربر در فرآیند ثبت‌نام.

    شماره موبایل را اعتبارسنجی می‌کند و در صورت معتبر بودن، به انتخاب جنسیت می‌رود.

    Args:
        update (telegram.Update): شیء آپدیت حاوی شماره موبایل.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره موقت شماره.

    Returns:
        int: وضعیت بعدی (GENDER یا PHONE اگر شماره نامعتبر باشد).
    """
    phone_number = update.message.text.strip()
    if not phone_number.isdigit() or len(phone_number) != 11:
        update.message.reply_text("❌ شماره موبایل نامعتبر است. لطفاً یک شماره موبایل ۱۱ رقمی وارد کنید.")
        return PHONE
    context.user_data['phone'] = phone_number
    keyboard = [
        [InlineKeyboardButton("👨 مرد", callback_data="مرد"), InlineKeyboardButton("👩 زن", callback_data="زن")],
        [InlineKeyboardButton("❌ لغو", callback_data="لغو")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("لطفاً جنسیت خود را انتخاب کنید:", reply_markup=reply_markup)
    return GENDER

def get_gender(update: Update, context: CallbackContext) -> int:
    """دریافت جنسیت کاربر در فرآیند ثبت‌نام.

    جنسیت انتخاب‌شده از دکمه‌ها را ذخیره می‌کند و به مرحله بعدی (سن) می‌رود.

    Args:
        update (telegram.Update): شیء آپدیت حاوی اطلاعات انتخاب کاربر.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره جنسیت.

    Returns:
        int: وضعیت بعدی (AGE یا END اگر کاربر لغو کند).
    """
    query = update.callback_query
    query.answer()
    if query.data == "لغو":
        query.edit_message_text("❌ فرآیند لغو شد.")
        return ConversationHandler.END
    gender = query.data
    context.user_data['gender'] = gender
    query.edit_message_text(text=f"✅ جنسیت شما: {gender}\nلطفاً سن خود را وارد کنید:")
    return AGE

def get_age(update: Update, context: CallbackContext) -> int:
    """دریافت سن کاربر در فرآیند ثبت‌نام.

    سن را اعتبارسنجی می‌کند و در صورت معتبر بودن، به مرحله کد ملی می‌رود.

    Args:
        update (telegram.Update): شیء آپدیت حاوی سن.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره سن.

    Returns:
        int: وضعیت بعدی (NATIONAL_ID یا AGE اگر سن نامعتبر باشد).
    """
    age = update.message.text.strip()
    if not age.isdigit() or int(age) < 1 or int(age) > 120:
        update.message.reply_text("❌ سن نامعتبر است. لطفاً یک عدد بین ۱ تا ۱۲۰ وارد کنید.")
        return AGE
    context.user_data['age'] = age
    update.message.reply_text("لطفاً کد ملی خود را وارد کنید:")
    return NATIONAL_ID

def get_national_id(update: Update, context: CallbackContext) -> int:
    """دریافت و ذخیره کد ملی کاربر در فرآیند ثبت‌نام.

    کد ملی را اعتبارسنجی کرده و اطلاعات کاربر را در دیتابیس ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های کاربر.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در ذخیره‌سازی دیتابیس رخ دهد.
    """
    national_id = update.message.text.strip()
    if not validate_national_id(national_id):
        update.message.reply_text("❌ کد ملی نامعتبر است. لطفاً یک کد ملی ۱۰ رقمی معتبر وارد کنید.")
        return NATIONAL_ID
    context.user_data['national_id'] = national_id

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_profiles (telegram_id, name, last_name, phone, gender, age, national_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE
                SET name = EXCLUDED.name, last_name = EXCLUDED.last_name, phone = EXCLUDED.phone, 
                    gender = EXCLUDED.gender, age = EXCLUDED.age, national_id = EXCLUDED.national_id;
            """, (
                update.message.from_user.id,
                context.user_data.get('name', ""),
                context.user_data.get('last_name', ""),
                context.user_data.get('phone', ""),
                context.user_data.get('gender', ""),
                context.user_data.get('age', ""),
                national_id
            ))
            conn.commit()
        update.message.reply_text("✅ پروفایل شما با موفقیت ایجاد شد! از این پس می‌توانید شرح حال روزانه خود را ارسال کنید یا با /edit_my_info اطلاعات خود را ویرایش کنید.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ذخیره پروفایل کاربر {update.message.from_user.id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در ثبت پروفایل. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ذخیره پروفایل کاربر {update.message.from_user.id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در ثبت پروفایل رخ داد. لطفاً دوباره تلاش کنید.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END

def edit_my_info(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند ویرایش اطلاعات پروفایل کاربر.

    اطلاعات فعلی کاربر را از دیتابیس می‌خواند و منویی برای انتخاب بخش موردنظر نمایش می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره پروفایل فعلی.

    Returns:
        int: وضعیت بعدی (EDIT_MENU یا END اگر کاربر ثبت‌نام نکرده باشد).

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT name, last_name, phone, gender, age, national_id FROM user_profiles WHERE telegram_id = %s", (user_id,))
            result = cur.fetchone()
            if not result:
                update.message.reply_text("⚠️ شما هنوز پروفایل ندارید. لطفاً ابتدا با /start ثبت‌نام کنید.")
                return ConversationHandler.END
            context.user_data['current_profile'] = dict(zip(['name', 'last_name', 'phone', 'gender', 'age', 'national_id'], result))
        
        keyboard = [
            [InlineKeyboardButton("نام", callback_data="edit_name"), InlineKeyboardButton("نام خانوادگی", callback_data="edit_last_name")],
            [InlineKeyboardButton("شماره موبایل", callback_data="edit_phone"), InlineKeyboardButton("جنسیت", callback_data="edit_gender")],
            [InlineKeyboardButton("سن", callback_data="edit_age"), InlineKeyboardButton("کد ملی", callback_data="edit_national_id")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("کدام بخش از اطلاعات خود را می‌خواهید ویرایش کنید؟", reply_markup=reply_markup)
        return EDIT_MENU
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در بررسی پروفایل کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در بررسی پروفایل. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"❌ خطای عمومی در بررسی پروفایل کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در بررسی پروفایل رخ داد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END
    finally:
        if conn:
            db_pool.putconn(conn)

def edit_menu(update: Update, context: CallbackContext) -> int:
    """مدیریت منوی انتخاب بخش برای ویرایش اطلاعات کاربر.

    بر اساس انتخاب کاربر، به مرحله ویرایش فیلد موردنظر هدایت می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی انتخاب کاربر از منو.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی پروفایل فعلی.

    Returns:
        int: وضعیت بعدی (وضعیت فیلد انتخاب‌شده یا END در صورت لغو).
    """
    query = update.callback_query
    query.answer()
    if query.data == "cancel":
        query.edit_message_text("❌ فرآیند ویرایش لغو شد.")
        return ConversationHandler.END
    
    field_map = {
        "edit_name": (EDIT_NAME, f"نام فعلی: {context.user_data['current_profile']['name']}\nلطفاً نام جدید را وارد کنید یا 'بدون تغییر' بنویسید:"),
        "edit_last_name": (EDIT_LAST_NAME, f"نام خانوادگی فعلی: {context.user_data['current_profile']['last_name']}\nلطفاً نام خانوادگی جدید را وارد کنید یا 'بدون تغییر' بنویسید:"),
        "edit_phone": (EDIT_PHONE, f"شماره موبایل فعلی: {context.user_data['current_profile']['phone']}\nلطفاً شماره موبایل جدید را وارد کنید یا 'بدون تغییر' بنویسید:"),
        "edit_gender": (EDIT_GENDER, f"جنسیت فعلی: {context.user_data['current_profile']['gender']}\nلطفاً جنسیت جدید را انتخاب کنید یا 'بدون تغییر' بزنید:"),
        "edit_age": (EDIT_AGE, f"سن فعلی: {context.user_data['current_profile']['age']}\nلطفاً سن جدید را وارد کنید یا 'بدون تغییر' بنویسید:"),
        "edit_national_id": (EDIT_NATIONAL_ID, f"کد ملی فعلی: {context.user_data['current_profile']['national_id']}\nلطفاً کد ملی جدید را وارد کنید یا 'بدون تغییر' بنویسید:")
    }
    
    state, message = field_map[query.data]
    if query.data == "edit_gender":
        keyboard = [
            [InlineKeyboardButton("👨 مرد", callback_data="مرد"), InlineKeyboardButton("👩 زن", callback_data="زن")],
            [InlineKeyboardButton("❌ لغو", callback_data="لغو"), InlineKeyboardButton("بدون تغییر", callback_data="بدون تغییر")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(message, reply_markup=reply_markup)
    else:
        query.edit_message_text(message)
    return state

def edit_name(update: Update, context: CallbackContext) -> int:
    """ویرایش نام کاربر.

    نام جدید را بررسی کرده و در صورت معتبر بودن، تغییرات را ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی نام جدید.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های فعلی.

    Returns:
        int: پایان فرآیند با ذخیره تغییرات (ConversationHandler.END).
    """
    new_name = update.message.text.strip()
    if new_name != "بدون تغییر":
        if not new_name or len(new_name) < 2:
            update.message.reply_text("❌ نام نامعتبر است. لطفاً نام خود را به‌درستی وارد کنید یا 'بدون تغییر' بنویسید.")
            return EDIT_NAME
        context.user_data['name'] = new_name
    return save_profile_changes(update, context)

def edit_last_name(update: Update, context: CallbackContext) -> int:
    """ویرایش نام خانوادگی کاربر.

    نام خانوادگی جدید را بررسی کرده و در صورت معتبر بودن، تغییرات را ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی نام خانوادگی جدید.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های فعلی.

    Returns:
        int: پایان فرآیند با ذخیره تغییرات (ConversationHandler.END).
    """
    new_last_name = update.message.text.strip()
    if new_last_name != "بدون تغییر":
        if not new_last_name or len(new_last_name) < 2:
            update.message.reply_text("❌ نام خانوادگی نامعتبر است. لطفاً نام خانوادگی خود را به‌درستی وارد کنید یا 'بدون تغییر' بنویسید.")
            return EDIT_LAST_NAME
        context.user_data['last_name'] = new_last_name
    return save_profile_changes(update, context)

def edit_phone(update: Update, context: CallbackContext) -> int:
    """ویرایش شماره موبایل کاربر.

    شماره جدید را اعتبارسنجی کرده و در صورت معتبر بودن، تغییرات را ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی شماره موبایل جدید.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های فعلی.

    Returns:
        int: پایان فرآیند با ذخیره تغییرات (ConversationHandler.END).
    """
    new_phone = update.message.text.strip()
    if new_phone != "بدون تغییر":
        if not new_phone.isdigit() or len(new_phone) != 11:
            update.message.reply_text("❌ شماره موبایل نامعتبر است. لطفاً یک شماره موبایل ۱۱ رقمی وارد کنید یا 'بدون تغییر' بنویسید.")
            return EDIT_PHONE
        context.user_data['phone'] = new_phone
    return save_profile_changes(update, context)

def edit_gender(update: Update, context: CallbackContext) -> int:
    """ویرایش جنسیت کاربر.

    جنسیت جدید را از انتخاب کاربر دریافت کرده و تغییرات را ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی انتخاب جنسیت.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های فعلی.

    Returns:
        int: پایان فرآیند با ذخیره تغییرات (ConversationHandler.END).
    """
    query = update.callback_query
    query.answer()
    if query.data == "لغو":
        query.edit_message_text("❌ فرآیند ویرایش لغو شد.")
        return ConversationHandler.END
    if query.data != "بدون تغییر":
        context.user_data['gender'] = query.data
    query.edit_message_text("✅ جنسیت ویرایش شد.")
    return save_profile_changes(update, context)

def edit_age(update: Update, context: CallbackContext) -> int:
    """ویرایش سن کاربر.

    سن جدید را اعتبارسنجی کرده و در صورت معتبر بودن، تغییرات را ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی سن جدید.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های فعلی.

    Returns:
        int: پایان فرآیند با ذخیره تغییرات (ConversationHandler.END).
    """
    new_age = update.message.text.strip()
    if new_age != "بدون تغییر":
        if not new_age.isdigit() or int(new_age) < 1 or int(new_age) > 120:
            update.message.reply_text("❌ سن نامعتبر است. لطفاً یک عدد بین ۱ تا ۱۲۰ وارد کنید یا 'بدون تغییر' بنویسید.")
            return EDIT_AGE
        context.user_data['age'] = new_age
    return save_profile_changes(update, context)

def edit_national_id(update: Update, context: CallbackContext) -> int:
    """ویرایش کد ملی کاربر.

    کد ملی جدید را اعتبارسنجی کرده و در صورت معتبر بودن، تغییرات را ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی جدید.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های فعلی.

    Returns:
        int: پایان فرآیند با ذخیره تغییرات (ConversationHandler.END).
    """
    new_national_id = update.message.text.strip()
    if new_national_id != "بدون تغییر":
        if not validate_national_id(new_national_id):
            update.message.reply_text("❌ کد ملی نامعتبر است. لطفاً یک کد ملی ۱۰ رقمی معتبر وارد کنید یا 'بدون تغییر' بنویسید.")
            return EDIT_NATIONAL_ID
        context.user_data['national_id'] = new_national_id
    return save_profile_changes(update, context)

def save_profile_changes(update: Update, context: CallbackContext) -> int:
    """ذخیره تغییرات پروفایل کاربر در دیتابیس.

    اطلاعات ویرایش‌شده را در جدول user_profiles به‌روزرسانی می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت (پیام یا callback).
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی داده‌های جدید و فعلی.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در به‌روزرسانی دیتابیس رخ دهد.
    """
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE user_profiles 
                SET name = %s, last_name = %s, phone = %s, gender = %s, age = %s, national_id = %s
                WHERE telegram_id = %s
            """, (
                context.user_data.get('name', context.user_data['current_profile']['name']),
                context.user_data.get('last_name', context.user_data['current_profile']['last_name']),
                context.user_data.get('phone', context.user_data['current_profile']['phone']),
                context.user_data.get('gender', context.user_data['current_profile']['gender']),
                context.user_data.get('age', context.user_data['current_profile']['age']),
                context.user_data.get('national_id', context.user_data['current_profile']['national_id']),
                user_id
            ))
            conn.commit()
        update.message.reply_text("✅ اطلاعات پروفایل شما با موفقیت ویرایش شد!") if update.message else update.callback_query.edit_message_text("✅ اطلاعات پروفایل شما با موفقیت ویرایش شد!")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ویرایش پروفایل کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در ویرایش پروفایل. لطفاً دوباره تلاش کنید.") if update.message else update.callback_query.edit_message_text("⚠️ خطای دیتابیس در ویرایش پروفایل.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ویرایش پروفایل کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در ویرایش پروفایل رخ داد. لطفاً دوباره تلاش کنید.") if update.message else update.callback_query.edit_message_text("⚠️ مشکلی در ویرایش پروفایل رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END


##############################################
# بخش ۳: توابع گزارش‌گیری و مدیریت ادمین
##############################################

# تنظیمات مدل زبان برای استخراج اطلاعات
llm = ChatOpenAI(model="gpt-4o-mini", base_url=BASE_URL, api_key=AVALAI_API_KEY)

def extract_info_from_text(user_report: str) -> dict:
    """استخراج اطلاعات سلامت از گزارش روزانه کاربر با استفاده از LLM.

    متن گزارش را به مدل زبان ارسال می‌کند و اطلاعات کلیدی را در قالب JSON برمی‌گرداند.

    Args:
        user_report (str): متن گزارش روزانه ارسال‌شده توسط کاربر.

    Returns:
        dict: دیکشنری حاوی اطلاعات استخراج‌شده شامل health_status، need_for_medicines و غیره.
              اگر خطایی رخ دهد، یک پیام خطا به صورت رشته برگردانده می‌شود.

    Raises:
        json.JSONDecodeError: اگر پاسخ LLM به درستی JSON نباشد.
        ValueError: اگر فرمت پاسخ LLM نادرست باشد.
    """
    messages = [
        {"role": "system", "content": """
            شما یک دستیار مفید هستید که برای استخراج اطلاعات مرتبط با سلامت از گزارش‌های روزانه طراحی شده‌اید.
            اطلاعات را در قالب JSON با کلیدهای زیر برگردانید:
            - health_status
            - need_for_medicines
            - weakness_status
            - water_intake
            - food_preference
            اگر اطلاعاتی در دسترس نباشد، از "بدون پاسخ" استفاده کنید.
            لطفاً فقط JSON خالص برگردانید و از افزودن متن اضافی مثل ```json یا توضیحات خودداری کنید.
        """},
        {"role": "user", "content": user_report},
    ]
    try:
        response = llm.invoke(messages)
        logger.debug(f"پاسخ خام از LLM: {response.content}")
        if not response.content or response.content.strip() == "":
            raise ValueError("پاسخ LLM خالی است")
        
        # تمیز کردن پاسخ: حذف ```json و ```
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[len("```json"):].strip()
        if content.endswith("```"):
            content = content[:-len("```")].strip()
        
        extracted_info = json.loads(content)
        required_keys = ["health_status", "need_for_medicines", "weakness_status", "water_intake", "food_preference"]
        if not isinstance(extracted_info, dict) or not all(k in extracted_info for k in required_keys):
            raise ValueError("فرمت پاسخ LLM نادرست است")
        logger.info(f"📜 اطلاعات استخراج‌شده از LLM برای کاربر: {extracted_info}")
        return extracted_info
    except json.JSONDecodeError as e:
        logger.error(f"❌ خطای JSON در پردازش پاسخ LLM: {str(e)} - پاسخ خام: {response.content}", exc_info=True)
        return "⚠️ خطای پردازش JSON در شرح حال. لطفاً دوباره امتحان کنید."
    except ValueError as e:
        logger.error(f"❌ خطای اعتبارسنجی در پردازش پاسخ LLM: {str(e)} - پاسخ خام: {response.content}", exc_info=True)
        return "⚠️ مشکلی در پردازش شرح حال شما رخ داد. لطفاً دوباره امتحان کنید."
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره در پردازش LLM: {str(e)}", exc_info=True)
        return "⚠️ خطای غیرمنتظره‌ای رخ داد. لطفاً دوباره تلاش کنید."

def receive_daily_report(update: Update, context: CallbackContext) -> None:
    """دریافت و پردازش گزارش روزانه سلامت از کاربر.

    گزارش متنی کاربر را دریافت، اطلاعات را با LLM استخراج و در دیتابیس ذخیره می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی متن گزارش.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Notes:
        - اگر کاربر قفل شده باشد، اجازه ارسال گزارش نمی‌دهد.
        - اگر کاربر ثبت‌نام نکرده باشد، از او خواسته می‌شود با /start ثبت‌نام کند.
    """
    user_report = update.message.text
    user_id = update.message.from_user.id
    logger.info(f"📩 دریافت شرح حال از کاربر {user_id}: {user_report}")

    # بررسی وضعیت قفل کاربر
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT is_locked FROM user_profiles WHERE telegram_id = %s", (user_id,))
            result = cur.fetchone()
            if result and result[0]:
                update.message.reply_text("⚠️ حساب شما قفل شده است. با پشتیبانی تماس بگیرید.")
                return
    finally:
        if conn:
            db_pool.putconn(conn)
    
    extracted_info = extract_info_from_text(user_report)
    if isinstance(extracted_info, str):
        update.message.reply_text(extracted_info)
        return

    response_message = (
        "📋 **اطلاعات استخراج‌شده:**\n"
        f"🩺 **وضعیت سلامت:** {extracted_info.get('health_status', 'بدون پاسخ')}\n"
        f"💊 **نیاز به دارو:** {extracted_info.get('need_for_medicines', 'بدون پاسخ')}\n"
        f"⚡ **وضعیت ضعف:** {extracted_info.get('weakness_status', 'بدون پاسخ')}\n"
        f"💧 **مصرف آب:** {extracted_info.get('water_intake', 'بدون پاسخ')}\n"
        f"🍽 **نوع غذا:** {extracted_info.get('food_preference', 'بدون پاسخ')}\n\n"
        "✅ اگر اطلاعات صحیح است، در دیتابیس ذخیره خواهد شد."
    )
    update.message.reply_text(response_message, parse_mode="Markdown")

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT national_id FROM user_profiles WHERE telegram_id = %s", (user_id,))
            result = cur.fetchone()
            if not result:
                update.message.reply_text("⚠️ ابتدا باید پروفایل خود را ثبت کنید. از /start استفاده کنید.")
                return
            national_id = result[0]
            cur.execute("""
                INSERT INTO daily_reports (national_id, telegram_id, date, health_status, need_for_medicines,
                weakness_status, water_intake, food_preference, timestamp)
                VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, NOW())
            """, (
                national_id, user_id,
                extracted_info.get("health_status", "بدون پاسخ"),
                extracted_info.get("need_for_medicines", "بدون پاسخ"),
                extracted_info.get("weakness_status", "بدون پاسخ"),
                extracted_info.get("water_intake", "بدون پاسخ"),
                extracted_info.get("food_preference", "بدون پاسخ"),
            ))
            conn.commit()
        logger.info(f"✅ گزارش کاربر {user_id} با موفقیت در دیتابیس ذخیره شد.")
        update.message.reply_text("✅ گزارش شما با موفقیت در دیتابیس ذخیره شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ذخیره گزارش کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در ذخیره گزارش. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ذخیره گزارش کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در ذخیره گزارش رخ داد. لطفاً دوباره تلاش کنید.")
    finally:
        if conn:
            db_pool.putconn(conn)

def get_report(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند گزارش‌گیری توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (GET_NATIONAL_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END
    update.message.reply_text("لطفاً کد ملی شخص مورد نظر را ارسال کنید:")
    return GET_NATIONAL_ID

def get_report_national_id(update: Update, context: CallbackContext) -> int:
    """دریافت کد ملی برای گزارش‌گیری یا همه گزارش‌ها.

    کد ملی را اعتبارسنجی کرده و بسته به نوع درخواست (گزارش محدود یا همه گزارش‌ها) ادامه می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی نوع درخواست.

    Returns:
        int: وضعیت بعدی (GET_DAYS یا پایان فرآیند برای همه گزارش‌ها).
    """
    national_id = update.message.text.strip()
    if not validate_national_id(national_id):
        update.message.reply_text("❌ کد ملی نامعتبر است. لطفاً یک کد ملی ۱۰ رقمی معتبر وارد کنید.")
        return GET_NATIONAL_ID
    context.user_data['report_national_id'] = national_id
    if context.user_data.get('all_reports'):
        return get_all_reports(update, context)
    update.message.reply_text("لطفاً تعداد روزهای قبل را وارد کنید (مثلاً 5 برای ۵ روز اخیر):")
    return GET_DAYS

def get_report_days(update: Update, context: CallbackContext) -> int:
    """دریافت تعداد روزها و ارسال گزارش ادمین.

    گزارش‌های کاربر را برای تعداد روزهای مشخص‌شده تولید و ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی تعداد روزها.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی کد ملی.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    days = update.message.text.strip()
    if not days.isdigit() or int(days) < 1:
        update.message.reply_text("❌ تعداد روزها باید یک عدد مثبت باشد. لطفاً دوباره وارد کنید.")
        return GET_DAYS
    days = int(days)
    national_id = context.user_data['report_national_id']
    user_id = update.message.from_user.id

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dr.id, up.name, up.last_name, dr.date, dr.health_status, dr.need_for_medicines, 
                       dr.weakness_status, dr.water_intake, dr.food_preference, dr.timestamp
                FROM daily_reports dr
                JOIN user_profiles up ON dr.national_id = up.national_id
                WHERE dr.national_id = %s AND dr.date >= CURRENT_DATE - %s::interval
                ORDER BY dr.timestamp DESC
            """, (national_id, f"{days} days"))
            
            data = []
            batch_size = 1000
            while True:
                batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                for report in batch:
                    report_id, name, last_name, date, health_status, need_for_medicines, weakness_status, water_intake, food_preference, timestamp = report
                    data.append({
                        "آیدی گزارش": str(report_id),
                        "کد ملی": national_id,
                        "نام": name,
                        "نام خانوادگی": last_name,
                        "تاریخ": str(date),
                        "زمان ارسال": str(timestamp),
                        "وضعیت سلامت": health_status,
                        "نیاز به دارو": need_for_medicines,
                        "وضعیت ضعف": weakness_status,
                        "مصرف آب": water_intake,
                        "نوع غذا": food_preference
                    })

            if not data:
                update.message.reply_text(f"📊 هیچ گزارشی برای کد ملی {national_id} در {days} روز اخیر پیدا نشد.")
                return ConversationHandler.END

            df = pd.DataFrame(data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False, engine='openpyxl')
                tmp_path = tmp.name

            keyboard = [[InlineKeyboardButton("دریافت با فرمت JSON", callback_data=f"json_{national_id}_{days}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            with open(tmp_path, 'rb') as f:
                update.message.reply_document(
                    document=f,
                    filename=f"report_{national_id}_{days}_days.xlsx",
                    caption=f"📊 گزارش {days} روز اخیر برای کد ملی {national_id} (آیدی گزارش‌ها در فایل موجود است)",
                    reply_markup=reply_markup
                )
            os.unlink(tmp_path)
            logger.info(f"✅ گزارش اکسل برای کد ملی {national_id} به ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در گزارش‌گیری ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در دریافت گزارش. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در گزارش‌گیری ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در دریافت گزارش رخ داد. لطفاً دوباره تلاش کنید.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END


def send_json_report(update: Update, context: CallbackContext) -> None:
    """ارسال گزارش به فرمت JSON برای ادمین.

    گزارش‌های کاربر را به صورت JSON تولید و ارسال می‌کند. اگر طول پیام از 4096 کاراکتر بیشتر باشد، به صورت فایل ارسال می‌شود.

    Args:
        update (telegram.Update): شیء آپدیت حاوی درخواست JSON.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی کد ملی و روزها.

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
        Exception: برای خطاهای عمومی غیرمنتظره.
    """
    query = update.callback_query
    query.answer()
    _, national_id, days = query.data.split("_")
    days = int(days)

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dr.id, up.name, up.last_name, dr.date, dr.health_status, dr.need_for_medicines,
                       dr.weakness_status, dr.water_intake, dr.food_preference, dr.timestamp
                FROM daily_reports dr
                JOIN user_profiles up ON dr.national_id = up.national_id
                WHERE dr.national_id = %s AND dr.date >= CURRENT_DATE - %s::interval
                ORDER BY dr.timestamp DESC
            """, (national_id, f"{days} days"))

            data = []
            batch_size = 1000
            while True:
                batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                for report in batch:
                    report_id, name, last_name, date, health_status, need_for_medicines, weakness_status, water_intake, food_preference, timestamp = report
                    data.append({
                        "report_id": str(report_id),
                        "national_id": national_id,
                        "name": name,
                        "last_name": last_name,
                        "date": str(date),
                        "timestamp": str(timestamp),
                        "health_status": health_status,
                        "need_for_medicines": need_for_medicines,
                        "weakness_status": weakness_status,
                        "water_intake": water_intake,
                        "food_preference": food_preference
                    })

            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            if len(json_data) > 4096:  # محدودیت تلگرام برای طول پیام
                with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                    tmp.write(json_data.encode('utf-8'))
                    with open(tmp.name, 'rb') as f:
                        query.message.reply_document(
                            document=f,
                            filename=f"report_{national_id}_{days}.json",
                            caption=f"📊 گزارش JSON برای کد ملی {national_id}"
                        )
                os.unlink(tmp.name)
            else:
                query.edit_message_caption(
                    caption=f"📊 گزارش JSON برای کد ملی {national_id} (آیدی گزارش‌ها شامل شده):\n```{json_data}```",
                    parse_mode="Markdown"
                )
            logger.info(f"✅ گزارش JSON برای کد ملی {national_id} به ادمین {update.effective_user.id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ارسال JSON به ادمین {update.effective_user.id}: {str(e)}", exc_info=True)
        query.edit_message_caption(caption="⚠️ خطای دیتابیس در ارسال گزارش JSON.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ارسال JSON به ادمین {update.effective_user.id}: {str(e)}", exc_info=True)
        query.edit_message_caption(caption="⚠️ مشکلی در ارسال گزارش JSON رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
            

def all_reports(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند مشاهده همه گزارش‌های یک کاربر توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند تا تمام گزارش‌های او را نمایش دهد.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (GET_NATIONAL_ID یا END اگر دسترسی نداشته باشد).

    Notes:
        - این تابع با تنظیم پرچم 'all_reports'، فرآیند را از گزارش‌گیری محدود متمایز می‌کند.
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END

    context.user_data['all_reports'] = True  # تنظیم پرچم برای همه گزارش‌ها
    update.message.reply_text("لطفاً کد ملی کاربر را وارد کنید:")
    return GET_NATIONAL_ID


def get_all_reports(update: Update, context: CallbackContext) -> int:
    """تولید و ارسال همه گزارش‌های یک کاربر برای ادمین.

    تمام گزارش‌های کاربر را از دیتابیس خوانده و به صورت فایل اکسل و گزینه JSON ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی کد ملی کاربر.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    national_id = context.user_data['report_national_id']
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dr.id, up.name, up.last_name, dr.date, dr.health_status, dr.need_for_medicines, 
                       dr.weakness_status, dr.water_intake, dr.food_preference, dr.timestamp
                FROM daily_reports dr
                JOIN user_profiles up ON dr.national_id = up.national_id
                WHERE dr.national_id = %s
                ORDER BY dr.timestamp DESC
            """, (national_id,))
            
            data = []
            batch_size = 1000
            while True:
                batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                for report in batch:
                    report_id, name, last_name, date, health_status, need_for_medicines, weakness_status, water_intake, food_preference, timestamp = report
                    data.append({
                        "آیدی گزارش": str(report_id),
                        "کد ملی": national_id,
                        "نام": name,
                        "نام خانوادگی": last_name,
                        "تاریخ": str(date),
                        "زمان ارسال": str(timestamp),
                        "وضعیت سلامت": health_status,
                        "نیاز به دارو": need_for_medicines,
                        "وضعیت ضعف": weakness_status,
                        "مصرف آب": water_intake,
                        "نوع غذا": food_preference
                    })

            if not data:
                update.message.reply_text(f"📊 هیچ گزارشی برای کد ملی {national_id} پیدا نشد.")
                return ConversationHandler.END

            df = pd.DataFrame(data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False, engine='openpyxl')
                tmp_path = tmp.name

            keyboard = [[InlineKeyboardButton("دریافت با فرمت JSON", callback_data=f"json_all_{national_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            with open(tmp_path, 'rb') as f:
                update.message.reply_document(
                    document=f,
                    filename=f"all_reports_{national_id}.xlsx",
                    caption=f"📊 همه گزارش‌های کاربر با کد ملی {national_id} (آیدی گزارش‌ها در فایل موجود است)",
                    reply_markup=reply_markup
                )
            os.unlink(tmp_path)
            logger.info(f"✅ همه گزارش‌ها برای کد ملی {national_id} به ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در دریافت همه گزارش‌ها برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در دریافت گزارش‌ها.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در دریافت همه گزارش‌ها برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در دریافت گزارش‌ها رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END

def send_json_all_reports(update: Update, context: CallbackContext) -> None:
    """ارسال همه گزارش‌های یک کاربر به فرمت JSON برای ادمین.

    تمام گزارش‌های کاربر را به صورت JSON تولید و ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی درخواست JSON.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی کد ملی.

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    query = update.callback_query
    query.answer()
    _, _, national_id = query.data.split("_")
    user_id = update.effective_user.id

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT dr.id, up.name, up.last_name, dr.date, dr.health_status, dr.need_for_medicines, 
                       dr.weakness_status, dr.water_intake, dr.food_preference, dr.timestamp
                FROM daily_reports dr
                JOIN user_profiles up ON dr.national_id = up.national_id
                WHERE dr.national_id = %s
                ORDER BY dr.timestamp DESC
            """, (national_id,))

            data = []
            batch_size = 1000
            while True:
                batch = cur.fetchmany(batch_size)
                if not batch:
                    break
                for report in batch:
                    report_id, name, last_name, date, health_status, need_for_medicines, weakness_status, water_intake, food_preference, timestamp = report
                    data.append({
                        "report_id": str(report_id),
                        "national_id": national_id,
                        "name": name,
                        "last_name": last_name,
                        "date": str(date),
                        "timestamp": str(timestamp),
                        "health_status": health_status,
                        "need_for_medicines": need_for_medicines,
                        "weakness_status": weakness_status,
                        "water_intake": water_intake,
                        "food_preference": food_preference
                    })

            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            query.edit_message_caption(
                caption=f"📊 همه گزارش‌های JSON برای کد ملی {national_id} (آیدی گزارش‌ها شامل شده):\n```{json_data}```",
                parse_mode="Markdown"
            )
            logger.info(f"✅ گزارش JSON برای کد ملی {national_id} به ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ارسال JSON به ادمین {user_id}: {str(e)}", exc_info=True)
        query.edit_message_caption(caption="⚠️ خطای دیتابیس در ارسال گزارش JSON.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ارسال JSON به ادمین {user_id}: {str(e)}", exc_info=True)
        query.edit_message_caption(caption="⚠️ مشکلی در ارسال گزارش JSON رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)

def get_user_info(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند استخراج اطلاعات کاربر توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (GET_USER_NATIONAL_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END
    update.message.reply_text("لطفاً کد ملی کاربر مورد نظر را وارد کنید:")
    return GET_USER_NATIONAL_ID

def get_user_info_national_id(update: Update, context: CallbackContext) -> int:
    """استخراج و ارسال اطلاعات پروفایل کاربر برای ادمین.

    اطلاعات کاربر را از دیتابیس خوانده و به صورت فایل اکسل و گزینه JSON ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    national_id = update.message.text.strip()
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT telegram_id, name, last_name, phone, gender, age, national_id
                FROM user_profiles
                WHERE national_id = %s
            """, (national_id,))
            result = cur.fetchone()
            if not result:
                update.message.reply_text(f"📊 هیچ کاربری با کد ملی {national_id} پیدا نشد.")
                return ConversationHandler.END

            telegram_id, name, last_name, phone, gender, age, national_id = result
            data = [{
                "تلگرام آیدی": telegram_id,
                "نام": name,
                "نام خانوادگی": last_name,
                "شماره موبایل": phone,
                "جنسیت": gender,
                "سن": age,
                "کد ملی": national_id
            }]

            df = pd.DataFrame(data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False, engine='openpyxl')
                tmp_path = tmp.name

            keyboard = [[InlineKeyboardButton("دریافت با فرمت JSON", callback_data=f"json_user_{national_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            with open(tmp_path, 'rb') as f:
                update.message.reply_document(
                    document=f,
                    filename=f"user_info_{national_id}.xlsx",
                    caption=f"📊 اطلاعات پروفایل کاربر با کد ملی {national_id}",
                    reply_markup=reply_markup
                )
            os.unlink(tmp_path)
            logger.info(f"✅ اطلاعات پروفایل کاربر با کد ملی {national_id} به ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در استخراج اطلاعات کاربر {national_id} برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در استخراج اطلاعات. لطفاً دوباره تلاش کنید.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در استخراج اطلاعات کاربر {national_id} برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در استخراج اطلاعات رخ داد. لطفاً دوباره تلاش کنید.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END

def send_json_user_info(update: Update, context: CallbackContext) -> None:
    """ارسال اطلاعات پروفایل کاربر به فرمت JSON برای ادمین.

    اطلاعات کاربر را به صورت JSON تولید و ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی درخواست JSON.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی کد ملی.

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    query = update.callback_query
    query.answer()
    _, _, national_id = query.data.split("_")
    user_id = update.effective_user.id

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT telegram_id, name, last_name, phone, gender, age, national_id
                FROM user_profiles
                WHERE national_id = %s
            """, (national_id,))
            result = cur.fetchone()
            if result:
                telegram_id, name, last_name, phone, gender, age, national_id = result
                data = {
                    "telegram_id": telegram_id,
                    "name": name,
                    "last_name": last_name,
                    "phone": phone,
                    "gender": gender,
                    "age": age,
                    "national_id": national_id
                }
                json_data = json.dumps(data, ensure_ascii=False, indent=2)
                query.edit_message_caption(
                    caption=f"📊 اطلاعات پروفایل کاربر با کد ملی {national_id}:\n```{json_data}```",
                    parse_mode="Markdown"
                )
                logger.info(f"✅ اطلاعات JSON کاربر با کد ملی {national_id} به ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ارسال JSON اطلاعات کاربر {national_id} به ادمین {user_id}: {str(e)}", exc_info=True)
        query.edit_message_caption(caption="⚠️ خطای دیتابیس در ارسال اطلاعات JSON.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ارسال JSON اطلاعات کاربر {national_id} به ادمین {user_id}: {str(e)}", exc_info=True)
        query.edit_message_caption(caption="⚠️ مشکلی در ارسال اطلاعات JSON رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)

def list_users(update: Update, context: CallbackContext) -> None:
    """ارسال لیست همه کاربران به ادمین.

    لیست کاربران ثبت‌شده را به صورت فایل اکسل برای ادمین ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id, name, last_name, national_id FROM user_profiles")
            users = cur.fetchall()
            if not users:
                update.message.reply_text("📊 هیچ کاربری ثبت نشده است.")
                return
            
            data = [{"تلگرام آیدی": t_id, "نام": name, "نام خانوادگی": l_name, "کد ملی": n_id} 
                    for t_id, name, l_name, n_id in users]
            df = pd.DataFrame(data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                df.to_excel(tmp.name, index=False, engine='openpyxl')
                tmp_path = tmp.name
            
            with open(tmp_path, 'rb') as f:
                update.message.reply_document(
                    document=f,
                    filename="user_list.xlsx",
                    caption="📊 لیست کاربران ثبت‌شده"
                )
            os.unlink(tmp_path)
            logger.info(f"✅ لیست کاربران برای ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در لیست کاربران برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در دریافت لیست کاربران.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در لیست کاربران برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در دریافت لیست کاربران رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)

def delete_user(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند حذف کاربر توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (DELETE_USER_NATIONAL_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END
    update.message.reply_text("لطفاً کد ملی کاربری که می‌خواهید حذف کنید را وارد کنید:")
    return DELETE_USER_NATIONAL_ID

def delete_user_national_id(update: Update, context: CallbackContext) -> int:
    """حذف کاربر و گزارش‌هایش از دیتابیس.

    کاربر و تمام گزارش‌های مرتبط با کد ملی واردشده را حذف می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در حذف از دیتابیس رخ دهد.
    """
    national_id = update.message.text.strip()
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM daily_reports WHERE national_id = %s", (national_id,))
            cur.execute("DELETE FROM user_profiles WHERE national_id = %s", (national_id,))
            conn.commit()
            update.message.reply_text(f"✅ کاربر با کد ملی {national_id} و گزارش‌هایش با موفقیت حذف شد.")
            logger.info(f"✅ کاربر با کد ملی {national_id} توسط ادمین {user_id} حذف شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در حذف کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در حذف کاربر.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در حذف کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در حذف کاربر رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END

def edit_user(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند ویرایش اطلاعات کاربر توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (EDIT_USER_NATIONAL_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END

    update.message.reply_text("لطفاً کد ملی کاربری که می‌خواهید ویرایش کنید را وارد کنید:")
    return EDIT_USER_NATIONAL_ID

def edit_user_national_id(update: Update, context: CallbackContext) -> int:
    """دریافت کد ملی کاربر و نمایش منوی ویرایش برای ادمین.

    کد ملی را ذخیره کرده و منویی برای انتخاب فیلد موردنظر نمایش می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره کد ملی و پروفایل.

    Returns:
        int: وضعیت بعدی (EDIT_USER_FIELD یا END اگر کاربر پیدا نشود).

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    national_id = update.message.text.strip()
    context.user_data['edit_national_id'] = national_id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT name, last_name, phone, gender, age, national_id FROM user_profiles WHERE national_id = %s", (national_id,))
            result = cur.fetchone()
            if not result:
                update.message.reply_text(f"⚠️ کاربری با کد ملی {national_id} پیدا نشد.")
                return ConversationHandler.END
            context.user_data['edit_profile'] = dict(zip(['name', 'last_name', 'phone', 'gender', 'age', 'national_id'], result))
        
        keyboard = [
            [InlineKeyboardButton("نام", callback_data="name"), InlineKeyboardButton("نام خانوادگی", callback_data="last_name")],
            [InlineKeyboardButton("شماره موبایل", callback_data="phone"), InlineKeyboardButton("جنسیت", callback_data="gender")],
            [InlineKeyboardButton("سن", callback_data="age"), InlineKeyboardButton("کد ملی", callback_data="national_id")],
            [InlineKeyboardButton("❌ لغو", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("کدام بخش از اطلاعات کاربر را می‌خواهید ویرایش کنید؟", reply_markup=reply_markup)
        return EDIT_USER_FIELD
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ویرایش کاربر {national_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در بررسی کاربر.")
        return ConversationHandler.END
    finally:
        if conn:
            db_pool.putconn(conn)
            
def edit_user_field(update: Update, context: CallbackContext) -> int:
    """مدیریت منوی انتخاب فیلد برای ویرایش توسط ادمین.

    فیلد انتخاب‌شده را ذخیره کرده و از ادمین مقدار جدید را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی انتخاب فیلد از منو.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی پروفایل فعلی.

    Returns:
        int: وضعیت بعدی (EDIT_USER_VALUE یا END در صورت لغو).
    """
    query = update.callback_query
    query.answer()
    if query.data == "cancel":
        query.edit_message_text("❌ فرآیند ویرایش لغو شد.")
        return ConversationHandler.END
    
    field_map = {
        "name": "نام",
        "last_name": "نام خانوادگی",
        "phone": "شماره موبایل",
        "gender": "جنسیت",
        "age": "سن",
        "national_id": "کد ملی"
    }
    context.user_data['edit_field'] = query.data
    current_value = context.user_data['edit_profile'][query.data]
    if query.data == "gender":
        keyboard = [
            [InlineKeyboardButton("👨 مرد", callback_data="مرد"), InlineKeyboardButton("👩 زن", callback_data="زن")],
            [InlineKeyboardButton("❌ لغو", callback_data="لغو")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(f"{field_map[query.data]} فعلی: {current_value}\nلطفاً مقدار جدید را انتخاب کنید:", reply_markup=reply_markup)
        return EDIT_USER_VALUE
    else:
        query.edit_message_text(f"{field_map[query.data]} فعلی: {current_value}\nلطفاً مقدار جدید را وارد کنید:")
        return EDIT_USER_VALUE
    
def edit_user_value(update: Update, context: CallbackContext) -> int:
    """ذخیره مقدار جدید فیلد انتخاب‌شده توسط ادمین.

    مقدار جدید را اعتبارسنجی کرده و در دیتابیس به‌روزرسانی می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی مقدار جدید (پیام یا انتخاب).
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی کد ملی و فیلد.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در به‌روزرسانی دیتابیس رخ دهد.
    """
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    national_id = context.user_data['edit_national_id']
    field = context.user_data['edit_field']
    if update.message:
        new_value = update.message.text.strip()
    else:
        query = update.callback_query
        query.answer()
        if query.data == "لغو":
            query.edit_message_text("❌ فرآیند ویرایش لغو شد.")
            return ConversationHandler.END
        new_value = query.data

    if field == "national_id" and not validate_national_id(new_value):
        update.message.reply_text("❌ کد ملی نامعتبر است. لطفاً یک کد ملی ۱۰ رقمی معتبر وارد کنید.") if update.message else update.callback_query.edit_message_text("❌ کد ملی نامعتبر است.")
        return EDIT_USER_VALUE
    if field == "phone" and (not new_value.isdigit() or len(new_value) != 11):
        update.message.reply_text("❌ شماره موبایل نامعتبر است. لطفاً یک شماره ۱۱ رقمی وارد کنید.") if update.message else update.callback_query.edit_message_text("❌ شماره موبایل نامعتبر است.")
        return EDIT_USER_VALUE
    if field == "age" and (not new_value.isdigit() or int(new_value) < 1 or int(new_value) > 120):
        update.message.reply_text("❌ سن نامعتبر است. لطفاً یک عدد بین ۱ تا ۱۲۰ وارد کنید.") if update.message else update.callback_query.edit_message_text("❌ سن نامعتبر است.")
        return EDIT_USER_VALUE

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(f"UPDATE user_profiles SET {field} = %s WHERE national_id = %s", (new_value, national_id))
            conn.commit()
        update.message.reply_text(f"✅ اطلاعات کاربر با کد ملی {national_id} با موفقیت ویرایش شد.") if update.message else update.callback_query.edit_message_text(f"✅ اطلاعات کاربر با کد ملی {national_id} با موفقیت ویرایش شد.")
        logger.info(f"✅ اطلاعات کاربر {national_id} توسط ادمین {user_id} ویرایش شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در ویرایش کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در ویرایش کاربر.") if update.message else update.callback_query.edit_message_text("⚠️ خطای دیتابیس.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در ویرایش کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در ویرایش کاربر رخ داد.") if update.message else update.callback_query.edit_message_text("⚠️ مشکلی در ویرایش کاربر رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END

def delete_report(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند حذف یک گزارش توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او آیدی گزارش را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (DELETE_REPORT_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END

    update.message.reply_text("لطفاً آیدی گزارش (از /get_report) را وارد کنید:")
    return DELETE_REPORT_ID

def delete_report_id(update: Update, context: CallbackContext) -> int:
    """حذف گزارش مشخص‌شده از دیتابیس توسط ادمین.

    گزارش با آیدی واردشده را از جدول daily_reports حذف می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی آیدی گزارش.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در حذف از دیتابیس رخ دهد.
    """
    report_id = update.message.text.strip()
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM daily_reports WHERE id = %s", (report_id,))
            if cur.rowcount == 0:
                update.message.reply_text(f"⚠️ گزارشی با آیدی {report_id} پیدا نشد.")
            else:
                conn.commit()
                update.message.reply_text(f"✅ گزارش با آیدی {report_id} حذف شد.")
                logger.info(f"✅ گزارش {report_id} توسط ادمین {user_id} حذف شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در حذف گزارش {report_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در حذف گزارش.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در حذف گزارش {report_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در حذف گزارش رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END



def stats(update: Update, context: CallbackContext) -> None:
    """ارسال آمار کلی سیستم به ادمین.

    تعداد کاربران، گزارش‌های امروز و هفته گذشته را نمایش می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Raises:
        psycopg2.Error: اگر خطایی در دسترسی به دیتابیس رخ دهد.
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM user_profiles")
            total_users = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM daily_reports WHERE date = CURRENT_DATE")
            today_reports = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM daily_reports WHERE date >= CURRENT_DATE - INTERVAL '7 days'")
            week_reports = cur.fetchone()[0]
        
        stats_message = (
            "📊 **آمار کل سیستم:**\n"
            f"👥 تعداد کل کاربران: {total_users}\n"
            f"📅 گزارش‌های امروز: {today_reports}\n"
            f"📅 گزارش‌های ۷ روز گذشته: {week_reports}"
        )
        update.message.reply_text(stats_message, parse_mode="Markdown")
        logger.info(f"✅ آمار سیستم برای ادمین {user_id} ارسال شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در آمار سیستم برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در دریافت آمار.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در آمار سیستم برای ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در دریافت آمار رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)

def lock_user(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند قفل کردن کاربر توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (LOCK_USER_NATIONAL_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END
    update.message.reply_text("لطفاً کد ملی کاربری که می‌خواهید قفل کنید را وارد کنید:")
    return LOCK_USER_NATIONAL_ID

def lock_user_national_id(update: Update, context: CallbackContext) -> int:
    """قفل کردن دسترسی کاربر در دیتابیس.

    وضعیت قفل کاربر را به True تغییر می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در به‌روزرسانی دیتابیس رخ دهد.
    """
    national_id = update.message.text.strip()
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("UPDATE user_profiles SET is_locked = TRUE WHERE national_id = %s", (national_id,))
            if cur.rowcount == 0:
                update.message.reply_text(f"⚠️ کاربری با کد ملی {national_id} پیدا نشد.")
            else:
                conn.commit()
                update.message.reply_text(f"✅ کاربر با کد ملی {national_id} قفل شد.")
                logger.info(f"✅ کاربر {national_id} توسط ادمین {user_id} قفل شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در قفل کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در قفل کاربر.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در قفل کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در قفل کاربر رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END

def unlock_user(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند آزادسازی کاربر توسط ادمین.

    دسترسی ادمین را بررسی کرده و از او کد ملی کاربر را درخواست می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (UNLOCK_USER_NATIONAL_ID یا END اگر دسترسی نداشته باشد).
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END
    update.message.reply_text("لطفاً کد ملی کاربری که می‌خواهید آزاد کنید را وارد کنید:")
    return UNLOCK_USER_NATIONAL_ID

def unlock_user_national_id(update: Update, context: CallbackContext) -> int:
    """آزادسازی دسترسی کاربر در دیتابیس.

    وضعیت قفل کاربر را به False تغییر می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت حاوی کد ملی.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).

    Raises:
        psycopg2.Error: اگر خطایی در به‌روزرسانی دیتابیس رخ دهد.
    """
    national_id = update.message.text.strip()
    user_id = update.message.from_user.id
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("UPDATE user_profiles SET is_locked = FALSE WHERE national_id = %s", (national_id,))
            if cur.rowcount == 0:
                update.message.reply_text(f"⚠️ کاربری با کد ملی {national_id} پیدا نشد.")
            else:
                conn.commit()
                update.message.reply_text(f"✅ کاربر با کد ملی {national_id} آزاد شد.")
                logger.info(f"✅ کاربر {national_id} توسط ادمین {user_id} آزاد شد.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطای دیتابیس در آزادسازی کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ خطای دیتابیس در آزادسازی کاربر.")
    except Exception as e:
        logger.error(f"❌ خطای عمومی در آزادسازی کاربر {national_id} توسط ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در آزادسازی کاربر رخ داد.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END


##############################################
# بخش ۴: توابع پشتیبانی و تنظیمات اصلی
##############################################

def help_command(update: Update, context: CallbackContext) -> None:
    """ارسال راهنمای استفاده از ربات به کاربر.

    دستورالعمل‌های کلی استفاده از ربات را به صورت متنی نمایش می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.
    """
    help_text = (
        "📚 **راهنمای استفاده از ربات Health Agent:**\n\n"
        "1. **ثبت‌نام:**\n   با دستور /start اطلاعات خود را وارد کنید.\n"
        "2. **ویرایش اطلاعات:**\n   با /edit\_my\_info می‌توانید پروفایل خود را ویرایش کنید.\n"
        "3. **ارسال گزارش روزانه:**\n   کافی است شرح حال خود را به صورت متن ارسال کنید.\n"
        "4. **پشتیبانی:**\n   با /support با تیم پشتیبانی در ارتباط باشید.\n\n"
        "💡 هر زمان سوالی داشتید، از این دستور دوباره استفاده کنید!"
    )
    update.message.reply_text(help_text, parse_mode="Markdown")


def support(update: Update, context: CallbackContext) -> int:
    """شروع فرآیند پشتیبانی برای کاربر.

    از کاربر درخواست می‌کند پیام خود را برای پشتیبانی ارسال کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: وضعیت بعدی (SUPPORT_MESSAGE).
    """
    update.message.reply_text("📩 لطفاً پیام خود را برای پشتیبانی ارسال کنید:")
    return SUPPORT_MESSAGE

def receive_support_message(update: Update, context: CallbackContext) -> int:
    """دریافت پیام پشتیبانی کاربر و ارسال آن به ادمین‌ها.

    پیام کاربر را به تمام ادمین‌ها با گزینه پاسخ ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی پیام کاربر.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).
    """
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "نامشخص"
    message_text = update.message.text

    support_message = (
        "📩 پیام جدید از کاربر:\n"
        f"👤 نام کاربری: @{username}\n"
        f"🆔 آیدی عددی: {user_id}\n\n"
        f"💬 متن پیام: {message_text}"
    )
    keyboard = [[InlineKeyboardButton("ارسال پاسخ", callback_data=f"reply_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for admin_id in ADMIN_IDS:
        context.bot.send_message(chat_id=admin_id, text=support_message, reply_markup=reply_markup)
    update.message.reply_text("✅ پیام شما به پشتیبانی ارسال شد. منتظر پاسخ بمانید.")
    return ConversationHandler.END

def admin_reply(update: Update, context: CallbackContext) -> int:
    """آماده‌سازی پاسخ ادمین به پیام پشتیبانی کاربر.

    آیدی کاربر را ذخیره کرده و از ادمین درخواست پاسخ می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی درخواست پاسخ.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره آیدی کاربر.

    Returns:
        int: وضعیت بعدی (ADMIN_REPLY).
    """
    query = update.callback_query
    query.answer()
    _, user_id = query.data.split("_")
    context.user_data['support_user_id'] = int(user_id)
    query.edit_message_text("لطفاً پاسخ خود را برای کاربر وارد کنید:")
    return ADMIN_REPLY

def send_admin_reply(update: Update, context: CallbackContext) -> int:
    """ارسال پاسخ ادمین به کاربر.

    پاسخ واردشده توسط ادمین را به کاربر ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی پاسخ ادمین.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی آیدی کاربر.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).
    """
    user_id = context.user_data['support_user_id']
    reply_text = update.message.text
    admin_id = update.message.from_user.id
    keyboard = [[InlineKeyboardButton("ارسال پاسخ", callback_data=f"reply_to_admin_{admin_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        context.bot.send_message(
            chat_id=user_id,
            text=f"📬 پاسخ پشتیبانی:\n{reply_text}",
            reply_markup=reply_markup
        )
        update.message.reply_text(f"✅ پاسخ شما به کاربر با آیدی {user_id} ارسال شد.")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال پاسخ ادمین {admin_id} به کاربر {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در ارسال پاسخ به کاربر رخ داد. لطفاً دوباره تلاش کنید.")
    return ConversationHandler.END

def user_reply(update: Update, context: CallbackContext) -> int:
    """آماده‌سازی پاسخ کاربر به پیام پشتیبانی ادمین.

    آیدی ادمین را ذخیره کرده و از کاربر درخواست پاسخ می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی درخواست پاسخ.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای برای ذخیره آیدی ادمین.

    Returns:
        int: وضعیت بعدی (USER_REPLY).
    """
    query = update.callback_query
    query.answer()
    _, admin_id = query.data.split("_")
    context.user_data['support_admin_id'] = int(admin_id)
    query.edit_message_text("لطفاً پاسخ خود را برای پشتیبانی وارد کنید:")
    return USER_REPLY

def send_user_reply(update: Update, context: CallbackContext) -> int:
    """ارسال پاسخ کاربر به ادمین.

    پاسخ کاربر را به ادمین مربوطه با گزینه پاسخ ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت حاوی پاسخ کاربر.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای حاوی آیدی ادمین.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).
    """
    admin_id = context.user_data['support_admin_id']
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "نامشخص"
    reply_text = update.message.text

    support_message = (
        "📩 پاسخ جدید از کاربر:\n"
        f"👤 نام کاربری: @{username}\n"
        f"🆔 آیدی عددی: {user_id}\n\n"
        f"💬 متن پیام: {reply_text}"
    )
    keyboard = [[InlineKeyboardButton("ارسال پاسخ", callback_data=f"reply_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_message(
        chat_id=admin_id,
        text=support_message,
        reply_markup=reply_markup
    )
    update.message.reply_text("✅ پاسخ شما به پشتیبانی ارسال شد. منتظر پاسخ بمانید.")
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """لغو فرآیندهای در حال اجرا.

    هر فرآیند ConversationHandler را متوقف کرده و پیام لغو نمایش می‌دهد.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Returns:
        int: پایان فرآیند (ConversationHandler.END).
    """
    update.message.reply_text("❌ فرآیند لغو شد.")
    return ConversationHandler.END

def get_logs(update: Update, context: CallbackContext) -> None:
    """ارسال لاگ‌های ربات به ادمین.

    خطاهای ثبت‌شده در فایل لاگ را برای ادمین ارسال می‌کند.

    Args:
        update (telegram.Update): شیء آپدیت دریافت‌شده از تلگرام.
        context (telegram.ext.CallbackContext): اطلاعات زمینه‌ای گفتگو.

    Raises:
        FileNotFoundError: اگر فایل لاگ وجود نداشته باشد.
    """
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return

    args = context.args
    hours = int(args[0]) if args and args[0].isdigit() else 24
    log_file = "health_agent.log"
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.read()
        # فقط لاگ‌های حاوی خطا و ۱۰۰ خط آخر
        recent_logs = '\n'.join(line for line in logs.split('\n') if line.strip() and "ERROR" in line)[-100:]
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp.write(recent_logs.encode('utf-8'))
            tmp_path = tmp.name
        
        with open(tmp_path, 'rb') as f:
            update.message.reply_document(
                document=f,
                filename=f"logs_{hours}_hours.txt",
                caption=f"📜 لاگ‌های {hours} ساعت گذشته (فقط خطاها)"
            )
        os.unlink(tmp_path)
        logger.info(f"✅ لاگ‌ها برای ادمین {user_id} ارسال شد.")
    except FileNotFoundError:
        update.message.reply_text("⚠️ فایل لاگ پیدا نشد.")
        logger.warning(f"❌ فایل لاگ برای ادمین {user_id} پیدا نشد.")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال لاگ‌ها به ادمین {user_id}: {str(e)}", exc_info=True)
        update.message.reply_text("⚠️ مشکلی در ارسال لاگ‌ها رخ داد.")

def main() -> None:
    """راه‌اندازی و اجرای اصلی ربات تلگرامی Health Agent.

    ربات را مقداردهی اولیه کرده، دستورات و هندلرها را تنظیم می‌کند و فرآیند دریافت پیام‌ها را آغاز می‌کند.

    Notes:
        - متغیرهای محیطی باید در فایل .env تنظیم شده باشند.
        - در پایان اجرا، تمام اتصالات دیتابیس بسته می‌شوند.
    """
    updater = Updater(TELEGRAM_API_KEY, use_context=True)
    dp = updater.dispatcher

    # تنظیم دستورات با API تلگرام
    set_bot_commands()

    # ConversationHandler برای ثبت‌نام کاربر
    user_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
            LAST_NAME: [MessageHandler(Filters.text & ~Filters.command, get_last_name)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command, get_phone)],
            GENDER: [CallbackQueryHandler(get_gender, pattern="^(مرد|زن|لغو)$")],
            AGE: [MessageHandler(Filters.text & ~Filters.command, get_age)],
            NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, get_national_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای ویرایش اطلاعات کاربر
    edit_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('edit_my_info', edit_my_info)],
        states={
            EDIT_MENU: [CallbackQueryHandler(edit_menu)],
            EDIT_NAME: [MessageHandler(Filters.text & ~Filters.command, edit_name)],
            EDIT_LAST_NAME: [MessageHandler(Filters.text & ~Filters.command, edit_last_name)],
            EDIT_PHONE: [MessageHandler(Filters.text & ~Filters.command, edit_phone)],
            EDIT_GENDER: [CallbackQueryHandler(edit_gender, pattern="^(مرد|زن|لغو|بدون تغییر)$")],
            EDIT_AGE: [MessageHandler(Filters.text & ~Filters.command, edit_age)],
            EDIT_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, edit_national_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای گزارش‌گیری ادمین و همه گزارش‌ها
    admin_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('get_report', get_report), CommandHandler('all_reports', all_reports)],
        states={
            GET_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, get_report_national_id)],
            GET_DAYS: [MessageHandler(Filters.text & ~Filters.command, get_report_days)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای استخراج اطلاعات کاربر
    user_info_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('get_user_info', get_user_info)],
        states={
            GET_USER_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, get_user_info_national_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای پشتیبانی
    support_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('support', support)],
        states={
            SUPPORT_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, receive_support_message)],
            ADMIN_REPLY: [MessageHandler(Filters.text & ~Filters.command, send_admin_reply)],
            USER_REPLY: [MessageHandler(Filters.text & ~Filters.command, send_user_reply)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای حذف کاربر
    delete_user_handler = ConversationHandler(
        entry_points=[CommandHandler('delete_user', delete_user)],
        states={
            DELETE_USER_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, delete_user_national_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای ویرایش کاربر توسط ادمین
    edit_user_handler = ConversationHandler(
        entry_points=[CommandHandler('edit_user', edit_user)],
        states={
            EDIT_USER_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, edit_user_national_id)],
            EDIT_USER_FIELD: [CallbackQueryHandler(edit_user_field)],
            EDIT_USER_VALUE: [MessageHandler(Filters.text & ~Filters.command, edit_user_value), CallbackQueryHandler(edit_user_value)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای حذف گزارش
    delete_report_handler = ConversationHandler(
        entry_points=[CommandHandler('delete_report', delete_report)],
        states={
            DELETE_REPORT_ID: [MessageHandler(Filters.text & ~Filters.command, delete_report_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای قفل کاربر
    lock_user_handler = ConversationHandler(
        entry_points=[CommandHandler('lock_user', lock_user)],
        states={
            LOCK_USER_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, lock_user_national_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # ConversationHandler برای آزادسازی کاربر
    unlock_user_handler = ConversationHandler(
        entry_points=[CommandHandler('unlock_user', unlock_user)],
        states={
            UNLOCK_USER_NATIONAL_ID: [MessageHandler(Filters.text & ~Filters.command, unlock_user_national_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # اضافه کردن هندلرها به Dispatcher
    dp.add_handler(user_conversation_handler)
    dp.add_handler(edit_conversation_handler)
    dp.add_handler(admin_conversation_handler)
    dp.add_handler(user_info_conversation_handler)
    dp.add_handler(support_conversation_handler)
    dp.add_handler(delete_user_handler)
    dp.add_handler(edit_user_handler)
    dp.add_handler(delete_report_handler)
    dp.add_handler(lock_user_handler)
    dp.add_handler(unlock_user_handler)
    dp.add_handler(CommandHandler('help', help_command))
    dp.add_handler(CommandHandler('list_users', list_users))
    dp.add_handler(CommandHandler('stats', stats))
    dp.add_handler(CommandHandler('get_logs', get_logs))
    dp.add_handler(CallbackQueryHandler(send_json_report, pattern="^json_"))
    dp.add_handler(CallbackQueryHandler(send_json_all_reports, pattern="^json_all_"))
    dp.add_handler(CallbackQueryHandler(send_json_user_info, pattern="^json_user_"))
    dp.add_handler(CallbackQueryHandler(admin_reply, pattern="^reply_"))
    dp.add_handler(CallbackQueryHandler(user_reply, pattern="^reply_to_admin_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, receive_daily_report))

    try:
        updater.start_polling()
        updater.idle()
    finally:
        db_pool.closeall()

if __name__ == '__main__':
    main()