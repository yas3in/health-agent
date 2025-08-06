import json
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from apps.report.models import Answer, Question, Report, Response
from apps.voice_process.utils import RegisterAnswer

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
        data = json.loads(request.body)
        result = RegisterAnswer.handler(data, request.user)
        return JsonResponse({"status": True})
        

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
