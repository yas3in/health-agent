from django.shortcuts import render
from django.views.generic import ListView

from apps.report.models import Answer, Question, Report
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from apps.voice_process.models import Voice


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
        voice_count = Voice.objects.filter(user=request.user).count()
        if voice_count <= 10:
            file_path = Voice.objects.create(
                user=request.user, report=report, audio_file=audio_file
            )
        return JsonResponse({'message': 'فایل با موفقیت ذخیره شد', 'file_path': file_path})