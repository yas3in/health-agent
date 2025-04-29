from django.urls import path

from apps.report.views.front import (
    report_detail_view, report_list_view, my_reports_list, my_report_detail, delete_response
)

urlpatterns = [
    path("", report_list_view, name="report-list"),
    path("<int:sid>/", report_detail_view, name="report-detail"),
    path("my-reports-list/", my_reports_list, name="my-reports-list"),
    path("my-reports-list/<int:id>/", my_report_detail, name="my-report-detail"),
    path("delete-response/", delete_response, name="delete-response"),
]
