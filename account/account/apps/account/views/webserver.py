# pylint: disable=W0613
"""
Web server views for the docs app
"""
import os
from datetime import datetime

from django.http import FileResponse, HttpResponse
from django.views import View

from account.common.conf import account_settings
from account.lib.django.view_helpers import AMWebTxtView, AMWebXmlView


class RobotsTxtView(AMWebTxtView):
    """View to serve the robots.txt file"""

    template_path = "robots.txt"


class SitemapXmlView(AMWebXmlView):
    """View to serve the sitemap.xml file"""

    template_path = "sitemap.xml"
    context = {
        "base_url": account_settings.environment_url,
        "lastmod": datetime.now().strftime("%Y-%m-01"),
        "changefreq": "monthly",
    }


class FaviconView(View):
    """View to serve the favicon.ico file"""

    def get(self, request, *args, **kwargs):
        file_path = os.path.join("account", "static", "images", "logo", "favicon.ico")
        return FileResponse(open(file_path, "rb"), content_type="image/x-icon")


class HealthzView(View):
    """View to serve the healthz endpoint"""

    def get(self, request, *args, **kwargs):
        return HttpResponse("OK", content_type="text/plain")


class ReadinessView(View):
    """
    View to serve the readiness endpoint. Instantiate a ChatBotHelper object to
    force readiness of platform. This is the most likely collection of Python
    objects that will be used in the early stages of the application lifecycle.

    mcdaniel (aug-2025): squelching this idea for now as the overhead of instantiating
    ChatBotHelper is not worth the benefit at this stage.
    """

    def get(self, request, *args, **kwargs):
        return HttpResponse("OK", content_type="text/plain")
