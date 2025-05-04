from apps.main.views.front import index
from django.urls import path


urlpatterns = [
    path("", index, name="index")
]
