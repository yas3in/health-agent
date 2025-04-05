from django.contrib import admin
from django.contrib.admin import register
from .models import Answer, Question, Report


@register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("user", "question", "answer")


@register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("report", "question")


class AnswerInline(admin.TabularInline):
    model = Answer


class QuestionInline(admin.TabularInline):
    model = Question


@register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_time")
    inlines = [QuestionInline]