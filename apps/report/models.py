from django.db import models
from django.contrib.auth.models import User


class Report(models.Model):
    name = models.CharField()
    description = models.TextField()
    user = models.ForeignKey(User, related_name="user", null=True, blank=True, on_delete=models.CASCADE)
    created_time = models.TimeField(auto_now=True)


class Question(models.Model):
    name = models.ForeignKey(Report, related_name="question", on_delete=models.CASCADE)
    question = models.TextField()


class Answer(models.Model):
    name = models.ForeignKey(Report, related_name="answer", on_delete=models.CASCADE)
    answer = models.TextField()

