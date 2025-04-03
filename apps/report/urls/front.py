from django.urls import path

from apps.report.views.front import ReportListView


urlpatterns = [
    path("", ReportListView.as_view(), name="report-list")
]
