from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.report.models import Answer, Question, Report
from apps.voice_process.models import Voice
from apps.voice_process import utils

from io import BytesIO


class StreamingFile(BytesIO):
    def __init__(self, file):
        super().__init__(file.read())
        self.name = file.name


def report_list_view(request):
    reports = Report.objects.all()
    return render(request, "report/report_front_list.html", {"reports": reports})


@login_required
def report_detail_view(request, id):
    report = Report.objects.get(id=id)
    questions = Question.objects.filter(report=report)
    if request.method == "GET":
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
    else:
        audio_file = request.FILES["audio_file"]
        in_memory_file = StreamingFile(audio_file)
        voice_process = utils.VoiceProcess.handler(voice=in_memory_file, report=report)
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})