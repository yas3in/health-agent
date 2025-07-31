from django.urls import path

from apps.report.views import front as views

urlpatterns = [
    path("", views.report_list_view, name="report-list"),
    path("<int:sid>/", views.report_detail_view, name="report-detail"),
    path("my-reports-list/", views.my_reports_list, name="my-reports-list"),
    path("my-reports-list/<int:id>/", views.my_report_detail, name="my-report-detail"),
    path("delete-response/", views.delete_response, name="delete-response"),
    path("repdet/<int:id>/", views.ReportDetailAPIView.as_view(), name="rd"),
    path("rp/<int:sid>/", views.repdet, name="rd-view"),
]
