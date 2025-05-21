from django.urls import path

from apps.account.views.front import signup_view, login_view, logout_view


urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),
]
