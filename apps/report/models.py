from django.db import models
from django.contrib.auth.models import User


class Question(models.Model):
    question = models.TextField()


class Answer(models.Model):
    answer = models.TextField()


class Report(models.Model):
    name = models.CharField()
    user = models.ForeignKey(User, related_name="user", null=True, blank=True, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="user", on_delete=models.CASCADE)
    answer = models.ForeignKey(Answer, related_name="asnwer", null=True, blank=True, on_delete=models.CASCADE)
