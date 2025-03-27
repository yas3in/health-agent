import os
import tempfile
import requests
from telegram import Update
from telegram.ext import CallbackContext
from config import AVALAI_API_KEY, BASE_URL, logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read Iran server IP from .env
IRAN_SERVER_IP = os.getenv("IRAN_SERVER_IP")
if not IRAN_SERVER_IP:
    raise ValueError("❌ IRAN_SERVER_IP is not set in the .env file.")

# AVANEGAR API endpoint (using Iran server IP)
AVANEGAR_API_URL = f"http://{IRAN_SERVER_IP}:8080/speechRecognition/v1/file"
AVALAI_LLM_API_URL = f"{BASE_URL}/chat/completions"

def correct_text_with_llm(text: str) -> str:
    headers = {
        "Authorization": f"Bearer {AVALAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": """
                این متن فارسی از صوت استخراج شده و ممکن است حاوی غلط‌های املایی باشد.
                همچنین ممکن است فاقد نقطه‌گذاری مناسب، مانند نقطه بین جملات، باشد.
                وظایف شما عبارتند از:
                1. تصحیح غلط‌های املایی بر اساس نزدیک‌ترین واژه معتبر فارسی از نظر ساختاری.
                2. تشخیص مرزهای جملات بر اساس زمینه و معنا و افزودن نقطه (.) در پایان هر جمله.
                3. حفظ معنا و سبک اصلی متن.
                فقط متن تصحیح‌شده با نقطه‌ها را برگردانید، بدون توضیحات اضافی.
                """
            },
            {"role": "user", "content": text}
        ]
    }
    try:
        response = requests.post(AVALAI_LLM_API_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.error(f"Error in text correction: {str(e)}")
        return text

def process_voice_to_text(update: Update, context: CallbackContext) -> int:
    logger.info(f"Starting voice message processing for user {update.message.from_user.id}")
    update.message.reply_text("در حال پردازش صوت شما...")

    try:
        logger.debug("Retrieving voice file from Telegram...")
        voice_file = context.bot.get_file(update.message.voice.file_id)
        logger.debug(f"Voice file retrieved: {voice_file.file_id}")

        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                temp_file_path = temp_file.name
                logger.debug(f"Downloading voice file to temporary path: {temp_file_path}")
                voice_file.download(out=open(temp_file_path, 'wb'))
                logger.debug("Voice file downloaded successfully")

            headers = {}  # No need for gateway-token; handled by Iran server (nginx)
            with open(temp_file_path, 'rb') as audio_file:
                files = {'file': (os.path.basename(temp_file_path), audio_file, 'audio/ogg')}
                logger.debug("Sending request to Iran server (proxy to AVANEGAR)...")
                response = requests.post(AVANEGAR_API_URL, headers=headers, files=files, timeout=30)
                logger.debug(f"Response received: status code {response.status_code}")
                logger.debug(f"Raw API response: {response.text}")

            response.raise_for_status()
            if response.status_code == 200:
                response_json = response.json()
                # فقط بخش result رو استخراج می‌کنیم
                transcription_data = response_json.get("data", {}).get("data", {})
                transcription = transcription_data.get("result", "No text found in response")
                logger.info(f"Initial extracted text: {transcription}")

                corrected_text = correct_text_with_llm(transcription)
                logger.info(f"Corrected text with periods: {corrected_text}")

                update.message.text = corrected_text
                update.message.reply_text(f"متن استخراج شده از صوت شما:\n{corrected_text}")

                from report_manager import receive_daily_report
                return receive_daily_report(update, context)

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    logger.debug(f"Temporary file {temp_file_path} deleted")
                except Exception as file_error:
                    logger.warning(f"Could not delete temporary file {temp_file_path}: {str(file_error)}")

    except requests.exceptions.RequestException as e:
        logger.error(f"API Request Failed: {str(e)}")
        update.message.reply_text(f"Error processing voice message: {str(e)}")
        return 1
    except Exception as e:
        logger.error(f"Error processing voice message: {str(e)}")
        update.message.reply_text(f"Error processing voice message: {str(e)}")
        return 1