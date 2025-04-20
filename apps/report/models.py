from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels


class Report(models.Model):
    sid = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=480)
    description = models.TextField(blank=True)
    created_time = jmodels.jDateField()

    def __str__(self):
        return self.name
    

class Question(models.Model):
    report = models.ForeignKey(Report, related_name="question_report", on_delete=models.CASCADE)
    question = models.TextField()

    def __str__(self):
        return f"{self.report} - {self.question}"


class Response(models.Model):
    report = models.ForeignKey(Report, related_name="response_report", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="response_user", on_delete=models.CASCADE)
    created_time = jmodels.jDateField()

    def __str__(self):
        return f'{self.user} - response: {self.id}'


class Answer(models.Model):
    response = models.ForeignKey(Response, related_name="answer_response", on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name="answer_question", on_delete=models.CASCADE)
    answer = models.TextField()
    created_time = jmodels.jDateField()
    
    def __str__(self):
        return f"{self.question} - {self.answer}"
