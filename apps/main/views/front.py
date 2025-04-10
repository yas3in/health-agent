from django.shortcuts import redirect, render
from django.contrib.admin.views.decorators import staff_member_required
from apps.report.utils import main

def add_report_to_django(request):
    if request.user.is_superuser:
        if request.method == "GET":
            return render(request, "index.html") 
        if request.method == "POST":
            check = main()
            if check:
                return redirect("report-list")
            raise Exception("error in add report")