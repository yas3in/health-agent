import os

from langchain_openai import ChatOpenAI
from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()

AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")
AVALAI_BASE_URL = os.getenv("AVALAI_BASE_URL")

def chat_completions_api(text):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": text},
    ]
    model_name = "gpt-4o-mini"
    llm = ChatOpenAI(
        model=model_name, base_url=AVALAI_BASE_URL, api_key=AVALAI_API_KEY
    )
    print(llm.invoke(messages).model_dump()["content"])

chat_completions_api(input("text: "))


def voice_process_api():
    client = OpenAI(
        base_url="https://api.avalai.ir/v1",
        api_key=AVALAI_API_KEY
    )

    current_directory = os.path.dirname(os.path.abspath(__file__))
    audio_file_path = os.path.join(current_directory, 'audio.ogg')

    audio_file = open(audio_file_path, "rb")
    transcription = client.audio.transcriptions.create(
        model="whisper-1", 
        file=audio_file, 
        response_format="text"
    )
    print(transcription)