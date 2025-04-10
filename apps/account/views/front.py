from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User


def login_view(request):
    if request.method == "POST":
        response = request.POST.get('next', '/')

        username = request.POST.get("username")
        password = request.POST.get("password")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if response.endswith('login/'):
                return redirect('report-list')
            return HttpResponseRedirect(response)
        return redirect('login')
    else:
        if request.user.is_authenticated:
            return redirect('report-list')
    return render(request, "account/login.html")


def signup_view(request):
    if request.method == "POST":
        response = request.POST.get('next', '/')
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        if username and email and password is not None:
            sign_up = User.objects.create_user(username=username, email=email, password=password)
            if sign_up:
                user = authenticate(request, username=username, password=password)
                login(request, user)
                if response.endswith('signup/'):
                    return redirect('report-list')
                return HttpResponseRedirect(response)
            return redirect('login')
        return redirect('signup')
    else:
        if request.user.is_authenticated:
            return redirect('report-list')
        return render(request, "account/signup.html")

