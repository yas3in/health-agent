from django.shortcuts import redirect, render
from django.contrib.admin.views.decorators import staff_member_required
from apps.report.utils import main

def custom_page_not_found(request, exception):
    return render(request, '404.html', status=404)


def custom_page_server_error(request):
    return render(request, "500.html", status=500)


@staff_member_required
def admin_manage(request):
    if request.user.is_superuser:
        if request.method == "GET":
            return render(request, "main/admin.html") 
        if request.method == "POST":
            check = main()
            if check:
                return redirect("report-list")
            raise Exception("error in add report")
    return redirect("report-list")
