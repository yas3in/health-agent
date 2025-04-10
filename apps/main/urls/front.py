from django.urls import path

from apps.main.views.front import index_page


urlpatterns = [
    path("", index_page, name="index")
]
