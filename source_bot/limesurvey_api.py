import requests
from dotenv import load_dotenv
import os
import json
import base64
import pandas as pd
import psycopg2.pool
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, ConversationHandler
import tempfile

load_dotenv()

LIMESURVEY_MENU, SELECT_SURVEY, SURVEY_ACTION = range(3)

DATABASE_URL = f"postgresql://health_agent_user:{os.getenv('DATABASE_PASSWORD')}@localhost/health_agent_db"
db_pool = psycopg2.pool.SimpleConnectionPool(1, 20, dsn=DATABASE_URL)

LIMESURVEY_URL = os.getenv("LIMESURVEY_URL")
LIMESURVEY_USERNAME = os.getenv("LIMESURVEY_USERNAME")
LIMESURVEY_PASSWORD = os.getenv("LIMESURVEY_PASSWORD")

logger = logging.getLogger(__name__)

def get_session_key(url, username, password):
    payload = {"method": "get_session_key", "params": [username, password], "id": 1}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get("result")
    raise Exception(f"خطا در دریافت کلید сессион: {response.text}")

def release_session_key(url, session_key):
    payload = {"method": "release_session_key", "params": [session_key], "id": 1}
    response = requests.post(url, json=payload)
    return response.status_code == 200

def list_surveys(url, session_key, username):
    payload = {"method": "list_surveys", "params": [session_key, username], "id": 1}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get("result", [])
    raise Exception(f"خطا در دریافت لیست پرسشنامه‌ها: {response.text}")

def export_completed_responses(url, session_key, survey_id):
    payload = {
        "method": "export_responses",
        "params": [session_key, survey_id, "json", "fa", "complete"],
        "id": 1
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json().get("result")
        if isinstance(result, str):
            responses_data = base64.b64decode(result).decode("utf-8")
            return json.loads(responses_data).get("responses", [])
        elif isinstance(result, dict) and result.get("responses"):
            responses_data = base64.b64decode(result["responses"]).decode("utf-8")
            return json.loads(responses_data)
        return []
    raise Exception(f"خطا در دریافت پاسخ‌ها: {response.text}")

def list_questions(url, session_key, survey_id):
    payload = {
        "method": "list_questions",
        "params": [session_key, survey_id],
        "id": 1
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json().get("result", [])
    raise Exception(f"خطا در دریافت لیست سوالات: {response.text}")

def get_answer_options(url, session_key, survey_id, question_id):
    payload = {
        "method": "get_question_properties",
        "params": [session_key, question_id, ["answeroptions"]],
        "id": 1
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json().get("result", {})
        answer_options = result.get("answeroptions", {})
        return {code: details["answer"] for code, details in answer_options.items() if "answer" in details}
    raise Exception(f"خطا در دریافت گزینه‌های پاسخ برای سوال {question_id}: {response.text}")

def limesurvey_menu(update, context, admin_ids):
    """نمایش منوی اصلی پرسشنامه‌های LimeSurvey برای ادمین."""
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        raise ValueError("نوع به‌روزرسانی نامعتبر است.")

    if user_id not in admin_ids:  # به جای ADMIN_IDS از admin_ids استفاده می‌کنیم
        if update.message:
            update.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        elif update.callback_query:
            update.callback_query.message.reply_text("❌ شما دسترسی به این دستور ندارید!")
        logger.warning(f"کاربر {user_id} سعی کرد به دستور ادمین دسترسی پیدا کند.")
        return ConversationHandler.END

    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT survey_id, title FROM surveys")
            surveys = cur.fetchall()

        keyboard = [[InlineKeyboardButton("دریافت اطلاعات پرسشنامه جدید", callback_data="new_survey")]]
        if surveys:
            for sid, title in surveys:
                keyboard.append([InlineKeyboardButton(f"{title} (ID: {sid})", callback_data=f"survey_{sid}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            update.message.reply_text("📋 منوی پرسشنامه‌ها:", reply_markup=reply_markup)
        elif update.callback_query:
            update.callback_query.message.edit_text("📋 منوی پرسشنامه‌ها:", reply_markup=reply_markup)
        return LIMESURVEY_MENU
    except Exception as e:
        logger.error(f"❌ خطای دیتابیس در منوی LimeSurvey: {str(e)}")
        if update.message:
            update.message.reply_text("⚠️ خطای دیتابیس در نمایش منو.")
        elif update.callback_query:
            update.callback_query.message.edit_text("⚠️ خطای دیتابیس در نمایش منو.")
        return ConversationHandler.END
    finally:
        if conn:
            db_pool.putconn(conn)
            
def handle_limesurvey_menu(update: Update, context: CallbackContext) -> int:
    """مدیریت انتخاب از منوی اصلی LimeSurvey."""
    query = update.callback_query
    query.answer()
    data = query.data

    if data == "new_survey":
        query.edit_message_text("در حال اتصال به LimeSurvey...")
        return fetch_new_surveys(update, context)
    elif data.startswith("survey_"):
        survey_id = data.split("_")[1]
        context.user_data['selected_survey_id'] = survey_id
        keyboard = [
            [InlineKeyboardButton("آپدیت دستی اطلاعات این پرسشنامه", callback_data="update")],
            [InlineKeyboardButton("مشاهده اطلاعات این پرسشنامه", callback_data="view")],
            [InlineKeyboardButton("بازگشت به منوی قبلی", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(f"پرسشنامه انتخاب‌شده (ID: {survey_id})\nچه کاری می‌خواهید انجام دهید؟", 
                                reply_markup=reply_markup)
        return SURVEY_ACTION
    return LIMESURVEY_MENU


def fetch_new_surveys(update: Update, context: CallbackContext) -> int:
    session_key = None
    conn = None
    try:
        session_key = get_session_key(LIMESURVEY_URL, LIMESURVEY_USERNAME, LIMESURVEY_PASSWORD)
        surveys = list_surveys(LIMESURVEY_URL, session_key, LIMESURVEY_USERNAME)
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT survey_id FROM surveys")
            existing_surveys = {row[0] for row in cur.fetchall()}
            new_surveys = [s for s in surveys if str(s['sid']) not in existing_surveys]

        if not new_surveys:
            update.callback_query.edit_message_text("✅ همه پرسشنامه‌ها قبلاً دریافت شده‌اند.")
            return limesurvey_menu(update, context, context.bot_data.get('admin_ids', []))

        keyboard = [[InlineKeyboardButton(f"{s['surveyls_title']} (ID: {s['sid']})", callback_data=f"new_{s['sid']}")]
                    for s in new_surveys]
        keyboard.append([InlineKeyboardButton("بازگشت به منوی قبلی", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.edit_message_text("📋 پرسشنامه‌های جدید موجود:", reply_markup=reply_markup)
        return SELECT_SURVEY
    except Exception as e:
        logger.error(f"❌ خطا در دریافت پرسشنامه‌های جدید: {str(e)}")
        update.callback_query.edit_message_text("⚠️ خطا در اتصال به LimeSurvey.")
        return ConversationHandler.END
    finally:
        if session_key:
            release_session_key(LIMESURVEY_URL, session_key)
        if conn:
            db_pool.putconn(conn)
            

def select_new_survey(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    data = query.data

    if data == "back":
        return limesurvey_menu(update, context, context.bot_data.get('admin_ids', []))

    survey_id = data.split("_")[1]
    session_key = None
    conn = None
    try:
        session_key = get_session_key(LIMESURVEY_URL, LIMESURVEY_USERNAME, LIMESURVEY_PASSWORD)
        responses = export_completed_responses(LIMESURVEY_URL, session_key, survey_id)
        questions = list_questions(LIMESURVEY_URL, session_key, survey_id)
        question_titles = {q["title"]: q["question"] for q in questions}
        question_types = {q["title"]: q["type"] for q in questions}
        survey_title = next(s["surveyls_title"] for s in list_surveys(LIMESURVEY_URL, session_key, LIMESURVEY_USERNAME) if str(s["sid"]) == survey_id)

        if not responses:
            query.edit_message_text(f"⚠️ هیچ پاسخی برای پرسشنامه {survey_title} (ID: {survey_id}) وجود ندارد.")
            return SELECT_SURVEY

        # بقیه کد بدون تغییر...
    except Exception as e:
        logger.error(f"❌ خطا در دریافت پرسشنامه {survey_id}: {str(e)}")
        query.edit_message_text("⚠️ خطا در دریافت اطلاعات پرسشنامه.")
        return ConversationHandler.END
    finally:
        if session_key:
            release_session_key(LIMESURVEY_URL, session_key)
        if conn:
            db_pool.putconn(conn)



def survey_action(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    data = query.data
    survey_id = context.user_data.get('selected_survey_id')

    if data == "back":
        return limesurvey_menu(update, context, context.bot_data.get('admin_ids', []))
    elif data.startswith("view") or data == "view":
        return send_survey_excel(update, context, survey_id)
    elif data == "update":
        return update_survey(update, context, survey_id)
    return SURVEY_ACTION


def send_survey_excel(update, context, survey_id):
    """ارسال اطلاعات پرسشنامه به صورت فایل اکسل."""
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT survey_id, response_id, submit_date, question_title, question_text, answer
                FROM survey_responses WHERE survey_id = %s
            """, (survey_id,))
            responses = cur.fetchall()
            if not responses:
                update.callback_query.edit_message_text("📊 هیچ پاسخی برای این پرسشنامه ثبت نشده است.")
                return ConversationHandler.END

        data = [
            {
                "شناسه پرسشنامه": survey_id,
                "شناسه پاسخ": response_id,
                "تاریخ ارسال": str(submit_date) if submit_date else "نامشخص",
                "عنوان سوال": q_title,
                "متن سوال": q_text,
                "پاسخ": answer if answer is not None else "بدون پاسخ"
            }
            for survey_id, response_id, submit_date, q_title, q_text, answer in responses
        ]

        df = pd.DataFrame(data)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            df.to_excel(tmp.name, index=False, engine='openpyxl')
            tmp_path = tmp.name

        with open(tmp_path, 'rb') as f:
            update.callback_query.message.reply_document(
                document=f,
                filename=f"survey_{survey_id}.xlsx",
                caption=f"📊 اطلاعات پرسشنامه (ID: {survey_id})"
            )
        os.unlink(tmp_path)
        logger.info(f"✅ فایل اکسل پرسشنامه {survey_id} برای ادمین {update.effective_user.id} ارسال شد.")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال فایل اکسل پرسشنامه {survey_id}: {str(e)}")
        update.callback_query.edit_message_text("⚠️ خطا در ارسال اطلاعات پرسشنامه.")
    finally:
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END


def update_survey(update, context, survey_id):
    """بروزرسانی دستی اطلاعات پرسشنامه از LimeSurvey با بررسی اطلاعات جدید."""
    session_key = None
    conn = None
    try:
        session_key = get_session_key(LIMESURVEY_URL, LIMESURVEY_USERNAME, LIMESURVEY_PASSWORD)
        responses = export_completed_responses(LIMESURVEY_URL, session_key, survey_id)
        questions = list_questions(LIMESURVEY_URL, session_key, survey_id)
        question_titles = {q["title"]: q["question"] for q in questions}
        question_types = {q["title"]: q["type"] for q in questions}

        answer_options = {}
        for question in questions:
            if question["type"] == "L":
                options = get_answer_options(LIMESURVEY_URL, session_key, survey_id, question["qid"])
                answer_options[question["title"]] = options

        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM survey_responses WHERE survey_id = %s", (survey_id,))
            initial_count = cur.fetchone()[0]

            for response in responses:
                response_id = str(response.get("id", "نامشخص"))
                submit_date = response.get("submitdate") or None
                for q_title, answer in response.items():
                    if q_title in question_titles and q_title not in ["id", "submitdate", "lastpage", "startlanguage"]:
                        translated_answer = str(answer) if answer is not None else "بدون پاسخ"
                        if question_types.get(q_title) == "Y":
                            translated_answer = "بله" if answer == "Y" else "خیر" if answer == "N" else translated_answer
                        elif question_types.get(q_title) == "L" and q_title in answer_options:
                            translated_answer = answer_options[q_title].get(answer, translated_answer)

                        cur.execute("""
                            INSERT INTO survey_responses (survey_id, response_id, submit_date, question_title, question_text, answer)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (survey_id, response_id, question_title) DO UPDATE
                            SET answer = EXCLUDED.answer, submit_date = EXCLUDED.submit_date
                        """, (survey_id, response_id, submit_date, q_title, question_titles[q_title], translated_answer))

            cur.execute("UPDATE surveys SET last_updated = NOW() WHERE survey_id = %s", (survey_id,))
            cur.execute("SELECT COUNT(*) FROM survey_responses WHERE survey_id = %s", (survey_id,))
            final_count = cur.fetchone()[0]
            conn.commit()

            if final_count > initial_count:
                update.callback_query.edit_message_text(f"✅ اطلاعات پرسشنامه (ID: {survey_id}) با موفقیت بروزرسانی شد! {final_count - initial_count} ردیف جدید اضافه شد.")
            else:
                update.callback_query.edit_message_text(f"✅ اطلاعات پرسشنامه (ID: {survey_id}) بروزرسانی شد.\n❗️ اطلاعات جدیدی به این جدول اضافه نشده است❕")
            logger.info(f"✅ پرسشنامه {survey_id} توسط ادمین {update.effective_user.id} بروزرسانی شد.")
    except Exception as e:
        logger.error(f"❌ خطا در بروزرسانی پرسشنامه {survey_id}: {str(e)}")
        update.callback_query.edit_message_text("⚠️ خطا در بروزرسانی اطلاعات پرسشنامه.")
    finally:
        if session_key:
            release_session_key(LIMESURVEY_URL, session_key)
        if conn:
            db_pool.putconn(conn)
    return ConversationHandler.END


def auto_update_surveys(context, admin_ids):
    session_key = None
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT survey_id FROM surveys")
            survey_ids = [row[0] for row in cur.fetchall()]
        
        if not survey_ids:
            logger.info("ℹ️ هیچ پرسشنامه‌ای برای بروزرسانی خودکار وجود ندارد.")
            return

        session_key = get_session_key(LIMESURVEY_URL, LIMESURVEY_USERNAME, LIMESURVEY_PASSWORD)
        for survey_id in survey_ids:
            responses = export_completed_responses(LIMESURVEY_URL, session_key, survey_id)
            questions = list_questions(LIMESURVEY_URL, session_key, survey_id)
            question_titles = {q["title"]: q["question"] for q in questions}

            with conn.cursor() as cur:
                for response in responses:
                    response_id = str(response.get("id", "نامشخص"))
                    submit_date = response.get("submitdate") or None
                    for q_title, answer in response.items():
                        if q_title in question_titles and q_title not in ["id", "submitdate", "lastpage", "startlanguage"]:
                            cur.execute("""
                                INSERT INTO survey_responses (survey_id, response_id, submit_date, question_title, question_text, answer)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (survey_id, response_id, question_title) DO UPDATE
                                SET answer = EXCLUDED.answer, submit_date = EXCLUDED.submit_date
                            """, (survey_id, response_id, submit_date, q_title, question_titles[q_title], str(answer)))
                cur.execute("UPDATE surveys SET last_updated = NOW() WHERE survey_id = %s", (survey_id,))
                conn.commit()
            logger.info(f"✅ پرسشنامه {survey_id} به صورت خودکار بروزرسانی شد.")
    except Exception as e:
        logger.error(f"❌ خطا در بروزرسانی خودکار پرسشنامه‌ها: {str(e)}", exc_info=True)
        if survey_ids:
            for admin_id in admin_ids:  # به جای ADMIN_IDS از admin_ids استفاده می‌کنیم
                context.bot.send_message(chat_id=admin_id, text=f"⚠️ خطا در بروزرسانی خودکار پرسشنامه‌ها: {str(e)}")
    finally:
        if session_key:
            release_session_key(LIMESURVEY_URL, session_key)
        if conn:
            db_pool.putconn(conn)

        
def init_database():
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS surveys (
                    survey_id VARCHAR(50) PRIMARY KEY,
                    title TEXT NOT NULL,
                    last_updated TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS survey_responses (
                    id SERIAL PRIMARY KEY,
                    survey_id VARCHAR(50) REFERENCES surveys(survey_id),
                    response_id VARCHAR(50),
                    submit_date TIMESTAMP,
                    question_title TEXT,
                    question_text TEXT,
                    answer TEXT,
                    UNIQUE(survey_id, response_id, question_title)
                );
            """)
            conn.commit()
        logger.info("✅ جداول LimeSurvey در دیتابیس بررسی و ایجاد شدند.")
    except psycopg2.Error as e:
        logger.error(f"❌ خطا در ایجاد جداول دیتابیس: {str(e)}")
    finally:
        db_pool.putconn(conn)

