from django.urls import path

from apps.report.views.front import (
    report_detail_view, report_list_view, add_report_to_django
)

urlpatterns = [
    path("", report_list_view, name="report-list"),
    path("<int:sid>/", report_detail_view, name="report-detail"),
    path("add/", add_report_to_django, name="session-key"),
    
]
