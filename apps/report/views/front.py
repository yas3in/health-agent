from time import sleep
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from apps.report.models import Question, Report
from apps.report.utils import LimeSurvay, main
from apps.voice_process import utils

from io import BytesIO
import json


class StreamingFile(BytesIO):
    def __init__(self, file):
        super().__init__(file.read())
        self.name = file.name


@login_required
def report_list_view(request):
    reports = Report.objects.all()
    return render(request, "report/report_front_list.html", {"reports": reports})


@login_required
def report_detail_view(request, sid):
    try:
        report = Report.objects.get(sid=sid)
    except:
        raise Http404
    
    questions = Question.objects.filter(report=report)
    if request.method == "GET":
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
    else:
        audio_file = request.FILES["audio_file"]
        print(audio_file)
        if audio_file:
            in_memory_file = StreamingFile(audio_file)
            voice_process = utils.VoiceProcess.handler(voice=in_memory_file, report=report, user=request.user)
            if voice_process is None:
                return render(request, "report/report_detail.html", {"report": report, "questions": questions, "status": False})
            else:
                save_voice = utils.save_voice(voice=audio_file, report=report, user=request.user)
                return render(request, "report/report_detail.html", {"report": report, "questions": questions, "status": True})
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
        

@login_required
def my_reports_list(request):
    return render(request, "report/my_reports_list.html")


@login_required
def my_reports_detail(request):
    return render(request, "report/my_reports_detail.html")