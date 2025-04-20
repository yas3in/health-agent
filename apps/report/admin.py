from django.contrib import admin
from django.contrib.admin import register
from .models import Answer, Question, Report, Response


@register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("response", "question", "answer", "created_time")


@register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("report", "question")


class AnswerInline(admin.TabularInline):
    model = Answer


class QuestionInline(admin.TabularInline):
    model = Question


@register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("sid", "name", "description", "created_time")
    inlines = [QuestionInline]


@register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "created_time")