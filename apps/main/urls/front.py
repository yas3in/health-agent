from django.urls import path

from apps.main.views.front import add_report_to_django


urlpatterns = [
    path("", add_report_to_django, name="index")
]
