from django.urls import path

from apps.main.views.front import user_panel, index_page


urlpatterns = [
    path("panel/", user_panel, name="user-panel"),
    path("", index_page, name="index")
]
