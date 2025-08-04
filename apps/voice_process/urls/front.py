from django.urls import path
from apps.voice_process.views.front import transfer_voice_to_text


urlpatterns = [
    path("speech-to-text/", transfer_voice_to_text, name="speech-to-text")
]
