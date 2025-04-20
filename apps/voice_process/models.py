from django.db import models

from apps.report.models import Response


class Voice(models.Model):

    def folder_picture_name(self, file):
        return f"{self.report.name}/{self.user.username}/{file}"
    
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="voice_response")
    audio_file = models.FileField(upload_to=folder_picture_name)