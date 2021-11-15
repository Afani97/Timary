from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from . import models

# Register your models here.
admin.site.register(models.UserProfile)
admin.site.register(models.Invoice)
admin.site.register(models.DailyHoursInput)


class TimaryAdminSite(admin.AdminSite):
    index_template = "admin/custom_index.html"

    def custom_page(self, request):
        context = {
            "text": "Hello Admin",
            "page_name": "Custom Page",
            "app_list": self.get_app_list(request),
            **self.each_context(request),
        }
        return TemplateResponse(request, "admin/custom_page.html", context)

    def get_urls(self):
        return [
            path(
                "custom_page/",
                self.admin_view(self.custom_page),
                name="custom_page",
            ),
        ] + super().get_urls()
