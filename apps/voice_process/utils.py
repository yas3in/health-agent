from io import BytesIO
import json

import jdatetime
from langchain_openai import ChatOpenAI
from openai import OpenAI

from apps.report.models import Answer, Question, Response
from apps.voice_process.models import Voice

from django.conf import settings



AVALAI_BASE_URL = settings.AVALAI_BASE_URL
AVALAI_API_KEY = settings.AVALAI_API_KEY

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
            return None
        return transcription
    
    @classmethod
    def save_answer(cls, response, finaly_text):
        dict_text = json.loads(finaly_text)
        for i in dict_text.items():
            question_instance = Question.objects.filter(question=i[0]).last()
            answers = Answer.objects.create(
                response=response, question=question_instance, answer=i[1], created_time=jdatetime.date.today()
            )
        return True
            
    @classmethod
    def create_response(cls, report, user):
        time = jdatetime.date.today()
        instance = Response.objects.create(
            report=report, user=user, created_time=time 
        )
        return instance

    @classmethod
    def handler(cls, report, voice, user):
        response = cls.create_response(report, user)
        text = cls.voice_process_api(voice)
        if text is None:
            return None
    
        question_dict = {}
        question_quesryset = report.question_report.all()
        for i in question_quesryset:
            question_dict[i.question] =  "بدون پاسخ"
            
        finaly_text = cls.chat_completions_api(text, question_dict)
        save_answer = cls.save_answer(response, finaly_text)
        if save_answer:
            return response
        else:
            return None


def save_voice(user, response, voice):
    counts = Voice.objects.filter(response__user=user).count()
    try:
        if counts < 10:
            instance = Voice.objects.create(
                response=response, audio_file=voice
            )
            return instance
    except:
        return False
    

class StreamingFile(BytesIO):
    def __init__(self, file):
        super().__init__(file.read())
        self.name = file.name


def voice_process_api(voice):
    client = OpenAI(
        base_url=AVALAI_BASE_URL,
        api_key=AVALAI_API_KEY
    )
    try:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=voice, 
            response_format="text",
            language="fa"
        )
    except Exception as e:
        raise e
    import json
    return json.loads(transcription)
    