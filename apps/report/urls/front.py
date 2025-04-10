from django.urls import path

from apps.report.views.front import (
    report_detail_view, report_list_view,
    my_reports_list, my_reports_detail
)

urlpatterns = [
    path("", report_list_view, name="report-list"),
    path("<int:sid>/", report_detail_view, name="report-detail"),
    path("my-reports-list/", my_reports_list, name="my-reports-list"), 
    path("my-reports-detail/", my_reports_detail, name="my-reports-detail"), 
]
