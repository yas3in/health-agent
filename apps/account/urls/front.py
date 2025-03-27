from django.urls import path

from apps.account.views.front import FrontLoginView, FrontSigninView


urlpatterns = [
    path("login/", FrontLoginView.as_view(), name="login"),
    path("signin/", FrontSigninView.as_view(), name="signin"),
]
