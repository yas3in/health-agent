import json

import jdatetime
from langchain_openai import ChatOpenAI
from openai import OpenAI

from apps.report.models import Answer, Question
from apps.voice_process.models import Voice

AVALAI_BASE_URL = "https://api.avalai.ir/v1"
AVALAI_API_KEY = "aa-jTQuoFCLBel2Wffo3ojPLmIK4t3wwXJxgfnxLHuQrkbrIuE0"

class VoiceProcess:

    @staticmethod
    def chat_completions_api(text, questions):
        messages = [
            {"role": "system", "content": f"""
            شما یک دستیار مفید هستید که برای استخراج اطلاعات مرتبط با سلامت از گزارش‌های روزانه طراحی شده‌اید.
            اطلاعات را در قالب JSON با کلیدهای زیر برگردانید:
            من به شما یک دیکشنری از سوالات میدم که کلیدشون بدون پاسخ هست
            یک متن هم بهت میدم هر کدوم پاسخ این سوالات بود استخراج کن و با بدون پاسخ جایگزین کن
             هر کدوم هم نبود تغییرش نده
            لیست سوالات = {questions}
            توی پاسخ از /n استفاده نکن و یکاری کن وقتی من content رو گرفتم تبدیلش کنم به دیکشنری
            لطفاً فقط JSON خالص برگردانید و از افزودن متن اضافی مثل ```json یا توضیحات خودداری کنید.
        """},
            {"role": "user", "content": text},
        ]
        model_name = "gpt-4o-mini"
        llm = ChatOpenAI(
            model=model_name, base_url=AVALAI_BASE_URL, api_key=AVALAI_API_KEY
        )
        return llm.invoke(messages).model_dump()["content"]
    
    @staticmethod
    def voice_process_api(voice):
        client = OpenAI(
            base_url=AVALAI_BASE_URL,
            api_key=AVALAI_API_KEY
        )
        try:
            transcription = client.audio.transcriptions.create(
                model="whisper-1", 
                file=voice, 
                response_format="text"
            )
        except Exception as e:
            raise e
        return transcription
    
    @classmethod
    def save_answer(cls, user, finaly_text):
        dict_text = json.loads(finaly_text)
        for i in dict_text.items():
            question_instance = Question.objects.filter(question=i[0]).last()
            answers = Answer.objects.create(
                user=user, question=question_instance, answer=i[1], created_time=jdatetime.date.today()
            )
        return True
            
    @classmethod
    def handler(cls, report, voice, user):
        text = cls.voice_process_api(voice)
        if text is None:
            return None
    
        question_dict = {}
        question_quesryset = report.question_report.all()
        for i in question_quesryset:
            question_dict[i.question] =  "بدون پاسخ"
        finaly_text = cls.chat_completions_api(text, question_dict)
        svae_answer = cls.save_answer(user, finaly_text)
        return True


def save_voice(user, report, voice):
    counts = Voice.objects.filter(user=user).count()
    try:
        if counts < 10:
            instance = Voice.objects.create(
                user=user, report=report, audio_file=voice
            )
            return instance
    except Exception as e:
        raise e