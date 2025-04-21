from django.http import Http404
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from apps.report.models import Answer, Question, Report
from apps.voice_process import utils

from io import BytesIO
from django.contrib import messages


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
    except Report.DoesNotExist:
        raise Http404
    
    questions = Question.objects.filter(report=report)
    if request.method == "GET":
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
    else:
        audio_file = request.FILES["audio_file"]
        if audio_file:
            in_memory_file = StreamingFile(audio_file)
            response = utils.VoiceProcess.handler(voice=in_memory_file, report=report, user=request.user)
            if response is None:
                return render(request, "report/report_detail.html", {"report": report, "questions": questions})
            else:
                save_voice = utils.save_voice(user=request.user, voice=audio_file, response=response)
                return render(request, "report/report_detail.html", {"report": report, "questions": questions})
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
        

@login_required
def my_reports_list(request):
    reports = Report.objects.filter(
    question_report__answer_question__user=request.user
    ).distinct()
    return render(request, "report/my_reports_list.html", {"reports": reports})
