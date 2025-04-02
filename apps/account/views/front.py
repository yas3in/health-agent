from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth.models import User


class FrontLoginView(LoginView):
    template_name = 'account/login.html'
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('user-panel')
        return super().dispatch(request, *args, **kwargs)
    

def login_view(request):
    if request.method == "POST":
        response = request.POST.get('next', '/')

        username = request.POST.get("username")
        password = request.POST.get("password")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if response.endswith('login/'):
                return redirect('user-panel')
            return HttpResponseRedirect(response)
        return redirect('login')
    else:
        if request.user.is_authenticated:
            return redirect('user-panel')
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
                    return redirect('user-panel')
                return HttpResponseRedirect(response)
            return redirect('login')
        return redirect('signup')
    else:
        return render(request, "account/signup.html")

