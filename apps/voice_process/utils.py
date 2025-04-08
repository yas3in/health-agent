import os

from langchain_openai import ChatOpenAI
from openai import OpenAI

from dotenv import load_dotenv

from apps.report.models import Report

load_dotenv()

AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")
AVALAI_BASE_URL = os.getenv("AVALAI_BASE_URL")


class VoiceProcess:

    def __init__(self):
        pass

    @classmethod
    def handler(cls, report, voice):
        text = cls.voice_process_api(voice)
        print(report)
        finaly_text = cls.chat_completions_api(text)

    @staticmethod
    def chat_completions_api(text):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
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
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=voice, 
            response_format="text"
        )
        print(transcription)
        return transcription
