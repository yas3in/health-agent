from django.shortcuts import render


def user_panel(request):
    return render(request, "main/user_panel.html")


def index_page(request):
    return render(request, "main/index.html")