from django.db import models
from django.contrib.auth.models import User

from apps.report.models import Report


class Voice(models.Model):

    def folder_picture_name(self, file):
        return f"{self.report.name}/{self.user.username}/{file}"
    
    user = models.ForeignKey(User, related_name="voice_user", on_delete=models.CASCADE)
    report = models.ForeignKey(Report, related_name="voice_report", on_delete=models.CASCADE)
    audio_file = models.FileField(upload_to=folder_picture_name)