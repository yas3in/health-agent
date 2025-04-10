from django.shortcuts import redirect, render


def index_page(request):
    return redirect("report-list")