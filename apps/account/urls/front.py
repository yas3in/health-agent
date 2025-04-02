from django.urls import path

from apps.account.views.front import signup_view, login_view


urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
]
