from django.db import models
from django.contrib.auth.models import User


class Report(models.Model):
    name = models.CharField(max_length=480)
    description = models.TextField(blank=True)
    created_time = models.TimeField(auto_now_add=True)


class Question(models.Model):
    report = models.ForeignKey(Report, related_name="question", on_delete=models.CASCADE)
    question = models.TextField()


class Answer(models.Model):
    user = models.ForeignKey(User, related_name="answer", on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="answer", on_delete=models.CASCADE)
    answer = models.TextField()
