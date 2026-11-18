"""Django template and view helper functions."""

import logging
import re
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache

from am.common.conf import am_settings
from am.lib.django import waffle
from am.lib.django.request import AMRequestMixin
from am.lib.django.waffle import AMWaffleSwitches
from am.lib.logging import WaffleSwitchedLoggerWrapper


def should_log(level):
    """Check if logging should be done based on the waffle switch."""
    return waffle.switch_is_active(AMWaffleSwitches.VIEW_LOGGING) and level >= am_settings.log_level


base_logger = logging.getLogger(__name__)
logger = WaffleSwitchedLoggerWrapper(base_logger, should_log)


def redirect_and_expire_cache(path: str = "/"):
    """Redirect to the given path and expire the cache."""
    response = redirect(path)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


# ------------------------------------------------------------------------------
# Web Views
# ------------------------------------------------------------------------------
class AMView(View, AMRequestMixin):
    """
    The foundational base view for all Account Manager views.

    This class serves as the root for every view within the Account Manager application, providing a
    unified interface and shared functionality for web, XML, and text-based views.
    By inheriting from both Django's ``View`` and the custom ``AMRequestMixin``, it
    ensures consistent request handling and integration with Account Manager-specific request features.

    All other view classes in the platform are designed to extend this base, inheriting its
    core logic and conventions. This approach centralizes common behaviors, such as context management,
    template rendering, HTML comment removal, and logging, enabling maintainable and scalable
    development across the platform.

    The ``AMView`` class is intended to be subclassed, allowing developers to build
    specialized views while leveraging the robust foundation it provides. It encapsulates
    essential mechanisms for error handling, template processing, and integration with platform-wide
    configuration, making it the cornerstone of the Account Manager view architecture.
    """

    template_path: str = ""
    context: dict = {}

    def __init__(self, *args, **kwargs):
        """
        Initialize the AMView with request and other arguments.

        This method initializes the AMRequestMixin with the request.

        :param args: Positional arguments, where the first argument is expected to be the HttpRequest.
        :param kwargs: Keyword arguments, which may include the HttpRequest under the 'request'
                          key.
        :return: None
        :rtype: None
        """
        request: Optional[HttpRequest] = kwargs.pop("request", None)
        if args:
            request, *args = args  # type: ignore[assignment]

        AMRequestMixin.__init__(self, request, *args, **kwargs)
        # Django's View.__init__() takes keyword arguments only.
        super().__init__(**kwargs)

    def remove_comments(self, html):
        """
        Remove HTML comments from an html string.

        :param html: The HTML string from which to remove comments.
        :type html: str
        :return: The HTML string without comments.
        :rtype: str
        """
        return re.sub(r"<!--.*?-->", "", html)

    def render_clean_html(self, request: HttpRequest, template_path, context=None):
        """
        Render a template as a string, with HTML comments removed.

        :param request: The HTTP request object.
        :type request: HttpRequest
        :param template_path: The path to the template to render.
        :type template_path: str
        :param context: The context to use for rendering the template.
        :type context: dict, optional
        :return: The rendered, cleaned HTML string.
        :rtype: str
        :raises Exception: Whatever rendering the template raises, after logging it.
        """
        context = context or self.context
        try:
            response = render(request=request, template_name=template_path, context=context)
        # pylint: disable=W0718
        except Exception as e:
            logger.error(
                "%s.render_clean_html(): %s, %s. error: %s",
                self.formatted_class_name,
                self.smarter_build_absolute_uri(request),
                template_path,
                e,
                exc_info=True,
            )
            raise

        html = response.content.decode(response.charset)
        return self.remove_comments(html=html)

    def setup(self, request: HttpRequest, *args, **kwargs):
        """
        Setup the view with the request and any additional arguments.

        This method initializes the AMRequestMixin with the request.

        :param request: The HTTP request object.
        :type request: HttpRequest
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: The result of the superclass setup method.
        :rtype: Any
        """
        logger.info(
            "%s.setup() - request: %s, args: %s, kwargs: %s",
            self.formatted_class_name,
            self.smarter_build_absolute_uri(request),
            args,
            kwargs,
        )
        AMRequestMixin.__init__(self, request=request, *args, **kwargs)
        return super().setup(request, *args, **kwargs)


class AMWebTxtView(AMView):
    """Base view for plain text web views, such as robots.txt."""

    def get(self, request):
        html = self.render_clean_html(request, template_path=self.template_path, context=self.context)
        return HttpResponse(content=html, content_type="text/plain")


class AMWebHtmlView(AMView):
    """
    Base view for smarter web views.

    Includes helpers for rendering and stripping out developer comments.
    """

    # pylint: disable=W0613
    def clean_http_response(self, request: HttpRequest, template_path, *args, context=None, **kwargs):
        """
        Render a template and return an HttpResponse with comments removed.

        :param request: The HTTP request object.
        :type request: HttpRequest
        :param template_path: The path to the template to render.
        :type template_path: str
        :param context: The context to use for rendering the template.
        :type context: dict, optional
        :return: An HttpResponse with the cleaned HTML content.
        :rtype: HttpResponse
        """
        html = self.render_clean_html(request, template_path, context)
        return HttpResponse(content=html, content_type="text/html")

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests and return a cleaned HttpResponse.

        :param request: The HTTP request object.
        :type request: HttpRequest
        :return: An HttpResponse with the cleaned HTML content.
        :rtype: HttpResponse
        """
        return self.clean_http_response(
            request, template_path=self.template_path, context=self.context, *args, **kwargs
        )


@method_decorator(never_cache, name="dispatch")
class AMNeverCachedWebView(AMWebHtmlView):
    """
    A web view whose responses are never cached.

    The ``@never_cache`` decorator, applied to ``dispatch``, tells browsers and proxies not to
    store the response. The view does not require authentication: subclasses that need it,
    such as the login page's view, check it themselves.
    """
