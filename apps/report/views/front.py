from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.report.models import Answer, Question, Report
from apps.voice_process.models import Voice
from apps.voice_process import utils

from pydub import AudioSegment
import io


def report_list_view(request):
    reports = Report.objects.all()
    return render(request, "report/report_front_list.html", {"reports": reports})


@login_required
def report_detail_view(request, id):
    if request.method == "GET":
        report = Report.objects.get(id=id)
        questions = Question.objects.filter(report=report)
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
    else:
        audio_file = request.FILES["audio_file"]
        report = Report.objects.get(id=id)
        in_memory_file = io.BytesIO(audio_file.read())
        in_memory_file.seek(0)
        voice_process = utils.VoiceProcess.handler(voice=in_memory_file, report=report)
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})