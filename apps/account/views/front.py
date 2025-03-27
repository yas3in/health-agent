from django.shortcuts import redirect, render

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView


class FrontLoginView(LoginView):
    template_name = 'account/login.html'
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('user-panel')
        return super().dispatch(request, *args, **kwargs)
    

class FrontSigninView(LoginView):
    pass