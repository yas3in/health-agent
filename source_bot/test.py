# from openai import OpenAI # pip install -U openai

# client = OpenAI(
#     base_url="https://api.avalai.ir/v1",
#     )

# audio_file = open(r"C:\\Users\sadaf\Desktop\audio.ogg", "rb")
# transcription = client.audio.transcriptions.create(
#     model="whisper-1", 
#     file=audio_file, 
#     response_format="text"
# )
# print(transcription.text)
import os
from langchain_openai import ChatOpenAI  # pip install -U langchain_openai

from dotenv import load_dotenv

load_dotenv()
AVALAI_API_KEY = os.getenv("AVALAI_API_KEY")      # کلید API مدل زبان AvalAI
AVALAI_BASE_URL = os.getenv("AVALAI_BASE_URL")      # کلید API مدل زبان AvalAI

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "سلام خوبی"},
]
# استفاده از مدل gpt-4o-mini
model_name = "gpt-4o-mini"


llm = ChatOpenAI(
    model=model_name, base_url=AVALAI_BASE_URL, api_key=AVALAI_API_KEY
)

# print(llm.invoke(messages).model_dump())




from openai import OpenAI # pip install -U openai

client = OpenAI(
    base_url="https://api.avalai.ir/v1",
    api_key=AVALAI_API_KEY
)

current_directory = os.path.dirname(os.path.abspath(__file__))

# ترکیب مسیر دایرکتوری با نام فایل صوتی (مسیر نسبی)
audio_file_path = os.path.join(current_directory, 'audio.ogg')

audio_file = open(audio_file_path, "rb")
transcription = client.audio.transcriptions.create(
    model="whisper-1", 
    file=audio_file, 
    response_format="text"
)
print(transcription)
