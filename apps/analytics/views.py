"""Staff reporting dashboard and export endpoints."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.analytics.exports import csv_bytes, pdf_bytes, xlsx_bytes
from apps.analytics.services import report_data, report_window


class ReportsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "analytics/reports.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        days = report_window(self.request.GET.get("range"))
        return {
            **super().get_context_data(**kwargs),
            "report": report_data(self.request.user, days),
            "ranges": (7, 30, 90),
        }


@require_GET
def report_export(request, file_format: str):
    if not request.user.is_authenticated or not request.user.is_staff:
        raise Http404
    data = report_data(request.user, report_window(request.GET.get("range")))
    exports = {
        "csv": (csv_bytes, "text/csv; charset=utf-8"),
        "xlsx": (xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "pdf": (pdf_bytes, "application/pdf"),
    }
    renderer, content_type = exports.get(file_format, (None, None))
    if renderer is None:
        raise Http404
    response = HttpResponse(renderer(data), content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="secure-commerce-{data["start"]}-{data["end"]}.{file_format}"'
    return response
