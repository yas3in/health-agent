from django.urls import path

from apps.main.views.admin import admin_manage


urlpatterns = [
    path("", admin_manage, name="paneladmin"),
]
