from django.http import Http404
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from apps.report.models import Answer, Question, Report, Response
from apps.report.serializer.front import ReportDetailSerializer
from apps.voice_process import utils

from io import BytesIO

from rest_framework.generics import ListAPIView


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
                return redirect("my-report-detail", id=response.id)
        return render(request, "report/report_detail.html", {"report": report, "questions": questions})
        

@login_required
def my_reports_list(request):
    responses = Response.objects.filter(user=request.user).order_by("-id")
    return render(request, "report/my_reports_list.html", {"responses": responses})


@login_required
def my_report_detail(request, id):
    try:
        response = Response.objects.get(id=id)
    except:
        return Http404
    else:
        responses = Answer.objects.filter(response=response)
        return render(request, "report/my_report_detail.html", {"responses": responses, "id": response})


@require_POST
@login_required
def delete_response(request):
    response = request.POST.get('id', None)
    if response is not None:
        try:
            instance = Response.objects.get(id=response)
        except:
            return Http404
        else:
            instance.delete()
            return redirect("my-reports-list")
    else:
        return Http404
    


class ReportDetailAPIView(ListAPIView):
    serializer_class = ReportDetailSerializer
    queryset = Report.objects.all()
    lookup_url_kwarg = "sid"
    lookup_field = "sid"

    def get_queryset(self):
        return super().get_queryset().filter(sid=self.kwargs["id"])


def repdet(request, sid):
    try:
        report = Report.objects.get(sid=sid)
    except Report.DoesNotExist:
        raise Http404
    
    questions = Question.objects.filter(report=report)
    if request.method == "GET":
        return render(request, "report/repdet.html", {"report": report, "questions": questions})