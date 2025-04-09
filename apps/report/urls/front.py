from django.urls import path

from apps.report.views.front import (
    report_detail_view, report_list_view, limesurvey_view
)

urlpatterns = [
    path("", report_list_view, name="report-list"),
    path("session/", limesurvey_view, name="session-key"),
    path("<int:id>/", report_detail_view, name="report-detail"),
]
