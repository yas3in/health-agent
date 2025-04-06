from django.urls import path
from apps.voice_process.views.front import voice_process

urlpatterns = [
    path('upload/', voice_process, name='upload-audio'),
]
