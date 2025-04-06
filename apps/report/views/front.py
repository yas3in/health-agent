from django.shortcuts import render
from django.views.generic import ListView

from apps.report.models import Answer, Question, Report



def report_list_view(request):
    reports = Report.objects.all()
    return render(request, "report/report_front_list.html", {"reports": reports})


def report_detail_view(request, id):
    report = Report.objects.get(id=id)
    questions = Question.objects.filter(report=report)
    return render(request, "report/report_detail.html", {"report": report, "questions": questions})