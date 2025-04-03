from django.views.generic import ListView

from apps.report.models import Report


class ReportListView(ListView):
    queryset = Report.objects.all()
    model = Report
    context_object_name = "reports"
    template_name_suffix = "_front_list"