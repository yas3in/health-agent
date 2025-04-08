from django.contrib import admin
from django.contrib.admin import register

from apps.voice_process.models import Voice


@register(Voice)
class VoiceAdmin(admin.ModelAdmin):
    list_display = ("user", "report", "audio_file")
