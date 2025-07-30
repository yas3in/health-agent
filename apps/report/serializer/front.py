from rest_framework import serializers
from apps.report.models import Question, Report



class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ("question",)

class ReportDetailSerializer(serializers.ModelSerializer):
    question_report = QuestionSerializer(many=True)
    class Meta:
        model = Report
        fields = ("question_report",)

